# Tool Ideas

Candidate tools for the workspace, in the same mold as `git-sync` / `pdf-scrub`:
small, single-purpose CLIs (typer + rich, src layout, own `pyproject.toml`,
console-script entry point). Ordered by rough fit to current workflow.

---

## 1. `env-audit` — snapshot & diff Python environments across conda + uv

**Problem.** Juggling conda (lab/hardware) and uv (general) means "works on my
machine" drift is invisible until something breaks. Neither `conda env export`
nor `uv pip list` gives a clean cross-ecosystem diff.

**What it does.** Captures a normalized manifest (interpreter version, platform,
resolved package==version set, source: conda vs pip/uv) into a pydantic model,
then diffs two of them.

```
env-audit snapshot                      # capture the active env -> env-audit.toml
env-audit snapshot --name lab           # named snapshot in a local store
env-audit diff lab general              # rich table: added / removed / version-changed
env-audit diff env-audit.toml           # snapshot-vs-current drift check, exit 1 if drift
```

**Why it fits.** Directly targets the conda/uv split. `diff ... && exit 1` makes
it usable as a CI or pre-run guard. **Deps:** typer, rich, pydantic; read
`uv.lock`/`conda list --json`/`importlib.metadata`.

---

## 2. `visa-scan` — discover & health-check lab instruments

**Problem.** Before a measurement run you want to know what's actually on the bus
and responding, without opening a notebook and hand-typing addresses.

**What it does.** Enumerates VISA resources, opens each, queries `*IDN?`, times
the response, flags unreachable/stale. Keeps a small pydantic-modeled registry
mapping friendly aliases -> addresses so scripts stop hardcoding
`GPIB0::7::INSTR`.

```
visa-scan list                          # all resources, rich table
visa-scan idn                           # *IDN? every responder, with latency
visa-scan ping smu                      # health-check one alias, tenacity retry
visa-scan register smu GPIB0::24::INSTR # save alias -> address
```

**Why it fits.** Pure lab utility, no overlap with existing tools. Pairs with
pymeasure (the registry can hand back addresses for `Instrument(...)`).
**Deps:** typer, rich, pydantic, tenacity, pyvisa (optional `[visa]` extra so the
tool installs without hardware drivers present).

---

## 3. `nb-lint` — catch notebook problems before they land in git

**Problem.** Notebooks accumulate issues that plain `nbstripout` doesn't catch:
cells executed out of order, huge embedded outputs bloating the repo, hardcoded
absolute paths (`C:\Users\...`), empty/orphan cells.

**What it does.** Static scan over `.ipynb` files reporting: non-monotonic
execution counts, output payloads over a size threshold, absolute-path string
literals, and empty cells. `--check` exits non-zero for pre-commit use;
`--strip` clears outputs/counts as a convenience.

```
nb-lint check notebooks/               # report, exit 1 on findings
nb-lint check . --max-output-kb 200
nb-lint strip notebooks/analysis.ipynb # clear outputs + exec counts
```

**Why it fits.** Jupyter-heavy workflow + clean git diffs. Note: `nbstripout`
already handles stripping — this earns its place via the *lint* checks
(exec order, path leaks, output bloat), not the strip. **Deps:** typer, rich,
nbformat.

---

## 4. `watch-run` — rerun a command when files change (the `entr` Windows lacks)

**Problem.** On Windows there's no `entr`/`inotifywait`. Re-running tests or a
script on save means alt-tab + up-arrow + enter, forever.

**What it does.** Watches a glob and reruns a command on change, debounced.
The dev-loop primitive.

```
watch-run "**/*.py" -- uv run pytest
watch-run "src/**/*.py" --clear -- uv run python -m mytool
watch-run "*.md" --debounce 500 -- some-build-step
```

**Why it fits.** Fills a genuine Windows gap, uses watchdog (already in your
orbit), complements incremental dev. **Deps:** typer, rich, watchdog.

---

## 5. `peek` — fast terminal preview of tabular / data files

**Problem.** Spinning up a Jupyter kernel just to check the shape, dtypes, and
null counts of a CSV/Parquet is overkill for a five-second look.

**What it does.** One-shot inspector: shape, per-column dtype + null %, head/tail,
quick numeric stats, in-memory size. Supports CSV/TSV/Parquet/Excel/JSON.
Optional `--schema` emits a pydantic model stub from the columns — handy for
turning a raw file into a validated input at a pipeline boundary.

```
peek data.csv                          # shape, dtypes, null %, head
peek results.parquet --stats           # + numeric summary
peek data.csv --schema                 # print a pydantic BaseModel stub
```

**Why it fits.** pandas/forecasting-data heavy, Jupyter-first — this is the
"don't open a kernel" shortcut. The `--schema` flag ties into the pydantic
habit. **Deps:** typer, rich, pandas (or polars), pyarrow.

---

### Rough priority

If picking one to build first: **`watch-run`** (smallest, immediate daily
payoff) or **`visa-scan`** (highest leverage for lab work, no prior art to
compete with). `env-audit` is the most novel but also the most design work
(cross-ecosystem normalization is fiddly).
