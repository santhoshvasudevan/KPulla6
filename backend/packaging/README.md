# Local finance library packaging (not committed)

The active `pyproject.toml` in this folder is **gitignored** so packaging experiments stay local until you are ready to publish.

## Purpose

`backend/finance/` is framework-independent (no Django). This folder holds a **local** Hatch config to build `kpulla6-finance` as a wheel/sdist for reuse in other projects.

## Setup

1. Copy or edit `pyproject.toml` in this directory (already present locally if you ran the scaffold task).
2. Install build tools in your venv:

   ```bash
   cd backend && .venv/bin/pip install build hatchling
   ```

3. Build artifacts (output goes to `backend/packaging/dist/`, also gitignored):

   ```bash
   cd backend/packaging && ../.venv/bin/python -m build
   ```

4. Editable install for local experiments:

   ```bash
   cd backend/packaging && ../.venv/bin/pip install -e .
   ```

## Gitignored paths

See root `.gitignore` § Local Python packaging:

- `backend/packaging/pyproject.toml`
- `backend/packaging/dist/`
- `build/`, `dist/`, `*.egg-info/`

## Before publishing publicly

- Choose final PyPI name and license
- Add `pyproject.toml` version/changelog policy
- Copy or symlink tests (`test_finance_*.py`) into the distributable layout
- Remove `license = { text = "Proprietary" }` or replace with SPDX id
- Decide whether to commit `pyproject.toml` in a separate extract repo (recommended) rather than this monorepo
