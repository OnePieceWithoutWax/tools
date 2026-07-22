"""folder clean-jupyter: removing named directories whole."""

from __future__ import annotations

from pathlib import Path

from fdt.purge import JUPYTER_CHECKPOINTS, purge_dirs
from fdt.results import Status
from treebuild import make_tree

CHECKPOINTS = frozenset({JUPYTER_CHECKPOINTS})


def test_removes_checkpoints_with_their_contents(tree: Path) -> None:
    make_tree(tree, {f"{JUPYTER_CHECKPOINTS}/analysis-checkpoint.ipynb": "{}" * 10})

    results = purge_dirs(tree, CHECKPOINTS)

    assert results[0].status is Status.DELETED
    assert results[0].files == 1
    assert results[0].size == 20
    assert not (tree / JUPYTER_CHECKPOINTS).exists()


def test_non_recursive_only_looks_in_root(tree: Path) -> None:
    make_tree(tree, {f"notebooks/{JUPYTER_CHECKPOINTS}/x-checkpoint.ipynb": "{}"})

    assert purge_dirs(tree, CHECKPOINTS) == []
    assert (tree / "notebooks" / JUPYTER_CHECKPOINTS).exists()


def test_recursive_sweeps_the_whole_tree(tree: Path) -> None:
    make_tree(
        tree,
        {
            f"{JUPYTER_CHECKPOINTS}/a-checkpoint.ipynb": "{}",
            f"a/{JUPYTER_CHECKPOINTS}/b-checkpoint.ipynb": "{}",
            f"a/deep/nested/{JUPYTER_CHECKPOINTS}/c-checkpoint.ipynb": "{}",
            "a/keep.ipynb": "{}",
        },
    )

    results = purge_dirs(tree, CHECKPOINTS, recursive=True)

    assert len(results) == 3
    assert not list(tree.rglob(JUPYTER_CHECKPOINTS))
    assert (tree / "a" / "keep.ipynb").exists()


def test_dry_run_deletes_nothing_but_still_measures(tree: Path) -> None:
    make_tree(tree, {f"{JUPYTER_CHECKPOINTS}/a-checkpoint.ipynb": "x" * 40})

    results = purge_dirs(tree, CHECKPOINTS, dry_run=True)

    assert results[0].status is Status.WOULD_DELETE
    assert results[0].size == 40
    assert (tree / JUPYTER_CHECKPOINTS).exists()


def test_skipped_dirs_are_not_searched(tree: Path) -> None:
    make_tree(tree, {f".venv/lib/{JUPYTER_CHECKPOINTS}/x.ipynb": "{}"})

    assert purge_dirs(tree, CHECKPOINTS, recursive=True) == []
    assert (tree / ".venv" / "lib" / JUPYTER_CHECKPOINTS).exists()
