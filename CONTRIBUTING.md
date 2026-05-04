# Contributing to Agent State DB

Thanks for contributing. Here's how to get started.

## Dev Environment

```bash
git clone https://github.com/vystartasv/agent-state-db.git
cd agent-state-db
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before You Start

- Open an issue first for features or large changes — saves you wasting time
  if it doesn't fit the roadmap
- Bug fixes can go straight to PR

## Branch Naming

```
feat/short-description    # New features
fix/short-description     # Bug fixes
docs/short-description    # Documentation only
chore/short-description   # Tooling, CI, dependencies
```

## Pull Request Checklist

- [ ] Tests pass: `pytest`
- [ ] New code has tests
- [ ] Lint passes: `ruff check .`
- [ ] README updated if needed
- [ ] CHANGELOG entry added under `[Unreleased]`

## Code Style

- Python 3.11+
- Ruff for linting and formatting
- Type hints on all public functions
- Docstrings for public APIs (Google style)

## Testing

```bash
pytest -v
```

Tests live in `tests/` mirroring the `src/` structure.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the design rationale and schema.
