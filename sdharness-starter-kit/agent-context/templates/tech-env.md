<!--
TEMPLATE — tech-env.md (the HOW / constraints). OPTIONAL but powerful: this is the
AUTHORITATIVE layer — it wins over any stack the agent would otherwise free-choose.
If the agent keeps picking the wrong stack, this file is the lever. Delete the
comment and fill in; drop the file entirely to let the agent decide.
-->

# Technical Environment — <Project Name>

## Summary
| Attribute | Value |
|---|---|
| Project type | <greenfield prototype / addition to existing code> |
| Language / runtime | <e.g. Python 3.12> |
| Package manager | <e.g. uv> |
| Deploy target | <local / a cloud — name it, or "none (local only)"> |

## Frameworks & services
| Layer | Choice |
|---|---|
| <e.g. API> | <e.g. FastAPI> |
| <e.g. storage> | <e.g. SQLite (prototype)> |

## Prohibitions
- <anything the agent must NOT use or do>

## Validation commands
<The commands that prove milestones — the agent will run these. e.g. `pytest -q`,
`ruff check .`, a curl against a local endpoint.>
