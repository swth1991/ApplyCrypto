# Repository Guidelines

## Project Structure & Module Organization
Core Python code lives in `src/`, organized by responsibility:
- `src/cli`: command parsing and orchestration (`analyze`, `list`, `modify`, `clear`)
- `src/config`, `src/collector`, `src/parser`, `src/analyzer`: config loading, file discovery, parsing, and DB-access analysis
- `src/modifier`: LLM-driven code modification, context/code generators, and patchers
- `src/persistence`, `src/models`: JSON persistence and shared domain models
- `src/ui_app`: Streamlit UI

Tests are in `tests/` (`test_*.py`), docs/diagrams in `docs/`, examples in `examples/`, and utility scripts in `scripts/`.

## Build, Test, and Development Commands
- `./scripts/setup.ps1`: creates/activates `venv`, installs from local `wheels/`, installs project editable, verifies `applycrypto`.
- `applycrypto --help`: show CLI entrypoint after environment setup.
- `python main.py analyze --config config.json`: run analysis workflow.
- `python main.py modify --config config.json --dry-run`: preview modifications safely.
- `pytest`: run full test suite with verbose output and coverage (configured in `pyproject.toml`).
- `pytest --cov=src --cov-report=html`: generate HTML coverage report.
- `./scripts/lint.ps1`: run `isort`, `ruff format`, and `ruff check --fix`.
- `python run_ui.py`: start Streamlit UI.

## Coding Style & Naming Conventions
Use Python 3.13+, 4-space indentation, and type hints for public interfaces where practical.  
Follow existing naming patterns: modules/functions in `snake_case`, classes in `PascalCase`, constants in `UPPER_SNAKE_CASE`.  
Run `./scripts/lint.ps1` before committing; formatting and import order are enforced via Ruff/isort.

## Testing Guidelines
Framework: `pytest` (with some `unittest`-style tests collected by pytest).  
Naming conventions are configured in `pyproject.toml`: files `test_*.py`, functions `test_*`, classes `Test*`.  
Add/extend tests in `tests/` next to affected components; include regression coverage for parser/analyzer/modifier changes.

## Commit & Pull Request Guidelines
Recent history favors short, imperative subjects, often Conventional Commit style (e.g., `feat: ...`, `fix: ...`, `refactor: ...`).  
Recommended format: `<type>: <summary>` with focused scope per commit.

For PRs, include:
- what changed and why
- impacted commands/config (example: `config.json` fields)
- test/lint evidence (`pytest`, `./scripts/lint.ps1`)
- sample CLI output or screenshots when UI/reporting behavior changes

## Security & Configuration Tips
Keep secrets in `.env` only (never commit API keys).  
Start from `config.example.json` when creating project-specific config, and review `exclude_dirs`/`exclude_files` before running `modify`.
