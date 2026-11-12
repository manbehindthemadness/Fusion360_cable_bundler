"""
Keep full source discovery exact and fresh while combining recursive suffix walks.
"""

from __future__ import annotations

from pathlib import Path

from experiments.experiment_ribbon_locked_solver.lock import _analysis_paths


def test_analysis_discovery_keeps_nested_hidden_and_bare_suffix_names(tmp_path: Path) -> None:
    """
    Include every supported full-name suffix and retain malformed matching directories for read failure.
    """
    included = (
        "model.py",
        "assets/view.html",
        "assets/code.js",
        ".hidden.py",
        ".py",
        ".html",
        ".js",
    )
    excluded = ("model.pyc", "model.PY", "view.HTML", "code.js.map", "model.py.txt", "readme")
    for name in included + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source")
    malformed = tmp_path / "directory.py"
    malformed.mkdir()
    assert _analysis_paths(tmp_path) == {tmp_path / name for name in included} | {malformed}


def test_analysis_discovery_observes_additions_and_removals_on_every_scan(tmp_path: Path) -> None:
    """
    No previously discovered path list can hide a later added executable or retain a removed file.
    """
    first = tmp_path / "first.py"
    first.write_text("original")
    assert _analysis_paths(tmp_path) == {first}
    second = tmp_path / "nested" / "second.js"
    second.parent.mkdir()
    second.write_text("new")
    assert _analysis_paths(tmp_path) == {first, second}
    first.unlink()
    assert _analysis_paths(tmp_path) == {second}


def test_absent_analysis_tree_preserves_empty_discovery(tmp_path: Path) -> None:
    """
    Preserve ordinary glob behavior when an optional analysis tree does not exist.
    """
    assert _analysis_paths(tmp_path / "absent") == set()
