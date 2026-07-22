"""folder size, file find-large, file find-dupes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fdt.dupes import find_dupes
from fdt.report import human_bytes, parse_size
from fdt.sizes import folder_sizes, largest_files
from treebuild import make_tree


def test_folder_size_totals_nested_content(tree: Path) -> None:
    make_tree(tree, {"big/nested/a.txt": "x" * 100, "small/b.txt": "y" * 10})

    rows, total, files = folder_sizes(tree, depth=1)

    assert [r.path.name for r in rows] == ["big", "small"]  # largest first
    assert rows[0].size == 100
    assert (total, files) == (110, 2)


def test_folder_size_depth_lists_deeper_rows(tree: Path) -> None:
    make_tree(tree, {"outer/inner/a.txt": "x" * 5})

    shallow, _, _ = folder_sizes(tree, depth=1)
    deep, _, _ = folder_sizes(tree, depth=2)

    assert [r.path.name for r in shallow] == ["outer"]
    assert {r.path.name for r in deep} == {"outer", "inner"}


def test_folder_size_ignores_skipped_dirs(tree: Path) -> None:
    make_tree(tree, {"pkg/__pycache__/x.pyc": "x" * 50, "pkg/x.py": "y"})

    _, total, files = folder_sizes(tree)

    assert (total, files) == (1, 1)


def test_largest_files_orders_and_limits(tree: Path) -> None:
    make_tree(tree, {"a.txt": "x" * 30, "sub/b.txt": "y" * 20, "c.txt": "z" * 10})

    found = largest_files(tree, top=2)

    assert [f.path.name for f in found] == ["a.txt", "b.txt"]


def test_largest_files_honours_min_size(tree: Path) -> None:
    make_tree(tree, {"a.txt": "x" * 30, "b.txt": "y"})

    found = largest_files(tree, min_size=10)

    assert [f.path.name for f in found] == ["a.txt"]


def test_find_dupes_groups_identical_content(tree: Path) -> None:
    make_tree(tree, {"one.txt": "same", "sub/two.txt": "same", "other.txt": "different"})

    groups = find_dupes(tree)

    assert len(groups) == 1
    assert {p.name for p in groups[0].paths} == {"one.txt", "two.txt"}
    assert groups[0].wasted == 4


def test_find_dupes_ignores_same_size_different_content(tree: Path) -> None:
    make_tree(tree, {"a.txt": "abcd", "b.txt": "wxyz"})

    assert find_dupes(tree) == []


def test_find_dupes_skips_empty_files_by_default(tree: Path) -> None:
    make_tree(tree, {"a.txt": "", "b.txt": ""})

    assert find_dupes(tree) == []


def test_find_dupes_orders_by_recoverable_space(tree: Path) -> None:
    make_tree(
        tree,
        {
            "small1.txt": "ab",
            "small2.txt": "ab",
            "big1.txt": "z" * 500,
            "big2.txt": "z" * 500,
        },
    )

    groups = find_dupes(tree)

    assert [g.size for g in groups] == [500, 2]


@pytest.mark.parametrize(
    ("text", "expected"),
    [("500", 500), ("10MB", 10 * 1024**2), ("1.5G", int(1.5 * 1024**3)), (" 2 kb ", 2048)],
)
def test_parse_size(text: str, expected: int) -> None:
    assert parse_size(text) == expected


def test_parse_size_rejects_nonsense() -> None:
    with pytest.raises(ValueError, match="not a size"):
        parse_size("huge")


def test_human_bytes() -> None:
    assert human_bytes(512) == "512 B"
    assert human_bytes(1536) == "1.5 KB"
    assert human_bytes(3 * 1024**3) == "3.0 GB"
