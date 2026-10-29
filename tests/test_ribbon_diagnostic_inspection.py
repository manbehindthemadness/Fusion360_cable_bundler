"""
Check recoverable search evidence, actual forward frames and scoped diagnostic claims.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    canonical,
    parse_snapshot,
    snapshot_payload,
    targets_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.capture import (
    CaptureLimits,
    SearchRecorder,
    load_history_path,
    read_history,
)
from devtools.ribbon_analysis.inspection.geometry import freeze_curve, freeze_path, local_frame
from devtools.ribbon_analysis.inspection.measurements import observations
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_diagnostic_viewer.fixture import SpatialSBend, Tightness
from experiments.experiment_ribbon_diagnostic_viewer.runner import recover
from experiments.experiment_ribbon_route_discovery import box_fit, broad_chart
from experiments.experiment_ribbon_route_discovery.families import Seed


def _manifest(path: Path) -> tuple[Path, SpatialSBend]:
    """
    Write a reference and an explicit missing solver without running a search.
    """
    fixture = SpatialSBend()
    snapshot = freeze_curve("reference", fixture, 1.5, intervals=32)
    methods = [
        {
            "id": "reference",
            "label": "Reference",
            "status": "reference",
            "detail": "Authored, not solved.",
            "source": "fixture",
            "snapshot": snapshot_payload(snapshot),
            "rules": [asdict(rule) for rule in observations(snapshot, fixture.targets(), 4.5)],
        },
        {
            "id": "ordinary",
            "label": "Ordinary",
            "status": "not_run",
            "detail": "No result.",
            "source": "solver",
            "rules": [],
        },
    ]
    manifest = path / "reference.json"
    write_document(
        manifest,
        {"schema": SCHEMA, "targets": targets_payload(fixture.targets()), "solvers": methods},
    )
    return manifest, fixture


def test_spatial_s_attains_declared_limit_and_turns_laterally_during_both_lobes() -> None:
    """
    Check the independent fixture definition, scale and signed pitch reversal.
    """
    curve = SpatialSBend()
    assert curve.tangent(0) == Vector3(0, 0, 1)
    assert magnitude(difference(curve.tangent(1), Vector3(1, 0, 0))) < 1e-15
    assert curve.curvature(0) == pytest.approx(1 / 4.5)
    assert curve.curvature(1) == pytest.approx(1 / 4.5)
    assert max(curve.curvature(i / 128) for i in range(129)) <= 1 / 4.5 + 1e-14
    for u in (0.1, 0.25, 0.5, 0.75, 0.9):
        frame = curve.frame(u)
        assert dot(cross(frame.x, frame.y), frame.z) == pytest.approx(1)
        assert magnitude(difference(frame.z, curve.tangent(u))) < 1e-15
        before, after = curve.tangent(u - 1e-5), curve.tangent(u + 1e-5)
        assert math.atan2(after.x, after.z) > math.atan2(before.x, before.z)
        if u < 0.5:
            assert after.y > before.y
        elif u > 0.5:
            assert after.y < before.y
    doubled = SpatialSBend(Tightness(diameter_mm=3))
    assert doubled.length_mm == pytest.approx(2 * curve.length_mm)
    assert (
        magnitude(difference(doubled.jet(1)[0], curve.jet(1)[0].translated(curve.jet(1)[0], 1)))
        < 1e-12
    )
    assert doubled.curvature(0.4) == pytest.approx(curve.curvature(0.4) / 2)


def test_snapshot_roundtrip_retains_sections_frames_and_rejects_tampering() -> None:
    """
    Preserve a complete immutable geometry record and verify its content digest.
    """
    snapshot = freeze_curve("S", SpatialSBend(), 1.5, intervals=32)
    payload = json.loads(canonical(snapshot_payload(snapshot)))
    assert parse_snapshot(payload) == snapshot
    for section in snapshot.sections:
        assert all(
            dot(difference(point, section.frame.origin), section.frame.z)
            == pytest.approx(0, abs=1e-12)
            for point in section.outline
        )
        assert all(
            magnitude(difference(point, section.frame.origin)) == pytest.approx(0.75)
            for point in section.outline
        )
    payload["geometry"]["sections"][0]["frame"]["z"]["x"] = 1
    with pytest.raises(ValueError, match="fingerprint"):
        parse_snapshot(payload)
    with pytest.raises(ValueError, match="orthonormal"):
        replace(snapshot.sections[0].frame, z=Vector3(1, 0, 1))
    with pytest.raises(ValueError):
        local_frame(Vector3(0, 0, 0), Vector3(0, 0, 1), Vector3(0, 0, 2))
    with pytest.raises(ValueError):
        malformed: dict[str, Any] = {"lines": 1.5}
        replace(snapshot, **malformed)


def test_capture_keeps_finite_difference_probes_trials_and_unchanged_result(tmp_path: Path) -> None:
    """
    Compare fitting with and without recording, then replay every evaluated path.
    """
    case = SpatialSBend().targets()
    seed = Seed(0, (0.0,) * 9 + (1.2,), 0, ())
    work = box_fit.FitWork(1, 0, 14)
    original, metrics = box_fit.refine(case, seed, lambda: None, work)
    history = tmp_path / "ordinary.jsonl"
    recorder = SearchRecorder(history, "ordinary", lambda: None)
    with recorder.recording():
        recorded, result = box_fit.refine(case, seed, lambda: None, work)
    assert recorded == original
    assert result["coordinates"] == metrics["coordinates"]
    assert result["stages"] == metrics["stages"]
    assert recorder.count == result["evaluations"]
    records = read_history(history)
    assert sum(str(record["stage"]).startswith("probe") for record in records) == 10
    assert any(
        str(record["stage"]).startswith("trial") and isinstance(record["accepted"], bool)
        for record in records
    )
    assert all(record["score"] is not None for record in records)
    assert load_history_path(history, records[0]).sections[0].frame.z == case.start_tangent
    assert tuple(guide.number for guide in load_history_path(history, records[0]).guides) == (0,)
    assert recorder.bytes == history.stat().st_size
    # Scope restoration means an ordinary later transport cannot append anything.
    broad_chart.integrate(case, seed.coordinates, 64, lambda: None)
    assert len(read_history(history)) == len(records)


def test_recording_limit_stops_before_dropping_a_path_and_restores_scope(tmp_path: Path) -> None:
    """
    Preserve the completed prefix, propagate the cap and permit later normal work.
    """
    case = SpatialSBend().targets()
    coordinates = (0.0,) * 9 + (1.2,)
    recorder = SearchRecorder(
        tmp_path / "cap.jsonl", "limited", lambda: None, CaptureLimits(paths=1)
    )
    with pytest.raises(RuntimeError, match="count cap"), recorder.recording():
        broad_chart.integrate(case, coordinates, 64, lambda: None)
        broad_chart.integrate(case, coordinates, 64, lambda: None)
    assert len(read_history(recorder.path)) == 1
    broad_chart.integrate(case, coordinates, 64, lambda: None)
    with pytest.raises(RuntimeError, match="reopen"), recorder.recording():
        pass


def test_interrupted_tail_recovers_without_rerunning_or_rewriting_evidence(tmp_path: Path) -> None:
    """
    Simulate a power loss after one flushed path and half of the next JSON event.
    """
    manifest, fixture = _manifest(tmp_path)
    history = tmp_path / "ordinary.jsonl"
    with SearchRecorder(history, "ordinary", lambda: None).recording():
        broad_chart.integrate(fixture.targets(), (0.0,) * 9 + (1.2,), 64, lambda: None)
    with history.open("ab") as stream:
        stream.write(b'{"kind":"path","sequence":1')
    before = history.read_bytes()
    reference_before = manifest.read_bytes()
    with pytest.raises(ValueError, match="Interrupted"):
        read_history(history)
    recovered = recover(tmp_path)
    assert manifest.read_bytes() == reference_before
    assert history.read_bytes() == before
    session = Session(recovered)
    session.select("ordinary", 0)
    assert session.snapshot is not None
    session.select_section(9)
    assert session.state()["section"] == 9
    assert session.state()["solvers"][1]["status"] == "stopped"
    assert session.state()["solvers"][1]["history_count"] == 1
    with pytest.raises(ValueError, match="outside"):
        session.select("ordinary", 1)


def test_missing_solver_and_unmeasured_rules_stay_visible(tmp_path: Path) -> None:
    """
    Keep unrun methods, missing physics and invalid selections distinct from success.
    """
    manifest, fixture = _manifest(tmp_path)
    session = Session(manifest)
    session.select_section(16)
    assert session.snapshot is not None
    rules = observations(session.snapshot, fixture.targets(), 4.5)
    assert (
        next(rule for rule in rules if rule.name == "Full-thickness self-collision").status
        == "unmeasured"
    )
    assert (
        next(rule for rule in rules if rule.name == "No wide-axis bending").status
        == "not_applicable"
    )
    assert next(
        rule for rule in rules if rule.name == "Displayed centre bend / declared tightness"
    ).value == pytest.approx(1, abs=0.01)
    session.select("ordinary")
    assert session.snapshot is None
    assert session.state()["snapshot"] is None
    assert session.state()["solvers"][1]["status"] == "not_run"
    with pytest.raises(ValueError):
        session.select_section(0)
    with pytest.raises(ValueError):
        session.select("made-up")
    payload = json.loads(manifest.read_text())
    payload["solvers"][1]["history"] = "../outside.jsonl"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="inside"):
        Session(manifest)


def test_multi_conductor_capture_does_not_invent_circular_conductor_profiles() -> None:
    """
    Retain the existing material ruling until an actual bonded profile is supplied.
    """
    case = replace(SpatialSBend().targets(), lines=4)
    path = broad_chart.integrate(case, (0.0,) * 9 + (1.2,), 64, lambda: None)
    snapshot = freeze_path("multi", path, intervals=16)
    assert all(
        section.kind == "material_ruling" and len(section.outline) == 2
        for section in snapshot.sections
    )
    assert snapshot.lines == 4
