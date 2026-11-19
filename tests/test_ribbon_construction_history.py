"""
Verify frozen replay, honest provenance, feature correspondence and optional observer neutrality.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cable_bundler.routing.ribbon import RibbonFrame
from cable_bundler.routing.ribbon_shape import RibbonShape
from devtools.ribbon_analysis.construction import records
from devtools.ribbon_analysis.construction.journal import Journal, TraceLimit, load
from devtools.ribbon_analysis.construction.sampled import capture_shape
from devtools.ribbon_analysis.construction.view import export
from experiments.experiment_ribbon_constrained_construction.clearance_motion import ClearanceMotion
from experiments.experiment_ribbon_constrained_construction.clearance_planes import select
from experiments.experiment_ribbon_constrained_construction.waypoint_solve import Work, run
from experiments.experiment_ribbon_construction_diagnostic.adapter import (
    EventBridge,
    assembly,
    inputs,
    item,
)
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_waypoint_kinematics import checkpoint, objective


def journal(tmp_path: Path) -> Journal:
    """
    Allocate one exclusive small diagnostic stream per analytical test.
    """
    return Journal(tmp_path / "trace.jsonl", "analytical trace", {"solver": "test only"})


def test_frozen_geometry_lineage_and_exclusive_prefix(tmp_path: Path) -> None:
    """
    Later mutable edits cannot repaint prior evidence; unknown ancestry and overwrite fail.
    """
    log = journal(tmp_path)
    log.define("a", "End A", "target", (), "test:input")
    with pytest.raises(ValueError, match="parents"):
        log.define("b", "Fold", "fold", ("unknown",), "test:fold")
    scene = [item("a", [[[0, 0, 0], [1, 0, 0]]])]
    log.emit("input", "initial", "reference", "observed", scene)
    scene[0]["paths"][0][1][0] = 999
    log.close()
    assert load(log.path)["steps"][0]["scene"][0]["paths"][0][1][0] == 1
    with pytest.raises(FileExistsError):
        journal(tmp_path)


def test_trace_limit_retains_prior_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A resource limit never erases a flushed prefix or silently discards an observation.
    """
    log = journal(tmp_path)
    log.emit("input", "initial", "reference", "observed", [])
    monkeypatch.setattr(records, "MAX_STEPS", 1)
    with pytest.raises(TraceLimit):
        log.emit("output", "over limit", "unresolved", "observed", [])
    log.close()
    assert len(load(log.path)["steps"]) == 1


@pytest.mark.parametrize("damage", ("truncated", "reordered", "nonfinite", "unknown_feature"))
def test_invalid_external_history_is_not_replayed(tmp_path: Path, damage: str) -> None:
    """
    Malformed or incomplete records cannot become trusted display stages.
    """
    log = journal(tmp_path)
    log.define("a", "A", "target", (), "test:input")
    log.emit("input", "initial", "reference", "observed", [item("a", [[[0, 0, 0], [1, 0, 0]]])])
    log.close()
    rows = log.path.read_text().splitlines()
    step = json.loads(rows[-1])
    if damage == "truncated":
        rows[-1] = rows[-1][:-5]
    elif damage == "reordered":
        step["index"] = 5
    elif damage == "nonfinite":
        step["scene"][0]["paths"][0][0][0] = float("inf")
    else:
        step["scene"][0]["feature"] = "missing"
    if damage != "truncated":
        rows[-1] = json.dumps(step)
    log.path.write_text("\n".join(rows) + ("" if damage == "truncated" else "\n"))
    with pytest.raises(ValueError):
        load(log.path)


def test_material_assembly_reproduces_local_and_world_origins_honestly(tmp_path: Path) -> None:
    """
    Saved primitives retain original poses and material order without pretending to be solver events.
    """
    route = objective().model.original
    log = journal(tmp_path)
    context = inputs(log, route)
    assembly(log, route, "chain", context)
    log.close()
    packet = load(log.path)
    assert {s["phase"] for s in packet["steps"]} >= {
        "input",
        "preplot",
        "primitive",
        "bend",
        "placement",
        "output",
    }
    primitive = next(s for s in packet["steps"] if s["phase"] == "bend")
    assert primitive["basis"] == "reconstructed"
    assert primitive["scene"][0]["space"] == "local"
    identity = primitive["scene"][0]["feature"]
    final = packet["steps"][-1]
    placed = next(o for o in final["scene"] if o["feature"] == identity)
    actual = route.pieces[1].surface(0, -route.half_width_mm)[0]
    assert placed["paths"][0][0] == [actual.x, actual.y, actual.z]
    assert packet["features"][identity]["parents"] == ["End A"]
    assert (
        placed["details"]["entry_frame"]["origin"] == snapshot(route)["pieces"][1]["pose"]["origin"]
    )
    assert all(
        s["basis"] == "reconstructed"
        for s in packet["steps"]
        if s["phase"] in ("primitive", "bend", "placement")
    )
    assert final["status"] == "unresolved"


def test_status_only_events_never_invent_current_geometry(tmp_path: Path) -> None:
    """
    Existing solver callbacks preserve missing history and original downstream event order.
    """
    route = objective().model.original
    log = journal(tmp_path)
    events: list[dict[str, Any]] = []
    bridge = EventBridge(log, inputs(log, route), downstream=events.append, stable_chain="fixed")
    bridge({"status": "closed_before_certification", "route": snapshot(route)})
    bridge({"status": "closure_failed"})
    log.close()
    packet = load(log.path)
    assert len(events) == 2
    assert packet["steps"][-1]["details"]["geometry_available"] is False
    assert "context" in packet["steps"][-1]["details"]["geometry_notice"]
    assert packet["steps"][-1]["status"] == "rejected"


def test_application_shape_adapter_reports_unrecorded_bend_history(tmp_path: Path) -> None:
    """
    A final application result is inspectable without fabricating its internal construction decisions.
    """
    route = objective().model.original
    poses = (route.pieces[0].pose, route.pieces[-1].end_pose())
    frames = tuple(RibbonFrame(p.origin, p.tangent, p.width, p._normal) for p in poses)
    lanes = (tuple(p.origin for p in poses),)
    shape = RibbonShape(frames, lanes, (route.material_length_mm,), 0.0, False, 1.0)
    log = journal(tmp_path)
    capture_shape(log, shape, "existing solver")
    log.close()
    packet = load(log.path)
    assert packet["steps"][1]["basis"] == "unavailable"
    assert packet["steps"][1]["scene"] == []
    assert packet["steps"][-1]["scene"][0]["paths"][0][0] == [
        poses[0].origin.x,
        poses[0].origin.y,
        poses[0].origin.z,
    ]


def test_html_export_escapes_recorded_script_markup(tmp_path: Path) -> None:
    """
    Labels remain data, even when they contain script-closing syntax.
    """
    log = journal(tmp_path)
    log.emit("input", "</script><script>bad()</script>", "reference", "observed", [])
    log.close()
    page = export(log.path, tmp_path / "viewer.html").read_text()
    assert "<script>bad()" not in page
    assert "\\u003c/script\\u003e" in page
    assert "/*CONSTRUCTION_" not in page


def test_optional_observation_preserves_joint_results_and_work() -> None:
    """
    Capturing actual correction state and raw proposals changes neither coordinates nor work counts.
    """
    problem = objective()
    hardware = Hardware.create(
        problem.model.original.targets, Dimensions.scaled(problem.model.original.targets)
    )
    planes = select(problem.model, hardware, problem.model.initial, checkpoint).planes
    records_seen: list[dict[str, Any]] = []
    plain, observed = (
        ClearanceMotion(problem, hardware, lambda event: None),
        ClearanceMotion(problem, hardware, lambda event: None, trace=records_seen.append),
    )
    plain.planes = observed.planes = planes
    values = list(problem.model.initial)
    values[0] += 0.001
    first = plain.restore(tuple(values), checkpoint, 2, checkpoint)
    second = observed.restore(tuple(values), checkpoint, 2, checkpoint)
    assert first == second
    assert records_seen and records_seen[0]["status"] == "correction_state"
    assert "clearance_rows" in records_seen[0] and "cap_position_components_mm" in records_seen[0]
    baseline, traced = Work(), Work()
    run(problem, baseline, lambda route: False, checkpoint, lambda event: None)
    trace_events: list[dict[str, Any]] = []
    run(
        problem,
        traced,
        lambda route: False,
        checkpoint,
        lambda event: None,
        trace=trace_events.append,
    )
    assert baseline == traced
    assert trace_events[0]["status"] == "raw_proposal"
    assert "route" in trace_events[0]
