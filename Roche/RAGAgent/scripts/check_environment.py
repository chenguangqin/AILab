from __future__ import annotations

import importlib
import os
import platform
import sys

if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required")


def status(name: str, module: str) -> tuple[str, str]:
    try:
        imported = importlib.import_module(module)
    except Exception as exc:
        return name, f"ERROR: {exc}"
    return name, getattr(imported, "__version__", "installed")


print("Python:", sys.version.split()[0])
print("Platform:", platform.platform())
for name, module in [
    ("LangGraph", "langgraph"),
    ("Pydantic", "pydantic"),
    ("SQLGlot", "sqlglot"),
    ("Langfuse", "langfuse"),
    ("Boto3", "boto3"),
    ("RAGAS(optional)", "ragas"),
]:
    print(f"{name}: {status(name, module)[1]}")

print("Bedrock chat model configured:", bool(os.getenv("BEDROCK_CHAT_MODEL_ID")))
print("Bedrock embedding model configured:", bool(os.getenv("BEDROCK_EMBED_MODEL_ID")))
print(
    "Langfuse configured:",
    all(
        os.getenv(name)
        for name in ["LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    ),
)
