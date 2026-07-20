# tools

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) holding multiple small Python CLI tools, plus a tracked `windows/` directory for PowerShell/batch scripts.

## Layout

```
tools/
├── pyproject.toml     # workspace root — NOT an installable package
├── windows/           # non-Python scripts (PowerShell/batch), tracked as plain files
└── <tool>/            # one directory per Python tool, registered as a workspace member
```

## Conventions

- **Each Python tool is a workspace member**: its own directory, its own `pyproject.toml` with a console-script entry point, src layout (`<tool>/src/<pkg>/`), and its own `tests/`.
- **Shared dev tooling lives at the root** — ruff and pytest configuration in the root `pyproject.toml` applies to every member. The root dev dependency group provides `ruff` and `pytest`.
- **`windows/`** holds PowerShell/batch scripts that aren't Python packages. Each subfolder gets a short README explaining what the scripts do and how to use them.
- **`uv.lock` is committed**; `.venv/` is never committed.

## Tools

### [git-tools](git-tools/README.md)

Git housekeeping across many repos at once. Commands ending in `-all` apply a git operation to every repo under a folder — skipping anything dirty, diverged, or without an upstream — and `hub` commands do the same against GitHub via the `gh` CLI.

```
uv tool install ./git-tools
git-tools status-all [folder]         # offline report on every repo
git-tools pull-all   [folder]         # fast-forward everything that's behind
git-tools push-all   [folder]         # push everything that's ahead
git-tools sync-all   [folder]         # both directions
git-tools clean-all  [folder]         # prune stale refs, drop merged branches
git-tools config-all user.email [folder] --expect '*@gmail.com'
git-tools hub list | clone-all | audit
```

`folder` defaults to the current directory when omitted. Every `-all` command takes `--recursive`, `--jobs N`, and (where it changes something) `--dry-run`.

Naming convention: the `-all` suffix means the operation repeats once per repository, which is why `hub clone-all` has it but `hub list` and `hub audit` — single queries — do not. The `hub` commands need [`gh`](https://cli.github.com) installed and authenticated.

### pdf-scrub

Strips mailto link annotations and watermarks (annotation- and layer-based) from PDFs.

```
uv tool install ./pdf-scrub
pdf-scrub <input.pdf> [output.pdf] [--no-mailto] [--no-watermarks]
```

### Windows scripts

Non-Python PowerShell/batch scripts live in [windows/](windows/README.md): a remote-dev setup kit (SSH/Tailscale/WSL/mosh/tmux), "open shell here" launchers, and a Jupyter kernel diagnostic.

## Using a tool

Install a tool globally:

```
uv tool install ./<tool>
```

Reinstall all tools at once (e.g. after pulling changes), using `--force` so updated source is
always picked up:

```
install_python_tools.bat
```

Run without installing:

```
uv run --package <tool> <command>
```

## Adding a new tool

1. Create the tool directory: `<tool>/`
2. Add it to `members` in the root `pyproject.toml` under `[tool.uv.workspace]`
3. Use src layout: `<tool>/src/<pkg>/` with a `pyproject.toml` defining a console-script entry point (`[project.scripts]`)
4. Add `<tool>/tests/`
5. Add a section for the tool to this README
