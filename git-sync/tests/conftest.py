"""Fixtures building real temp git repos: a bare "remote" plus clones."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git in ``cwd``, raising on failure so fixture bugs surface loudly."""
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\n{proc.stderr}")
    return proc


def commit_file(repo: Path, name: str, content: str, message: str = "update") -> None:
    """Write a file, stage it, and commit."""
    (repo / name).write_text(content)
    run_git(repo, "add", name)
    run_git(repo, "commit", "-m", message)


@pytest.fixture(autouse=True)
def _isolate_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shield tests (and the tool's subprocesses) from the user's git config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")


@dataclass
class RepoSet:
    """A bare remote with two clones: ``local`` under test, ``other`` to drive the remote."""

    remote: Path
    local: Path
    other: Path


@pytest.fixture
def repos(tmp_path: Path) -> RepoSet:
    """Bare remote seeded with one commit on main, plus two clones tracking it."""
    seed = tmp_path / "seed"
    seed.mkdir()
    run_git(seed, "init", "--initial-branch=main")
    commit_file(seed, "file.txt", "one\n", "initial commit")

    remote = tmp_path / "remote.git"
    run_git(tmp_path, "clone", "--bare", str(seed), str(remote))

    local = tmp_path / "local"
    run_git(tmp_path, "clone", str(remote), str(local))
    other = tmp_path / "other"
    run_git(tmp_path, "clone", str(remote), str(other))
    return RepoSet(remote=remote, local=local, other=other)


def push_remote_change(repos: RepoSet, content: str = "remote change\n") -> None:
    """Advance the remote's main by one commit via the ``other`` clone."""
    commit_file(repos.other, "file.txt", content, "remote-side commit")
    run_git(repos.other, "push")


def head_of(repo: Path, ref: str = "HEAD") -> str:
    return run_git(repo, "rev-parse", ref).stdout.strip()
