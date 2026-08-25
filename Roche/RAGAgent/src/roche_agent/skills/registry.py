from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    description: str
    risk_level: str
    max_steps: int
    allowed_scripts: tuple[str, ...]
    instructions: str
    directory: Path

    def read_reference(self, relative_path: str) -> str:
        path = (self.directory / "references" / relative_path).resolve()
        reference_root = (self.directory / "references").resolve()
        if reference_root not in path.parents:
            raise ValueError("reference path escapes the skill directory")
        return path.read_text(encoding="utf-8")


class SkillRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.skills: dict[str, Skill] = {}

    def discover(self) -> dict[str, Skill]:
        skills: dict[str, Skill] = {}
        for path in sorted(self.root.glob("*/SKILL.md")):
            raw = path.read_text(encoding="utf-8")
            if not raw.startswith("---\n"):
                raise ValueError(f"missing YAML frontmatter: {path}")
            _, frontmatter, instructions = raw.split("---\n", 2)
            metadata = yaml.safe_load(frontmatter)
            skill = Skill(
                name=metadata["name"],
                version=str(metadata["version"]),
                description=metadata["description"],
                risk_level=metadata.get("risk_level", "read_only"),
                max_steps=int(metadata.get("max_steps", 1)),
                allowed_scripts=tuple(metadata.get("allowed_scripts", [])),
                instructions=instructions.strip(),
                directory=path.parent.resolve(),
            )
            if skill.name in skills:
                raise ValueError(f"duplicate skill name: {skill.name}")
            skills[skill.name] = skill
        self.skills = skills
        return skills

    def summaries(self) -> list[dict[str, str]]:
        return [
            {
                "name": skill.name,
                "version": skill.version,
                "description": skill.description,
                "risk_level": skill.risk_level,
            }
            for skill in self.skills.values()
        ]

    def get(self, name: str) -> Skill:
        if name not in self.skills:
            raise KeyError(f"unknown skill: {name}")
        return self.skills[name]

    @staticmethod
    def _load_module(path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(f"roche_skill_{path.parent.name}", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load skill script: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def execute(
        self,
        skill_name: str,
        script_name: str,
        *,
        context: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        skill = self.get(skill_name)
        if skill.risk_level != "read_only":
            raise PermissionError(f"unsupported skill risk level: {skill.risk_level}")
        if script_name not in skill.allowed_scripts:
            raise PermissionError(f"script is not allowlisted: {script_name}")
        script = (skill.directory / "scripts" / script_name).resolve()
        scripts_root = (skill.directory / "scripts").resolve()
        if scripts_root not in script.parents:
            raise ValueError("script path escapes the skill directory")
        module = self._load_module(script)
        if not hasattr(module, "run"):
            raise AttributeError(f"skill script must expose run(): {script}")
        result = module.run(context=context, params=params or {})
        if not isinstance(result, dict):
            raise TypeError("skill script must return a dict")
        return result

