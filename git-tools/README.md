# git-tools

Git housekeeping across many repositories at once. Point it at a folder full of clones and it
pulls, pushes, inspects, or tidies every repo under it in one shot — skipping anything dirty,
diverged, or without an upstream. The `hub` commands do the same job against GitHub itself.

## Install

```bash
uv tool install ./git-tools
```

Or run it without installing:

```bash
uv run --package git-tools git-tools status-all [folder]
```

The `hub` commands additionally need the [GitHub CLI](https://cli.github.com) on PATH, already
authenticated (`gh auth login`). Nothing else needs a token — see [Why `gh`](#why-gh).

## Naming convention

One rule: **the `-all` suffix means the operation repeats once per repository.**

| Shape | Meaning | Commands |
|---|---|---|
| `<git-verb>-all` | A git operation applied to every repo found under a folder | `pull-all`, `push-all`, `fetch-all`, `status-all`, `clean-all`, `config-all` |
| `<intent>-all` | A composite that names what it is for rather than one git verb | `sync-all`, `reconcile-all` |
| `hub <verb>` | GitHub-specific, and runs once rather than per repo | `hub list`, `hub audit` |
| `hub <verb>-all` | GitHub-specific, and fans out | `hub clone-all` |

So `git-tools pull-all` is "`git pull`, everywhere", and the absence of `-all` on `hub list` tells
you it is a single query rather than a sweep.

## Usage

```bash
git-tools --help                 # list the available commands
git-tools --version              # print the installed version
```

Every `-all` command takes the same shape:

```bash
git-tools <command> [folder] [--recursive] [--jobs N]
```

- `folder` — Folder containing git repositories. Defaults to the current directory. If `folder`
  itself is a repo, only it is used; otherwise repos are looked for one level below it (or the
  whole tree with `--recursive`, without descending into repos already found).
- `--recursive, -r` — Walk the whole tree, not just one level deep.
- `--jobs, -j` — Repos to process concurrently (default: 8).
- `--dry-run` — On the commands that change things, report without acting.

### The local commands

| Command | Network | Changes your repos | What it does |
|---|---|---|---|
| `sync-all` | yes | yes | Fetch, pull repos that are behind, push repos that are ahead. |
| `reconcile-all` | yes | yes | `sync-all`, plus: rebase diverged repos onto upstream and push. Aborts on conflict. |
| `pull-all` | yes | yes | Fetch and fast-forward pull repos that are behind. **Never pushes.** |
| `push-all` | yes | yes | Fetch and push repos that are ahead. **Never pulls.** |
| `fetch-all` | yes | no | Fetch, then report what is behind/ahead. Touches nothing locally. |
| `status-all` | **no** | no | Report every repo's state offline. Fast. |
| `clean-all` | yes* | yes | Prune stale remote refs, delete merged local branches. |
| `config-all` | no | no | Read one git config key in every repo. |

\* `clean-all --no-prune` makes it fully offline.

`status-all` and `fetch-all` are the same report; the difference is that `status-all` skips the
fetch, so its behind/ahead counts come from the last time you fetched and may be stale. It prints a
banner saying so. Use `status-all` for a quick look, `fetch-all` when the numbers must be right.

### Examples

```bash
git-tools status-all ~/code           # what's the state of everything? (offline, instant)
git-tools pull-all ~/code             # bring everything up to date, push nothing
git-tools push-all ~/code --dry-run   # what am I sitting on that isn't pushed?
git-tools sync-all ~/code -r          # full two-way sync, whole tree
git-tools reconcile-all ~/code        # same, but untangle diverged repos too
git-tools clean-all ~/code --dry-run  # which merged branches could go?
git-tools config-all user.email ~/code --expect '*@gmail.com'
```

That last one is the identity audit: it prints the committer email each repo would use and exits 1
if any repo does not match the glob — handy when you have a work identity and a personal one and
want to be sure you have not been committing under the wrong one.

### `hub` — GitHub

```bash
git-tools hub list [--owner O] [--forks] [--archived] [--limit N]
git-tools hub clone-all [dest] [--owner O] [--forks] [--archived] [--dry-run] [--jobs N]
git-tools hub audit [folder] [--recursive] [--owner O]
```

- `hub list` — your GitHub repositories, with visibility, default branch, and last push.
- `hub clone-all` — clone every repo that is not already in `dest`. An existing directory of the
  same name is left completely alone, so re-running it only fetches what is new.
- `hub audit` — the one neither `git` nor `gh` gives you: cross-references your local clones
  against GitHub.

Forks and archived repos are excluded by default from `list` and `clone-all`; `audit` includes
archived ones, since a checkout of an archived repo is worth knowing about.

```bash
git-tools hub audit ~/code
```

| Status | Meaning |
|---|---|
| `CLONED` | On GitHub and present locally. |
| `MISSING` | On GitHub, not cloned here. |
| `ARCHIVED` | Cloned locally, but archived upstream. |
| `LOCAL_ONLY` | A local repo whose origin is not among the listed GitHub repos (a fork, another account, or an org you did not pass via `--owner`). |
| `NO_REMOTE` | A local repo with no origin, or an origin that is not GitHub — i.e. nothing is backing it up. |

`NO_REMOTE` is the row worth reading: it is a real answer to "is any of my work unbacked?"

## Result statuses

`sync-all`, `reconcile-all`, `pull-all`, `push-all`, `fetch-all`, and `status-all` give each repo
one row:

| Status | Meaning |
|---|---|
| `UP_TO_DATE` | Clean, and level with its upstream. |
| `PULLED` | Clean and behind; fast-forwarded to upstream. |
| `PUSHED` | Clean and ahead; pushed to upstream. |
| `RECONCILED` | Was diverged; rebased onto upstream and pushed (`reconcile-all` only). |
| `BEHIND` | Behind, and this command does not pull (so: `push-all`, `fetch-all`, `status-all`). |
| `AHEAD` | Ahead, and this command does not push (so: `pull-all`, `fetch-all`, `status-all`). |
| `DIRTY` | Uncommitted changes to *tracked* files; reported with its counts but never touched. Untracked files alone do not count — see below. |
| `DIVERGED` | Both behind and ahead; skipped — try `reconcile-all`, or merge/rebase by hand. |
| `CONFLICT` | `reconcile-all` tried to rebase and git could not auto-merge; the rebase was aborted and the repo left exactly as it was. The conflicting paths are in the detail column — resolve by hand. |
| `NO_UPSTREAM` | Detached HEAD, or the current branch has no upstream configured; skipped. |
| `COLLISION` | An untracked local file sits where a pulled file would land; git aborted the pull and the repo was left exactly as it was. The paths are listed in the detail column — move or delete them, then re-run. |
| `PULL_FAILED` | A fast-forward pull was attempted but git refused for some other reason. |
| `PUSH_FAILED` | A push was rejected (e.g. the remote has commits git-tools does not know about). |
| `ERROR` | An unexpected git failure at some other step. |

`PULL_FAILED`, `PUSH_FAILED`, and `ERROR` make the command exit 1; everything else exits 0.

## How a sync works

For each repo found under `folder`:

1. Read the current branch name (and spot a detached HEAD).
2. Check whether any *tracked* file has uncommitted changes.
3. Resolve the upstream branch — no upstream means `NO_UPSTREAM` and stops there.
4. Fetch, to bring the local view of the upstream up to date (skipped by `status-all`).
5. Count commits behind/ahead of upstream.
6. Act: both non-zero is `DIVERGED` (or a rebase under `reconcile-all`); dirty is `DIRTY`;
   behind-only fast-forward pulls if this command pulls, else `BEHIND`; ahead-only pushes if this
   command pushes, else `AHEAD`.

A dirty repo is still fetched and still reports its behind/ahead counts — knowing you are five
commits ahead *and* mid-edit is more useful than being told only that you are mid-edit. It is
never pulled or pushed.

## How `reconcile-all` stays safe

`sync-all` stops at `DIVERGED` because untangling one is a judgement call. `reconcile-all` makes
that call the only way it can be made safely — attempt it, and back out completely if git cannot do
it without help:

1. The repo must be **clean** first. Uncommitted changes to tracked files report `DIRTY` and the
   rebase is never started, so there is nothing in the working tree that a rebase could lose.
2. `git rebase @{u}` replays your local commits on top of the already-fetched upstream. No second
   fetch, so nothing can move underneath the operation.
3. If the rebase exits non-zero for *any* reason — a content conflict, an untracked file in the
   way, anything — `git rebase --abort` runs immediately. That restores HEAD, the index, and the
   working tree to their pre-rebase state. The repo reports `CONFLICT` with the conflicting paths
   and the sweep moves on.
4. Nothing is pushed unless every commit replayed cleanly. A push that is then rejected reports
   `PUSH_FAILED` with the rebase already applied locally — re-running picks up from there.
5. In the pathological case where the abort itself fails and a rebase is still in progress, the
   repo reports `ERROR` saying so rather than pretending it was cleaned up.

The tradeoff to know about: **rebasing rewrites your local commits' SHAs.** Those commits are
unpushed by definition here, so this is normally invisible. But if someone else has pulled your
branch, prefer to resolve it yourself. `--dry-run` reports which repos would be rebased without
touching any of them.

### Untracked files

Untracked files — build output, scratch notes, stray downloads — are no reason to skip a repo, so
they don't make it `DIRTY`. The one way an untracked file can interact with a sync is a **name
collision**: the incoming pull contains a file at a path where you already have an untracked one.
Git refuses that pull rather than clobber your file, and it makes the check *before* touching the
index or working tree, so the abort is atomic — HEAD, tracked files, and your untracked file are
all exactly as they were. git-tools reports this as `COLLISION` with the offending paths and moves
on; nothing is merged, and nothing needs undoing.

Repos are processed concurrently (`--jobs`, default 8) using threads — git operations are I/O-bound
subprocesses, so the GIL isn't a bottleneck.

## How `clean-all` stays safe

- Only `git branch -d` is used, never `-D`. Git itself refuses to delete a branch holding unmerged
  commits, so the worst case is a branch left alone.
- "Merged" is judged against `origin/<default branch>`, not a local branch — so a branch is only
  deleted once its commits are published on the remote.
- The current branch and the default branch are never candidates.
- The default branch is read from `refs/remotes/origin/HEAD`. A repo without it reports
  `NO_REMOTE` and is skipped rather than cleaned against a guess.
- Pruning needs the network but deleting merged branches does not, so an unreachable remote does
  not cost a repo its local cleanup: the prune failure is reported as `ERROR` and the branch
  cleanup still runs. Comparing against a stale `origin/<default>` can only ever delete *fewer*
  branches.

## Why `gh`

The `hub` commands shell out to the GitHub CLI rather than calling the REST API directly. That
mirrors how the rest of git-tools shells out to `git`, and it means authentication, SSO, enterprise
hosts, and rate limiting are `gh`'s problem. No token is ever read, stored, or passed by this tool.
The cost is a hard dependency on `gh` being installed; when it isn't, `hub` commands exit 2 with an
install hint.

## Git commands reference

Every git command a sync shells out to, in order:

| Command | What it does | Why git-tools uses it |
|---|---|---|
| `git rev-parse --abbrev-ref HEAD` | Prints the current branch's short name, or literally `HEAD` when detached. | Labels the repo's branch in the output table, and detects a detached HEAD. |
| `git status --porcelain=v1 --untracked-files=no` | Lists uncommitted changes to tracked files in a stable, script-friendly format; `--untracked-files=no` omits untracked files. | Decides whether a repo is safe to touch. Untracked files are deliberately ignored, since they can't be lost by a fetch or a fast-forward. |
| `git rev-parse --abbrev-ref --symbolic-full-name @{u}` | Resolves the current branch's configured upstream to a short ref like `origin/main`; fails if none is set. | Confirms an upstream exists before comparing, pulling, or pushing; failure means `NO_UPSTREAM`. |
| `git fetch` | Downloads new commits and refs, without touching the working tree or local branches. | Brings the local view of `@{u}` up to date before comparing. Skipped by `status-all`. |
| `git rev-list --left-right --count @{u}...HEAD` | Counts commits reachable from upstream but not `HEAD` (behind), and vice versa (ahead). | The core decision: behind ⇒ pull, ahead ⇒ push, both ⇒ diverged, neither ⇒ up to date. |
| `git pull --ff-only` | Fast-forwards to match upstream; refuses instead of merging or rebasing if that isn't possible. | Only run when strictly behind. `--ff-only` guarantees git-tools never creates a merge commit or rewrites history. |
| `git push` | Uploads local commits on the current branch to its upstream. | Only run when strictly ahead. A rejection fails as `PUSH_FAILED` rather than force-pushing. |

And the ones `clean-all` and `config-all` add:

| Command | Why |
|---|---|
| `git symbolic-ref --short refs/remotes/origin/HEAD` | Finds the remote's default branch, the base that "merged" is judged against. |
| `git remote prune origin` | Drops remote-tracking refs for branches deleted on the remote. |
| `git branch --merged origin/<base>` | Lists local branches whose commits are all published. |
| `git branch -d <name>` | Deletes a merged branch; refuses if anything is unmerged. |
| `git config --get <key>` | Reads the effective value of one config key, including anything inherited from global config or an `includeIf` block. |
| `git remote get-url origin` | Used by `hub audit` to work out which GitHub repo a clone belongs to. |

Every command runs as `git -C <repo> ...` with `GIT_TERMINAL_PROMPT=0`, so an unauthenticated repo
fails fast instead of hanging a worker thread on a credential prompt.

## Development

```bash
uv run pytest git-tools/tests
```

Tests run against real temporary git repositories — a bare "remote" plus clones — rather than
mocking git, so the behaviour under test is git's actual behaviour. The `hub` tests exercise the
audit and parsing logic without touching the network.
