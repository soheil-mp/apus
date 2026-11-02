# Apus task runner. Run `just` to list the recipes.
# Install just with `uv tool install rust-just` (or your package manager).

set shell := ["bash", "-euo", "pipefail", "-c"]

# List the available recipes
default:
    @just --list --unsorted

# Install the workspace, development tools and git hooks
setup:
    uv sync
    uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

# Lint, check formatting, import boundaries and dependency policy
lint: deps
    uv run ruff check .
    uv run ruff format --check .
    uv run lint-imports

# Check dependency licences and the no-ML policy
deps:
    uv run python scripts/check_dependencies.py

# Format code and apply safe lint fixes
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Type-check everything in strict mode
typecheck:
    uv run mypy

# Run the tests with coverage; extra arguments go to pytest (e.g. `just test -k coords`)
test *args:
    uv run pytest --cov --cov-report=term-missing {{ args }}

# Run every pre-commit hook on every file
hooks:
    uv run pre-commit run --all-files

# Everything CI checks, in the same order
check: lint typecheck test

# Serve the documentation site locally with live reload
docs:
    uv run --group docs zensical serve

# Build the documentation site in strict mode into site/
docs-build:
    uv run --group docs zensical build --strict --clean

# Start the local platform with Docker Compose
up:
    @echo "Not available yet: the Compose stack arrives in roadmap item M1.4." >&2
    @exit 1

# Stop the local platform
down:
    @echo "Not available yet: the Compose stack arrives in roadmap item M1.4." >&2
    @exit 1

# Run a seeded scenario end to end and check it against ground truth
e2e:
    @echo "Not available yet: the end-to-end test arrives in roadmap item M1.9." >&2
    @exit 1

# Preview the GitHub issue changes implied by ROADMAP.md (add --apply to make them)
roadmap-sync *args:
    python3 scripts/sync_roadmap_issues.py {{ args }}

# Apply the repository's GitHub settings
repo-settings:
    scripts/repo-settings.sh

# Remove caches and build output
clean:
    rm -rf .mypy_cache .pytest_cache .ruff_cache .hypothesis .coverage coverage.xml htmlcov dist build site .cache
    find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
