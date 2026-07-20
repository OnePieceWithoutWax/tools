"""Diverged-repo reconciliation: rebase when it applies cleanly, abort when it does not."""

from __future__ import annotations

from conftest import RepoSet, commit_file, head_of, push_remote_change, run_git
from git_tools.repo import Status, sync_repo


def _diverge(repos: RepoSet, *, local_file: str = "other.txt") -> None:
    """Put one commit on the remote and one on the local clone, touching different files."""
    push_remote_change(repos)
    commit_file(repos.local, local_file, "local only\n")


def test_diverged_rebases_and_pushes(repos: RepoSet) -> None:
    _diverge(repos)

    result = sync_repo(repos.local, reconcile=True)

    assert result.status is Status.RECONCILED
    assert (result.behind, result.ahead) == (1, 1)
    # Local replayed on top of upstream, then pushed: both sides now agree.
    assert head_of(repos.local) == head_of(repos.remote, "main")
    assert (repos.local / "file.txt").read_text() == "remote change\n"
    assert (repos.local / "other.txt").read_text() == "local only\n"
    # Rebase, not merge: history stays linear.
    parents = run_git(repos.local, "rev-list", "--parents", "-n", "1", "HEAD").stdout.split()
    assert len(parents) == 2


def test_conflicting_rebase_aborts_and_leaves_repo_untouched(repos: RepoSet) -> None:
    # Both sides edit file.txt, so the replay cannot be resolved automatically.
    push_remote_change(repos, "theirs\n")
    commit_file(repos.local, "file.txt", "mine\n")
    local_before = head_of(repos.local)
    remote_before = head_of(repos.remote, "main")

    result = sync_repo(repos.local, reconcile=True)

    assert result.status is Status.CONFLICT
    assert "file.txt" in result.detail
    assert (result.behind, result.ahead) == (1, 1)
    assert head_of(repos.local) == local_before
    assert head_of(repos.remote, "main") == remote_before
    assert (repos.local / "file.txt").read_text() == "mine\n"
    # The abort left no rebase in progress, so the next run starts clean.
    assert run_git(repos.local, "status", "--porcelain").stdout == ""


def test_dirty_diverged_repo_is_never_rebased(repos: RepoSet) -> None:
    _diverge(repos)
    (repos.local / "file.txt").write_text("uncommitted edit\n")
    before = head_of(repos.local)

    result = sync_repo(repos.local, reconcile=True)

    assert result.status is Status.DIRTY
    assert (result.behind, result.ahead) == (1, 1)
    assert head_of(repos.local) == before
    assert (repos.local / "file.txt").read_text() == "uncommitted edit\n"


def test_dry_run_reports_without_rebasing(repos: RepoSet) -> None:
    _diverge(repos)
    local_before = head_of(repos.local)
    remote_before = head_of(repos.remote, "main")

    result = sync_repo(repos.local, reconcile=True, dry_run=True)

    assert result.status is Status.RECONCILED
    assert "dry-run" in result.detail
    assert head_of(repos.local) == local_before
    assert head_of(repos.remote, "main") == remote_before


def test_without_reconcile_diverged_is_still_reported(repos: RepoSet) -> None:
    _diverge(repos)
    before = head_of(repos.local)

    result = sync_repo(repos.local)

    assert result.status is Status.DIVERGED
    assert head_of(repos.local) == before


def test_reconcile_leaves_ordinary_cases_alone(repos: RepoSet) -> None:
    # Behind-only still fast-forwards; the reconcile path must not intercept it.
    push_remote_change(repos, "two\n")

    result = sync_repo(repos.local, reconcile=True)

    assert result.status is Status.PULLED
    assert (repos.local / "file.txt").read_text() == "two\n"
