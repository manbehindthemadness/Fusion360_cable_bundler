"""
Check recorded counter attribution, optional-cost exclusion and partial-result handling.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from devtools.ribbon_analysis.gym import Config, generate
from devtools.ribbon_analysis.performance import for_layout


def _record(directory: Path, name: str, data: Any) -> None:
    """
    Author synthetic records without solver, native or historical artifact dependencies.
    """
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize(
    "native_status", ("built_and_named_fidelity_checks_pass", "built_with_precision_warning")
)
def test_generation_excludes_uv_and_audit_and_clears_for_changed_layout(
    tmp_path: Path, native_status: str
) -> None:
    """
    Keep nested timers distinct and never attribute another case's measurements to a new draft.
    """
    scene = generate(Config(lines=6))
    _record(
        tmp_path,
        "plan.json",
        {
            "targets": asdict(scene.targets),
            "gym": scene.payload(),
            "settings": {"material_uv": True},
        },
    )
    _record(
        tmp_path,
        "numerical-result.json",
        {
            "elapsed_seconds": 2.5,
            "material_uv_seconds": 0.5,
            "cpu_seconds": 2.1,
            "first_pass_seconds": 1.2,
            "smoothing_seconds": 0.6,
        },
    )
    _record(
        tmp_path,
        "native-result.json",
        {
            "generation_seconds": 3.0,
            "material_uv_seconds": 4.0,
            "audit_seconds": 20.0,
            "status": native_status,
        },
    )
    result = for_layout(scene.targets, scene.payload(), tmp_path)
    rows = {r["label"]: r["value"] for r in result["rows"]}
    assert rows["Conductors"] == "6"
    assert rows["Generation total"] == "5.000 s"
    assert rows["Route + checks"] == "2.000 s"
    assert rows["Fidelity audit"] == "20.000 s"
    assert rows["UV storage"] == "4.000 s"
    assert ("precision warning" in result["status"]) == (
        native_status == "built_with_precision_warning"
    )
    changed = generate(Config(seed=42, lines=3))
    stale = for_layout(changed.targets, changed.payload(), tmp_path)
    assert stale["status"] == "No measured run for this layout"
    assert stale["rows"][0]["value"] == "3"
    assert all(r["value"] == "—" for r in stale["rows"][1:])


@pytest.mark.parametrize("bad", [None, False, -1, float("nan"), "0.5"])
def test_partial_or_invalid_measurements_never_become_zero(tmp_path: Path, bad: Any) -> None:
    """
    Retain available numerical measurements while missing/invalid native costs stay unmeasured.
    """
    scene = generate()
    _record(
        tmp_path,
        "plan.json",
        {
            "targets": asdict(scene.targets),
            "gym": scene.payload(),
            "settings": {"material_uv": False},
        },
    )
    _record(
        tmp_path,
        "numerical-result.json",
        {"elapsed_seconds": 1, "material_uv_seconds": 0, "smoothing_seconds": 0},
    )
    _record(tmp_path, "native-result.json", {"generation_seconds": bad, "status": "stopped"})
    result = for_layout(scene.targets, scene.payload(), tmp_path)
    rows = {r["label"]: r["value"] for r in result["rows"]}
    assert rows["Geometry build"] == rows["Generation total"] == "—"
    assert rows["Route + checks"] == "1.000 s"
    assert rows["Smoothing · subset"] == "0.000 s"
    assert rows["UV storage"] == "Off"
    assert "stopped" in result["status"]


def test_incomplete_file_is_unmeasured_then_refreshes_after_completion(tmp_path: Path) -> None:
    """
    Refresh the cache on changed records while tolerating a partial in-flight write.
    """
    scene = generate()
    _record(tmp_path, "plan.json", {"targets": asdict(scene.targets), "gym": scene.payload()})
    native = tmp_path / "native-result.json"
    native.write_text('{"generation_seconds":', encoding="utf-8")
    before = for_layout(scene.targets, scene.payload(), tmp_path)
    assert next(r["value"] for r in before["rows"] if r["label"] == "Geometry build") == "—"
    _record(tmp_path, "native-result.json", {"generation_seconds": 0.25})
    after = for_layout(scene.targets, scene.payload(), tmp_path)
    assert next(r["value"] for r in after["rows"] if r["label"] == "Geometry build") == "0.250 s"


@pytest.mark.parametrize("optimization,expected", ((True, "On"), (False, "Off"), (None, "—")))
def test_optimization_counter_uses_recorded_run_setting(
    tmp_path: Path, optimization: bool | None, expected: str
) -> None:
    """
    Attribute the toggle to its measured job and leave older unspecified jobs unmeasured.
    """
    scene = generate()
    settings = {} if optimization is None else {"first_pass_optimization": optimization}
    _record(
        tmp_path,
        "plan.json",
        {"targets": asdict(scene.targets), "gym": scene.payload(), "settings": settings},
    )
    result = for_layout(scene.targets, scene.payload(), tmp_path)
    assert (
        next(r["value"] for r in result["rows"] if r["label"] == "First-pass optimization")
        == expected
    )
