"""clean-all: pruning stale remote refs and deleting merged local branches."""

from __future__ import annotations

from conftest import RepoSet, commit_file, run_git
from git_tools.clean import CleanStatus, clean_repo


def _branches(repo) -> set[str]:  # noqa: ANN001 - Path, kept short for a test helper
    out = run_git(repo, "branch", "--format=%(refname:short)").stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def _set_origin_head(repo) -> None:  # noqa: ANN001
    """Clones of a local bare repo do not always get origin/HEAD; set it explicitly."""
    run_git(repo, "remote", "set-head", "origin", "main")


def test_deletes_merged_branch(repos: RepoSet) -> None:
    _set_origin_head(repos.local)
    run_git(repos.local, "branch", "merged-work")  # points at main, so trivially merged

    result = clean_repo(repos.local)

    assert result.status is CleanStatus.CLEANED
    assert result.deleted == ["merged-work"]
    assert "merged-work" not in _branches(repos.local)


def test_keeps_unmerged_branch(repos: RepoSet) -> None:
    _set_origin_head(repos.local)
    run_git(repos.local, "checkout", "-b", "unmerged")
    commit_file(repos.local, "wip.txt", "not pushed anywhere\n")
    run_git(repos.local, "checkout", "main")

    result = clean_repo(repos.local)

    assert result.deleted == []
    assert "unmerged" in _branches(repos.local)


def test_never_deletes_current_or_default_branch(repos: RepoSet) -> None:
    _set_origin_head(repos.local)
    run_git(repos.local, "checkout", "-b", "sitting-here")

    result = clean_repo(repos.local)

    assert result.deleted == []
    assert {"main", "sitting-here"} <= _branches(repos.local)


def test_dry_run_deletes_nothing(repos: RepoSet) -> None:
    _set_origin_head(repos.local)
    run_git(repos.local, "branch", "merged-work")

    result = clean_repo(repos.local, dry_run=True)

    assert result.deleted == ["merged-work"]
    assert "merged-work" in _branches(repos.local)


def test_nothing_to_do(repos: RepoSet) -> None:
    _set_origin_head(repos.local)

    result = clean_repo(repos.local)

    assert result.status is CleanStatus.NOTHING
    assert result.deleted == []


def test_unreachable_remote_still_cleans_local_branches(repos: RepoSet) -> None:
    _set_origin_head(repos.local)
    run_git(repos.local, "branch", "merged-work")
    # Point origin at nothing so the prune step fails, leaving the local refs intact.
    run_git(repos.local, "remote", "set-url", "origin", str(repos.remote.parent / "gone.git"))

    result = clean_repo(repos.local)

    assert result.status is CleanStatus.ERROR
    assert "prune failed" in result.detail
    # The local half of the job still ran.
    assert result.deleted == ["merged-work"]
    assert "merged-work" not in _branches(repos.local)


def test_no_prune_skips_the_network(repos: RepoSet) -> None:
    _set_origin_head(repos.local)
    run_git(repos.local, "branch", "merged-work")
    run_git(repos.local, "remote", "set-url", "origin", str(repos.remote.parent / "gone.git"))

    result = clean_repo(repos.local, prune=False)

    assert result.status is CleanStatus.CLEANED
    assert result.deleted == ["merged-work"]


def test_no_origin_head_is_reported_not_guessed(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "remove", "origin")

    result = clean_repo(repos.local)

    assert result.status is CleanStatus.NO_REMOTE
    assert result.deleted == []
