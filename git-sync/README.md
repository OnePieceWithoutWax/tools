# git-sync

Syncs every git repository under a folder: fetches, fast-forward pulls repos that are behind,
pushes repos that are ahead, and skips anything dirty, diverged, or without an upstream — so you
can bring a whole directory of clones up to date in one shot.

## Install

```bash
uv tool install ./git-sync
```

Or run it without installing:

```bash
uv run --package git-sync git-sync run [folder]
```

## Usage

```bash
git-sync run [folder] [--recursive] [--dry-run] [--jobs N]
```

- `folder` — Folder containing git repositories. Defaults to the current directory when omitted.
  If `folder` itself is a repo, only it is synced; otherwise repos are looked for one level below
  it (or the whole tree with `--recursive`, without descending into repos already found).
- `--recursive, -r` — Walk the whole tree, not just one level deep.
- `--dry-run` — Report what would happen without making changes.
- `--jobs, -j` — Number of repos to sync concurrently (default: 8).

### Examples

```bash
git-sync run                       # sync every repo under the current directory
git-sync run ~/code --recursive    # walk the whole tree under ~/code
git-sync run . --dry-run           # preview without pulling/pushing
```

## Result statuses

Each repo gets one row in the summary table, with one of these statuses:

| Status | Meaning |
|---|---|
| `UP_TO_DATE` | Clean, and already level with its upstream. |
| `PULLED` | Clean and behind; fast-forwarded to upstream (or would be, under `--dry-run`). |
| `PUSHED` | Clean and ahead; pushed to upstream (or would be, under `--dry-run`). |
| `DIRTY` | Uncommitted changes in the working tree; skipped untouched. |
| `DIVERGED` | Both behind and ahead of upstream; skipped — needs a manual merge/rebase. |
| `NO_UPSTREAM` | Detached HEAD, or the current branch has no upstream configured; skipped. |
| `PULL_FAILED` | A fast-forward pull was attempted but git refused (e.g. it would overwrite a locally modified file); skipped. |
| `PUSH_FAILED` | A push was attempted but was rejected (e.g. the remote has commits git-sync doesn't know about); skipped. |
| `ERROR` | An unexpected git failure at some other step. |

## How it works

For each repo found under `folder`, git-sync runs, in order:

1. Read the current branch name (and spot a detached HEAD).
2. Check the working tree is clean — anything else marks the repo `DIRTY` and stops there.
3. Resolve the upstream branch — no upstream means `NO_UPSTREAM` and stops there.
4. Fetch, to bring the local view of the upstream up to date.
5. Count commits behind/ahead of upstream.
6. Act on the counts: both non-zero is `DIVERGED`; behind-only fast-forward pulls; ahead-only
   pushes; neither is `UP_TO_DATE`. Pull/push are skipped (but still reported) under `--dry-run`.

Repos are synced concurrently (`--jobs`, default 8) using threads — fetch/pull/push are I/O-bound
subprocesses, so the GIL isn't a bottleneck.

## Git commands reference

Every git command git-sync shells out to, in the order the sync uses them, what each one does,
and why:

| Command | What it does | Why git-sync uses it |
|---|---|---|
| `git rev-parse --abbrev-ref HEAD` | Prints the current branch's short name, or literally `HEAD` if in a detached-HEAD state. | Labels the repo's branch in the output table, and detects a detached HEAD. |
| `git status --porcelain` | Lists uncommitted changes (staged, unstaged, untracked) in a stable, script-friendly format; empty output means a clean working tree. | Decides whether a repo is safe to touch — anything not perfectly clean is marked `DIRTY` and left alone. |
| `git rev-parse --abbrev-ref --symbolic-full-name @{u}` | Resolves `@{u}` (the current branch's configured upstream) to a short ref like `origin/main`; fails if no upstream is set. | Confirms an upstream exists before comparing, pulling, or pushing; failure means `NO_UPSTREAM`. |
| `git fetch` | Downloads new commits and refs from the remote, without touching the working tree or local branches. | Brings the local view of `@{u}` up to date before comparing ahead/behind counts. |
| `git rev-list --left-right --count @{u}...HEAD` | Counts commits reachable from upstream but not `HEAD` (behind), and from `HEAD` but not upstream (ahead). | The core sync decision: behind ⇒ pull, ahead ⇒ push, both ⇒ diverged, neither ⇒ up to date. |
| `git pull --ff-only` | Fast-forwards the current branch to match upstream; refuses instead of merging or rebasing if a fast-forward isn't possible. | Only run when strictly behind. `--ff-only` guarantees git-sync never creates a merge commit or rewrites history — a would-be non-fast-forward (e.g. a hidden local edit) fails loudly as `PULL_FAILED` instead of silently clobbering anything. |
| `git push` | Uploads local commits on the current branch to its upstream. | Only run when strictly ahead. A rejection (e.g. the remote moved on) fails as `PUSH_FAILED` rather than force-pushing. |

Every command runs as `git -C <repo> ...` with `GIT_TERMINAL_PROMPT=0`, so an unauthenticated repo
fails fast instead of hanging a worker thread on a credential prompt.

## Development

```bash
uv run pytest git-sync/tests
```
