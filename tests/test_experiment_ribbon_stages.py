"""
Verify diagnostic observations preserve decisions and signed sample semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition import diagnostic
from experiments.experiment_ribbon_cap_transition.fixtures import direction_cases
from experiments.experiment_ribbon_cap_transition.screen import _fits
from experiments.experiment_ribbon_cap_transition.solver import solve_candidate
from experiments.experiment_ribbon_cap_transition.stages import StageRecorder
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit


def test_observation_preserves_shape_and_stage_order() -> None:
    """
    Compare instrumented and uninstrumented controls as a unit contract, not coverage.
    """
    case = direction_cases()[0]
    fits = _fits(case)
    recorder = StageRecorder(fits)
    original = solve_candidate(case, *fits)
    observed = solve_candidate(case, *fits, observer=recorder)
    assert observed == original
    assert tuple(recorder.stages) == ("unbanked", "banked", "cap_A", "cap_B", "equalized")
    assert all(stage["relative_length_spread"] == 0 for stage in recorder.stages.values())


def test_signed_chords_do_not_hide_reversed_arrival() -> None:
    """
    Keep a reversed B chord visible rather than taking absolute normal alignment.
    """
    normal = Vector3(1, 0, 0)
    fits = (
        RibbonEndFit((Vector3(0, 0, 0),), (Vector3(0, 0, 1),), approach_normal=normal),
        RibbonEndFit((Vector3(2, 0, 0),), (Vector3(0, 0, 1),), approach_normal=normal),
    )
    recorder = StageRecorder(fits)
    recorder("sample", ((Vector3(0, 0, 0), Vector3(3, 0, 0), Vector3(2, 0, 0)),))
    caps = recorder.stages["sample"]["caps"]
    assert isinstance(caps, list)
    assert caps[0]["inward_chord_angles_degrees"] == [0.0]
    assert caps[1]["inward_chord_angles_degrees"] == [180.0]
    with pytest.raises(ValueError, match="more than once"):
        recorder("sample", ((Vector3(0, 0, 0), Vector3(2, 0, 0)),))


def test_degenerate_chord_is_not_reported_as_a_tangent() -> None:
    """
    Reject unusable sample directions instead of supplying an optimistic angle.
    """
    point = Vector3(0, 0, 0)
    fit = RibbonEndFit((point,), (Vector3(0, 0, 1),), approach_normal=Vector3(1, 0, 0))
    with pytest.raises(ValueError, match="positive lengths"):
        StageRecorder((fit, fit))("sample", ((point, point),))


@pytest.mark.parametrize("discrepancy", (False, True))
def test_runner_retains_all_rows_and_stops_on_discrepancy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, discrepancy: bool
) -> None:
    """
    Exercise reporting and stop gates with a stubbed solver, not geometry coverage.
    """
    cases = direction_cases()[:2]
    previous = tmp_path / "previous.json"
    previous.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": case.name,
                        "candidate": {"trunk_lane_spread": 0.0, "preflight": {"failures": []}},
                    }
                    for case in cases
                ]
            }
        )
    )
    calls: list[str] = []

    def solve(*args: object, **kwargs: object) -> SimpleNamespace:
        """
        Supply final metrics without any numerical search.
        """
        del args, kwargs
        calls.append("solve")
        return SimpleNamespace(spread=0.02 if discrepancy else 0.0, folded=False, end_lead_mm=0.0)

    monkeypatch.setitem(diagnostic.__dict__, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(diagnostic, "PREVIOUS_REPORT", previous)
    monkeypatch.setitem(diagnostic.__dict__, "development_cases", lambda: cases)
    monkeypatch.setitem(diagnostic.__dict__, "_fingerprints", lambda: {"frozen": "hash"})
    monkeypatch.setitem(diagnostic.__dict__, "verify_sources", lambda: {})
    monkeypatch.setitem(diagnostic.__dict__, "solve_candidate", solve)
    monkeypatch.setitem(
        diagnostic.__dict__,
        "inspect_candidate",
        lambda *args: {"verdict": "unresolved", "failures": []},
    )
    report = json.loads((diagnostic.run() / "report.json").read_text())
    assert report["planned"] == 2 and report["native_attempts"] == 0
    assert len(calls) == (1 if discrepancy else 2)
    assert report["evaluated"] == len(calls)
    if discrepancy:
        assert "discrepancy" in report["stop_reason"]
        assert report["cases"][1]["status"] == "not_attempted"
    else:
        assert all(row["matches_saved_outcome"] for row in report["cases"])
