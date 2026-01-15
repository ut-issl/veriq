default:
    just --list

ruff:
    uv run -- ruff check

alias tc := typecheck

# Type check with mypy, basedpyright, and ty
typecheck:
    # -uv run -- mypy .
    # -uv run -- basedpyright .
    -uv run -- ty check .

# Run pytest and generate coverage report
test:
    uv run -- coverage run --source=./src/pdag -m pytest --import-mode importlib
    uv run -- coverage report -m
    uv run -- coverage xml -o ./coverage.xml

# Run pip-licenses against the dependencies
license:
    uv sync --quiet --frozen --no-dev --group license
    uv run --quiet --no-sync -- pip-licenses
    uv sync --quiet

# Lint the code with ruff, mypy, pyright, lint-imports, deptry, and pip-licenses
lint:
    -just --justfile {{ justfile() }} ruff
    -just --justfile {{ justfile() }} typecheck
    -just --justfile {{ justfile() }} license
