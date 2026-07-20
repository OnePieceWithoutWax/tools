# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A uv workspace holding multiple small Python CLI tools, plus a `windows/` directory for PowerShell/batch scripts tracked as plain files. The root `pyproject.toml` is a virtual workspace root — it is NOT an installable package; each Python tool is a workspace member registered in `[tool.uv.workspace] members`.

The numbered `NN-*.md` files at the root are scaffolding/build prompts, not documentation.

## Commands

```
uv sync                              # set up / update the workspace environment
uv run ruff check .                  # lint (config in root pyproject.toml)
uv run ruff format .                 # format
uv run pytest                        # run all tests (testpaths = */tests)
uv run pytest <tool>/tests           # run one tool's tests
uv run pytest <tool>/tests/test_x.py::test_name   # run a single test
uv run --package <tool> <command>    # run a tool's CLI without installing
uv tool install ./<tool>             # install a tool globally
```

## Architecture

- Workspace root `pyproject.toml` holds shared config only: `[tool.uv.workspace]` members, the `dev` dependency group (ruff, pytest), and ruff/pytest settings that every member inherits.
- Each tool is self-contained: `<tool>/pyproject.toml` (with a `[project.scripts]` console-script entry point), `<tool>/src/<pkg>/`, `<tool>/tests/`.
- Adding a tool: create the directory, add it to workspace `members`, use src layout with an entry point, add tests, and document it in a README section.

## Versioning

Each tool carries a semantic version in its own `pyproject.toml` (`version = "MAJOR.MINOR.PATCH"`). When you meaningfully change a tool, bump its version in the same change so `<tool> --version` stays honest: patch for fixes, minor for new backwards-compatible features, major for breaking changes. Only bump the tool(s) actually changed; skip pure test- or comment-only edits. No git tags — the `pyproject.toml` version is the source of truth.

## Conventions

- Every Python tool follows the uv workspace member pattern: own directory, own `pyproject.toml` with a console-script entry point, registered in root `members`.
- Use src layout (`<tool>/src/<pkg>/`) with tests in `<tool>/tests/`.
- Ruff and pytest are configured once at the workspace root; don't duplicate their config in members.
- `windows/` is for PowerShell/batch scripts that aren't Python packages — each subfolder gets a short README explaining its scripts.
- Never commit `.venv`. `uv.lock` is committed.
