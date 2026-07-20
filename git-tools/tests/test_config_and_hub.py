"""config-all reads, and the hub audit / gh-parsing logic (no network)."""

from __future__ import annotations

from pathlib import Path

from conftest import RepoSet, run_git
from git_tools.gitconfig import UNSET, ConfigStatus, read_config
from git_tools.github import AuditStatus, GhRepo, audit, origin_slug


def _repo(name: str, **kwargs: object) -> GhRepo:
    defaults = {"name": name, "nameWithOwner": f"me/{name}"}
    return GhRepo.model_validate({**defaults, **kwargs})


# --- config-all -------------------------------------------------------------


def test_reads_a_set_value(repos: RepoSet) -> None:
    run_git(repos.local, "config", "user.email", "me@personal.com")

    result = read_config(repos.local, "user.email")

    assert result.status is ConfigStatus.OK
    assert result.value == "me@personal.com"


def test_unset_value(repos: RepoSet) -> None:
    result = read_config(repos.local, "user.nonexistent")

    assert result.status is ConfigStatus.UNSET
    assert result.value == UNSET


def test_expect_matches_and_mismatches(repos: RepoSet) -> None:
    run_git(repos.local, "config", "user.email", "me@work.example.com")

    assert read_config(repos.local, "user.email", expect="*@work.example.com").status is (
        ConfigStatus.OK
    )

    bad = read_config(repos.local, "user.email", expect="*@personal.com")
    assert bad.status is ConfigStatus.MISMATCH
    assert "*@personal.com" in bad.detail


def test_expect_is_case_insensitive(repos: RepoSet) -> None:
    run_git(repos.local, "config", "user.email", "Me@Work.Example.com")

    result = read_config(repos.local, "user.email", expect="*@work.example.com")

    assert result.status is ConfigStatus.OK


# --- origin slug parsing ----------------------------------------------------


def test_origin_slug_https(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "https://github.com/me/thing.git")
    assert origin_slug(repos.local) == "me/thing"


def test_origin_slug_ssh(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "git@github.com:me/thing.git")
    assert origin_slug(repos.local) == "me/thing"


def test_origin_slug_without_suffix(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "https://github.com/me/thing")
    assert origin_slug(repos.local) == "me/thing"


def test_origin_slug_non_github(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "https://gitlab.com/me/thing.git")
    assert origin_slug(repos.local) is None


def test_origin_slug_no_remote(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "remove", "origin")
    assert origin_slug(repos.local) is None


# --- hub audit --------------------------------------------------------------


def test_audit_matches_cloned_and_flags_missing(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "https://github.com/me/thing.git")
    remote = [_repo("thing"), _repo("never-cloned")]

    rows = {r.name: r for r in audit([repos.local], remote)}

    assert rows["thing"].status is AuditStatus.CLONED
    assert rows["never-cloned"].status is AuditStatus.MISSING


def test_audit_flags_archived_checkout(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "https://github.com/me/thing.git")

    rows = audit([repos.local], [_repo("thing", isArchived=True)])

    assert rows[0].status is AuditStatus.ARCHIVED


def test_audit_flags_local_only_and_no_remote(repos: RepoSet, tmp_path: Path) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "https://github.com/me/elsewhere.git")
    orphan = tmp_path / "orphan"
    orphan.mkdir()
    run_git(orphan, "init")

    rows = {r.name: r for r in audit([repos.local, orphan], [_repo("thing")])}

    assert rows["local"].status is AuditStatus.LOCAL_ONLY
    assert rows["orphan"].status is AuditStatus.NO_REMOTE
    assert rows["thing"].status is AuditStatus.MISSING


def test_audit_slug_comparison_ignores_case(repos: RepoSet) -> None:
    run_git(repos.local, "remote", "set-url", "origin", "https://github.com/Me/Thing.git")

    rows = audit([repos.local], [_repo("thing")])

    assert [r.status for r in rows] == [AuditStatus.CLONED]


def test_gh_repo_parses_default_branch(repos: RepoSet) -> None:
    parsed = _repo("thing", defaultBranchRef={"name": "trunk"}, isPrivate=True)

    assert parsed.default_branch == "trunk"
    assert parsed.is_private is True
    # An empty repo has no default branch ref at all.
    assert _repo("empty").default_branch == ""
