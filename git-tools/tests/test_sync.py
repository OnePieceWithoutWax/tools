"""End-to-end sync scenarios against real git repos (no mocking of git)."""

from __future__ import annotations

from pathlib import Path

from conftest import RepoSet, commit_file, head_of, push_remote_change, run_git
from git_tools.repo import Status, sync_repo
from git_tools.scanner import find_repos


def test_clean_behind_pulls(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")

    result = sync_repo(repos.local)

    assert result.status is Status.PULLED
    assert (result.behind, result.ahead) == (1, 0)
    assert (repos.local / "file.txt").read_text() == "two\n"
    assert head_of(repos.local) == head_of(repos.remote, "main")


def test_clean_ahead_pushes(repos: RepoSet) -> None:
    commit_file(repos.local, "file.txt", "local change\n")

    result = sync_repo(repos.local)

    assert result.status is Status.PUSHED
    assert (result.behind, result.ahead) == (0, 1)
    assert head_of(repos.remote, "main") == head_of(repos.local)


def test_dirty_skipped(repos: RepoSet) -> None:
    push_remote_change(repos)
    (repos.local / "file.txt").write_text("uncommitted edit\n")
    before = head_of(repos.local)

    result = sync_repo(repos.local)

    assert result.status is Status.DIRTY
    assert head_of(repos.local) == before
    assert (repos.local / "file.txt").read_text() == "uncommitted edit\n"


def test_untracked_files_do_not_block_sync(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")
    (repos.local / "scratch.log").write_text("build noise\n")

    result = sync_repo(repos.local)

    assert result.status is Status.PULLED
    assert (repos.local / "file.txt").read_text() == "two\n"
    assert (repos.local / "scratch.log").read_text() == "build noise\n"


def test_untracked_collision_aborts_pull(repos: RepoSet) -> None:
    commit_file(repos.other, "new.txt", "from remote\n", "add new.txt")
    run_git(repos.other, "push")
    (repos.local / "new.txt").write_text("mine\n")
    before = head_of(repos.local)

    result = sync_repo(repos.local)

    assert result.status is Status.COLLISION
    assert "new.txt" in result.detail
    # git aborts before touching anything, so no revert is needed.
    assert head_of(repos.local) == before
    assert (repos.local / "new.txt").read_text() == "mine\n"


def test_diverged_skipped(repos: RepoSet) -> None:
    push_remote_change(repos)
    commit_file(repos.local, "other.txt", "local only\n")
    local_before = head_of(repos.local)
    remote_before = head_of(repos.remote, "main")

    result = sync_repo(repos.local)

    assert result.status is Status.DIVERGED
    assert (result.behind, result.ahead) == (1, 1)
    assert head_of(repos.local) == local_before
    assert head_of(repos.remote, "main") == remote_before


def test_no_upstream_skipped(repos: RepoSet) -> None:
    run_git(repos.local, "checkout", "-b", "feature")

    result = sync_repo(repos.local)

    assert result.status is Status.NO_UPSTREAM
    assert result.branch == "feature"


def test_detached_head_skipped(repos: RepoSet) -> None:
    run_git(repos.local, "checkout", "--detach")

    result = sync_repo(repos.local)

    assert result.status is Status.NO_UPSTREAM


def test_non_ff_pull_fails_gracefully(repos: RepoSet) -> None:
    # skip-worktree hides a local edit from `status --porcelain`, so the repo
    # looks clean but the fast-forward would clobber the file and git refuses.
    push_remote_change(repos)
    (repos.local / "file.txt").write_text("hidden local edit\n")
    run_git(repos.local, "update-index", "--skip-worktree", "file.txt")
    before = head_of(repos.local)

    result = sync_repo(repos.local)

    assert result.status is Status.PULL_FAILED
    assert (result.behind, result.ahead) == (1, 0)
    assert head_of(repos.local) == before
    assert (repos.local / "file.txt").read_text() == "hidden local edit\n"


def test_up_to_date(repos: RepoSet) -> None:
    result = sync_repo(repos.local)

    assert result.status is Status.UP_TO_DATE
    assert (result.behind, result.ahead) == (0, 0)


def test_dry_run_makes_no_changes(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")
    before = head_of(repos.local)

    result = sync_repo(repos.local, dry_run=True)

    assert result.status is Status.PULLED
    assert "dry-run" in result.detail
    assert head_of(repos.local) == before
    assert (repos.local / "file.txt").read_text() == "one\n"


def test_scanner_one_level_and_recursive(repos: RepoSet, tmp_path: Path) -> None:
    root = tmp_path / "scan-root"
    nested = root / "group" / "deep-repo"
    nested.mkdir(parents=True)
    run_git(nested, "init")
    plain = root / "not-a-repo"
    plain.mkdir()
    top = root / "top-repo"
    top.mkdir()
    run_git(top, "init")

    one_level = find_repos(root)
    assert [p.name for p in one_level] == ["top-repo"]

    recursive = find_repos(root, recursive=True)
    assert {p.name for p in recursive} == {"top-repo", "deep-repo"}
