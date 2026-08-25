from pathlib import Path

import yaml

from roche_agent.contracts import PipelineConfig


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PipelineConfig.model_validate(data)

