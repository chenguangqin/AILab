# Contributing to SD Harness Starter Kit

Thanks for your interest! This is a **deliberately lean** ~2,000-line baseline meant to be *read* and
*forked*, so contributions that keep it small, clear, and teachable are the most welcome. Bug fixes,
docs, tests, and small focused improvements are ideal.

## Ground rules

- **Keep it lean.** The value of this kit is that you can read it in an afternoon. New features that
  add surface area belong in *your fork* (that's the whole point — see the Level 400 growth path in the
  [README](README.md)), not in the core. Prefer a doc or an `examples/` entry over new framework code.
- **Preserve the two invariants.** Any change must keep (1) deterministic phase advancement — gates
  checked in code, never asked of the model — and (2) the generator/evaluator split (the thing that
  writes is never the thing that decides it's done).
- **Discuss big changes first.** Open an issue before a large PR so we can align on scope and fit.

## Dev setup

Prereqs: Python 3.11+, [`uv`](https://docs.astral.sh/uv/) (or pip).

```bash
uv pip install -e ".[dev]"     # editable install with dev tools
```

## The test gate (run before every PR)

```bash
ruff check harness tests       # lint — must be clean
pytest -q                      # full suite — must be green
```

`tests/test_readiness.py` is load-bearing: it rejects the config bugs (unsatisfiable gates, a missing
terminal gate, bad strategy pairing) that cause runaway loops. If you touch a `method.json`,
`strategy.json`, or the gate/predicate code, make sure the readiness tests still pass — and add a case
if you introduce a new gate shape.

CI (GitHub Actions) runs exactly these two commands on every push and PR; a green local run mirrors it.

## Submitting a change

1. Fork and branch from `main` (e.g. `fix/…`, `docs/…`).
2. Make the change; keep the diff focused. Match the surrounding code's style and comment density.
3. Run the test gate above — both commands green.
4. Open a PR using the template. Describe *what* changed and *why*, and confirm the two invariants hold.

## Reporting security issues

Please **do not** open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md) for private
disclosure.

## License

By contributing, you agree that your contributions will be licensed under the [Apache-2.0](LICENSE)
license that covers this project.
