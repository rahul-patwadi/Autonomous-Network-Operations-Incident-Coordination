# Working agreement: EV decision engine

## Hands-off files — do not write or suggest implementations

The following files hold the core decision logic and are **hand-written by the user only**:

- `schemas.py`
- `cost_model.py`
- `policy.py`

Do not write, complete, or suggest implementations for these files. Do not propose
scoring math, decision/policy logic, or model design (architecture, features, loss
choices), even as a starting draft or "just to unblock you." This applies regardless
of how the request is phrased (e.g. "sketch," "stub," "draft," "just this once").

The only exceptions:

- The user explicitly asks for a **review** of code they've already written in these
  files (style, bugs, types, tests for it).
- The user explicitly asks for a **bug fix** in code they've already written here.

When in doubt about whether a request crosses this line, ask first rather than writing
code into these three files.

## Freely assist with

- Project config and tooling (`pyproject.toml`, `ruff`, `mypy`, `pytest` setup)
- Test scaffolding (fixtures, test file structure) — but not the domain logic under test
- The FastAPI wrapper in `api.py` (routing, request/response plumbing, error handling)
- The synthetic event generator (for `eval/` scenarios and test fixtures)
- The PyTorch training loop's **scaffolding** in `ml/` — structure only (training loop
  boilerplate, checkpointing, CLI/config plumbing), not the model architecture, feature
  choices, or loss/objective design
- Storage/persistence code (`storage.py`) — incident-history storage isn't load-bearing
  decision logic
- Anything in `eval/`, `tests/`, and `adr/` that isn't itself decision/scoring logic

## Project layout

- `schemas.py` — Pydantic models (hand-written)
- `cost_model.py` — cost functions (hand-written)
- `policy.py` — decision logic (hand-written)
- `api.py` — FastAPI wrapper around the above
- `storage.py` — SQLite (via SQLAlchemy) incident-history storage; generic
  JSON-blob persistence, no domain modeling
- `ml/` — PyTorch classifier and training script (model design hand-written; loop
  scaffolding may be assisted)
- `eval/` — eval scripts and labeled scenarios
- `tests/` — pytest suite
- `adr/` — architecture decision records

## Tooling

- Dependency management: `uv` (`uv sync`, `uv add`, `uv run ...`)
- Lint: `uv run ruff check .`
- Type check: `uv run mypy .` (strict mode)
- Tests: `uv run pytest`
