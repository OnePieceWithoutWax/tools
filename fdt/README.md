# fdt

File and directory housekeeping from one command. Commands are grouped by what
they act on: `fdt folder <verb>` for directories, `fdt file <verb>` for files.

```
uv tool install ./fdt
```

Every command takes an optional folder argument that defaults to the current
directory, and everything that deletes takes `--dry-run`.

## Folder commands

```
fdt folder clean-empty   [path] [-r] [--dry-run] [--include-junk]
fdt folder clean-jupyter [path] [-r] [--dry-run]
fdt folder size          [path] [--depth N] [--top N]
```

### `clean-empty`

Deletes empty folders. Without `-r`/`--recursive` only the immediate
subfolders are considered; with it the tree is walked **bottom-up**, so a
folder holding nothing but empty folders collapses entirely in one pass.

```
fdt folder clean-empty                  # empty subfolders of the cwd
fdt folder clean-empty -r --dry-run     # see what a recursive sweep would take
fdt folder clean-empty D:\scratch -r
fdt folder clean-empty -r --include-junk  # count Thumbs.db / desktop.ini / .DS_Store as "empty"
```

`--include-junk` treats those three zero-value files as if they were not there,
and deletes them along with their folder. It is opt-in because deleting a file
is a real deletion, not a folder cleanup. `--ignore NAME` (repeatable) does the
same for a name you choose.

The folder you point at is never deleted, and symlinks and junctions are
treated as content rather than followed — nothing outside it can be reached.

### `clean-jupyter`

Deletes `.ipynb_checkpoints` folders **and their contents**. Jupyter recreates
the folder on the next save and the checkpoints are copies of notebooks you
still have, so this is a safe sweep — but unlike `clean-empty` it removes
non-empty folders, which is why it is a separate command rather than a flag.

```
fdt folder clean-jupyter -r --dry-run   # list them and the space they hold
fdt folder clean-jupyter ~/notebooks -r
```

### `size`

Which subfolders hold the space, largest first. Folders deeper than `--depth`
still count toward their ancestors' totals; they just get no row of their own.

```
fdt folder size --depth 2 --top 30
```

## File commands

```
fdt file find-large [path] [--top N] [--min-size 10MB]
fdt file find-dupes [path] [--top N] [--min-size 1MB]
```

`find-dupes` compares by size, then by the first 64 KiB, then in full, so a
reported group is a genuine content match rather than a hash guess. It reports
only — nothing is deleted.

```
fdt file find-large -n 30 --min-size 100MB
fdt file find-dupes D:\photos --min-size 1MB
```

## Notes

- `.git`, `.venv`, `node_modules`, `__pycache__`, `.pytest_cache` and similar
  are skipped by every command; pass `--no-default-skips` to include them.
- Sizes accept a unit suffix: `500`, `10MB`, `1.5G`.
- Commands exit 1 if something could not be deleted, so they can be used in a
  scheduled task and actually go red.

## Suggested commands (not built yet)

Candidate additions, roughly in priority order. Most can reuse the existing
walker, `--dry-run` convention, `Status` rows and exit-1-on-failure plumbing.

### `fdt file rename` — rename to a naming style

```
fdt file rename [path] --style kebab [-r] [--dry-run]
                       [--ext lower|upper|keep] [--folders] [--files]
                       [--only "*.md"] [--collide skip|number|error]
```

Styles, given `My Report v2 (final).PDF`:

| style | result |
| --- | --- |
| `pascal` | `MyReportV2Final.PDF` |
| `camel` | `myReportV2Final.PDF` |
| `kebab` | `my-report-v2-final.PDF` |
| `snake` | `my_report_v2_final.PDF` |
| `space` | `My Report V2 Final.PDF` |
| `lower` / `upper` | case-only, separators untouched |

Design points that matter more than the case algorithm:

- **Stem only.** Never touch the extension by default; `--ext lower` is a
  separate opt-in, because `.PDF` -> `.pdf` is a different intent.
- **Windows case-insensitivity.** `Foo.txt` -> `foo.txt` is a no-op rename on
  NTFS that some APIs reject; do it as a two-step through a temp name.
- **Collisions.** `Hello World.txt` and `hello-world.txt` both become
  `hello-world.txt`. Default to `skip` with a `collision` status row rather
  than silently clobbering.
- **Reserved names.** `CON`, `PRN`, `NUL`, `COM1`... A word split can land on
  one. Refuse and report.
- **Round-tripping.** `HTTPServer` -> `http-server` (not `h-t-t-p-server`),
  and `v2` / `2024-01-05` stay intact.
- **Depth order.** With `--folders -r`, rename bottom-up so paths are not
  invalidated mid-walk.

Sibling worth having alongside it: **`fdt file rename-pattern`** — regex/glob
search-replace, sequential numbering (`--number "{n:03}-{name}"`),
prefix/suffix, date stamps from mtime. Same dry-run and collision machinery,
so it is mostly incremental once `rename` exists.

### `fdt file clean-names`

Narrower and safer than a style change: strip what actually breaks things.
Collapse runs of spaces, trim leading/trailing spaces and dots, strip
`<>:"|?*`, transliterate accents and smart quotes to ASCII, replace
non-breaking spaces. Useful before pushing files to Linux, S3 or a sync tool.

### `fdt file find-long-paths`

Report paths over a threshold (default 260) so you find what will break
robocopy, zip or an Explorer copy before it breaks. Reports only. Cheap on top
of the existing walker.

### `fdt folder flatten` / `fdt folder organize`

Two directions of one idea: `flatten` moves all files from a nested tree into
one folder, resolving collisions (the "unpack a mess of download subfolders"
case); `organize` sorts loose files into subfolders by extension, mtime
year/month, or first letter. Both need move-with-rollback semantics, so they
are heavier than the rename work.

### `fdt file find-old` / `fdt folder find-stale`

There is "biggest" but no "oldest". Files not modified in N days, or folders
whose newest file is older than N days — the natural pairing with
`find-large`, since big *and* stale is the interesting set.

### `fdt file dedupe`

`find-dupes` deliberately reports only. The follow-through — delete or
hardlink duplicates, keeping one per group by a
`--keep oldest|newest|shortest-path|first-match` rule — belongs in a separate
command so the reporting one stays harmless. The exact three-stage comparison
it needs already exists.

### `fdt folder compare`

Diff two trees: present in A only, B only, same name but different content,
same content under a different name. Verifies a backup or migration actually
landed. Reuses the chunked compare in `dupes.py`.

### `fdt folder tree`

`size` says where the space went; a `tree` with sizes and a `--filter` shows
the layout. Low value, low cost.
