"""The pull/push/fetch flag combinations behind pull-all, push-all, fetch-all, status-all."""

from __future__ import annotations

from conftest import RepoSet, commit_file, head_of, push_remote_change
from git_tools.repo import Status, sync_repo


def test_pull_all_does_not_push(repos: RepoSet) -> None:
    commit_file(repos.local, "file.txt", "local change\n")
    remote_before = head_of(repos.remote, "main")

    result = sync_repo(repos.local, push=False)

    assert result.status is Status.AHEAD
    assert (result.behind, result.ahead) == (0, 1)
    assert head_of(repos.remote, "main") == remote_before


def test_pull_all_still_pulls(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")

    result = sync_repo(repos.local, push=False)

    assert result.status is Status.PULLED
    assert (repos.local / "file.txt").read_text() == "two\n"


def test_push_all_does_not_pull(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")
    before = head_of(repos.local)

    result = sync_repo(repos.local, pull=False)

    assert result.status is Status.BEHIND
    assert (result.behind, result.ahead) == (1, 0)
    assert head_of(repos.local) == before
    assert (repos.local / "file.txt").read_text() == "one\n"


def test_push_all_still_pushes(repos: RepoSet) -> None:
    commit_file(repos.local, "file.txt", "local change\n")

    result = sync_repo(repos.local, pull=False)

    assert result.status is Status.PUSHED
    assert head_of(repos.remote, "main") == head_of(repos.local)


def test_fetch_all_reports_without_changing_anything(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")
    before = head_of(repos.local)

    result = sync_repo(repos.local, pull=False, push=False)

    assert result.status is Status.BEHIND
    assert (result.behind, result.ahead) == (1, 0)
    assert head_of(repos.local) == before


def test_status_all_is_offline_and_therefore_stale(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")

    # No fetch, so the remote-tracking ref still points where it did at clone
    # time and the new upstream commit is invisible.
    offline = sync_repo(repos.local, pull=False, push=False, fetch=False)
    assert offline.status is Status.UP_TO_DATE
    assert (offline.behind, offline.ahead) == (0, 0)

    # Fetching is what makes the same repo report BEHIND.
    online = sync_repo(repos.local, pull=False, push=False)
    assert online.status is Status.BEHIND
    assert online.behind == 1


def test_status_all_sees_local_commits_without_network(repos: RepoSet) -> None:
    commit_file(repos.local, "file.txt", "local change\n")

    result = sync_repo(repos.local, pull=False, push=False, fetch=False)

    assert result.status is Status.AHEAD
    assert (result.behind, result.ahead) == (0, 1)


def test_dirty_repo_still_reports_counts(repos: RepoSet) -> None:
    push_remote_change(repos, "two\n")
    (repos.local / "file.txt").write_text("uncommitted edit\n")

    result = sync_repo(repos.local)

    assert result.status is Status.DIRTY
    assert (result.behind, result.ahead) == (1, 0)
    assert (repos.local / "file.txt").read_text() == "uncommitted edit\n"
