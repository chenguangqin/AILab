## What does this change?

<!-- A clear, concise description of what this PR does and why. -->

## How was it tested?

- [ ] `ruff check harness tests` — clean
- [ ] `pytest -q` — green (including `test_readiness.py`)

## The two invariants

Confirm that this change preserves:

- [ ] **Deterministic gates** — phases advance only when artifacts exist on disk, checked in code,
  never asked of the model.
- [ ] **Generator/evaluator split** — the thing that writes code (`sandbox.py`) is never the thing
  that decides it's done (`steering.py` / `phase_authority.py`).

## Anything else?

<!-- Link to the issue, note any open questions, or explain non-obvious choices. -->
