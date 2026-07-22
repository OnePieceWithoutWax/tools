"""folder clean-empty: which directories go, and which are left alone."""

from __future__ import annotations

from pathlib import Path

from fdt.empty import JUNK_NAMES, clean_empty
from fdt.results import Status
from treebuild import make_tree


def test_deletes_empty_child(tree: Path) -> None:
    make_tree(tree, {"empty": None, "full/file.txt": "x"})

    results = clean_empty(tree)

    assert [r.path.name for r in results] == ["empty"]
    assert results[0].status is Status.DELETED
    assert not (tree / "empty").exists()
    assert (tree / "full").exists()


def test_non_recursive_leaves_nested_empties(tree: Path) -> None:
    make_tree(tree, {"outer/inner": None})

    results = clean_empty(tree)

    assert results == []
    assert (tree / "outer" / "inner").exists()


def test_recursive_collapses_whole_chain(tree: Path) -> None:
    make_tree(tree, {"a/b/c/d": None})

    results = clean_empty(tree, recursive=True)

    # Children before parents: the deepest folder is removed first.
    assert [r.path.name for r in results] == ["d", "c", "b", "a"]
    assert not (tree / "a").exists()


def test_recursive_stops_at_a_folder_holding_a_file(tree: Path) -> None:
    make_tree(tree, {"keep/deep/empty": None, "keep/notes.txt": "hello"})

    clean_empty(tree, recursive=True)

    assert (tree / "keep").exists()
    assert (tree / "keep" / "notes.txt").exists()
    assert not (tree / "keep" / "deep").exists()


def test_root_is_never_deleted(tree: Path) -> None:
    make_tree(tree, {"gone": None})

    clean_empty(tree, recursive=True)

    assert tree.exists()


def test_dry_run_changes_nothing(tree: Path) -> None:
    make_tree(tree, {"a/b": None})

    results = clean_empty(tree, recursive=True, dry_run=True)

    assert [r.status for r in results] == [Status.WOULD_DELETE] * 2
    assert (tree / "a" / "b").exists()


def test_skipped_directories_are_left_alone(tree: Path) -> None:
    make_tree(tree, {"project/.git": None})

    clean_empty(tree, recursive=True)

    assert (tree / "project" / ".git").exists()


def test_junk_only_folder_is_empty_when_ignored(tree: Path) -> None:
    make_tree(tree, {"stale/Thumbs.db": "junk"})

    results = clean_empty(tree, ignore=JUNK_NAMES)

    assert results[0].removed_files == ["Thumbs.db"]
    assert not (tree / "stale").exists()


def test_junk_only_folder_is_kept_by_default(tree: Path) -> None:
    make_tree(tree, {"stale/Thumbs.db": "junk"})

    assert clean_empty(tree) == []
    assert (tree / "stale" / "Thumbs.db").exists()


def test_dry_run_does_not_delete_ignored_files(tree: Path) -> None:
    make_tree(tree, {"stale/desktop.ini": "junk"})

    clean_empty(tree, ignore=JUNK_NAMES, dry_run=True)

    assert (tree / "stale" / "desktop.ini").exists()
