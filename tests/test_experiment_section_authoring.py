"""
Protect shared section spacing and explicit cap interpolation without Fusion.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition import section_comparison
from experiments.experiment_ribbon_cap_transition.planning import FrozenTargetTurns
from experiments.experiment_ribbon_cap_transition.regression_cases import comparison_cases
from experiments.experiment_ribbon_cap_transition.screen import _fits
from experiments.experiment_ribbon_cap_transition.section_authoring import (
    SectionField,
    solve_authored_sections,
)
from experiments.experiment_ribbon_cap_transition.section_comparison import geometry_findings
from experiments.experiment_ribbon_cap_transition.section_sampling import section_metrics
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit, RibbonShape


def _field() -> SectionField:
    """
    Supply a curved/twisted two-node scaffold with perpendicular end widths.
    """
    return SectionField(
        (
            RibbonFrame(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)),
            RibbonFrame(Vector3(10, 0, 2), Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(0, -1, 0)),
        ),
        1.5,
        3,
    )


@pytest.mark.parametrize("fraction", (0.0, 0.1, 0.5, 0.9, 1.0))
def test_shared_field_keeps_nominal_spacing_and_planarity(fraction: float) -> None:
    """
    All lanes are translations along one unit width, even between authored nodes.
    """
    field = _field()
    points = tuple(field.lane_point(0, fraction, i) for i in range(3))
    gaps = tuple(difference(b, a) for a, b in zip(points, points[1:]))
    assert tuple(magnitude(gap) for gap in gaps) == pytest.approx((1.5, 1.5))
    assert magnitude(difference(gaps[0], gaps[1])) < 1e-12


@pytest.mark.parametrize("at_start", (True, False))
def test_every_lane_approaches_the_exact_cap_tangent(at_start: bool) -> None:
    """
    Near-cap chords converge to the prescribed derivative, not flattened samples.
    """
    field = _field()
    cap, inside = (0.0, 1e-5) if at_start else (1.0, 1 - 1e-5)
    desired = Vector3(1 if at_start else -1, 0, 0)
    for lane in range(3):
        chord = difference(field.lane_point(0, inside, lane), field.lane_point(0, cap, lane))
        assert dot(unit(chord), desired) > 1 - 1e-9


def test_regression_gate_does_not_require_identical_different_strategy_shapes() -> None:
    """
    Separate deliberate strategy differences from worsening existing hard metrics.
    """
    baseline = {
        "status": "reject",
        "failures": ["compression"],
        "source_shape": {"strategy": "old"},
        "section_metrics": {"minimum_neighbor_pitch_ratio": 0.98},
    }
    candidate = {
        "status": "reject",
        "failures": ["compression"],
        "source_shape": {"strategy": "new"},
        "section_metrics": {"minimum_neighbor_pitch_ratio": 0.97},
    }
    assert geometry_findings(baseline, candidate) == ["worsened:minimum_neighbor_pitch_ratio"]


def test_field_rejects_invalid_coordinates() -> None:
    """
    Do not extrapolate outside a fixed node pair or silently change conductor order.
    """
    with pytest.raises(ValueError, match="index"):
        _field().lane_point(1, 0.5, 0)
    with pytest.raises(ValueError, match="fraction"):
        _field().lane_point(0, float("nan"), 0)


def test_fixed_caps_must_not_be_repaired(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Check authoring wiring on a mocked scaffold, not a solver geometry trial.
    """
    case = comparison_cases()[0]
    fits = _fits(case)
    width = unit(difference(fits[0].centers[-1], fits[0].centers[0]))
    centers = tuple(fit.centers[case.lines // 2] for fit in fits)
    tangent = fits[0].approach_normal
    assert tangent is not None
    frames = tuple(RibbonFrame(p, tangent, width, fits[0].normals[0]) for p in centers)

    def scaffold(
        _case: RibbonStressCase, _start: RibbonEndFit, _end: RibbonEndFit
    ) -> tuple[RibbonFrame, ...]:
        """
        Supply fixed nodes without invoking a solver in a wiring unit test.
        """
        return frames

    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.section_authoring.candidate_frames",
        scaffold,
    )
    shape = solve_authored_sections(case, *fits)
    for i, lane in enumerate(shape.lanes):
        assert lane[0] is fits[0].centers[i] and lane[-1] is fits[1].centers[i]
    assert section_metrics(shape, case.diameter_mm)[
        "minimum_neighbor_pitch_ratio"
    ] == pytest.approx(1)
    moved = replace(
        fits[0], centers=(fits[0].centers[0].translated(width, 0.1), *fits[0].centers[1:])
    )
    with pytest.raises(ValueError, match="fixed cap targets"):
        solve_authored_sections(case, moved, fits[1])


def test_antiparallel_widths_are_rejected_without_a_fallback() -> None:
    """
    Do not silently reverse conductor order through a degenerate shared section.
    """
    field = _field()
    frames = (field.frames[0], replace(field.frames[1], width=Vector3(0, -1, 0)))
    with pytest.raises(ValueError, match="degenerates"):
        SectionField(frames, 1.5, 3)


def test_batch_stops_after_first_regression_and_retains_skips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Exercise scheduling with fake shapes; no numerical solve or Fusion call occurs.
    """
    calls: list[str] = []

    def fake_solve(case: RibbonStressCase, _start: RibbonEndFit, _end: RibbonEndFit) -> RibbonShape:
        """
        Record scheduled case IDs and return deliberately inert samples.
        """
        calls.append(case.name)
        return RibbonShape((), (), (), 0, False, 1)

    def fake_targets(
        case: RibbonStressCase, *_args: object, **_kwargs: object
    ) -> FrozenTargetTurns:
        """
        Keep fixture setup independent of numerical solving.
        """
        return FrozenTargetTurns(case)

    def empty_hashes() -> dict[str, str]:
        """
        Simulate stable input/source identities.
        """
        return {}

    def fake_inspect(_shape: RibbonShape, _plan: object) -> dict[str, object]:
        """
        Supply a worsening already-failing radius on the first candidate.
        """
        return {
            "failures": ["radius"],
            "occupied_and_lane_checks": {
                "sampled_whole_lane_minimum_radius_mm": 1 if len(calls) > 11 else 2
            },
        }

    def fake_measure(_shape: RibbonShape, _diameter: float) -> dict[str, object]:
        """
        Isolate the scheduler from section measurement implementation.
        """
        return {"section_findings": []}

    globals_under_test = vars(section_comparison)
    monkeypatch.setitem(globals_under_test, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(globals_under_test, "_fingerprints", empty_hashes)
    monkeypatch.setitem(globals_under_test, "verify_sources", empty_hashes)
    monkeypatch.setitem(globals_under_test, "freeze_targets", fake_targets)
    monkeypatch.setitem(globals_under_test, "solve_candidate", fake_solve)
    monkeypatch.setitem(globals_under_test, "solve_authored_sections", fake_solve)
    monkeypatch.setitem(globals_under_test, "inspect_candidate", fake_inspect)
    monkeypatch.setattr(section_comparison, "_measure", fake_measure)
    directory = section_comparison.run(section_comparison.SectionMethod.AUTHORED)
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    assert report["baseline_evaluated"] == 11 and report["candidate_evaluated"] == 1
    assert report["solve_calls"] == len(calls) == 12
    assert calls[-1] == comparison_cases()[5].name
    assert "regression" in report["stop_reason"]
    assert sum(row["candidate"]["status"] == "not_attempted" for row in report["cases"]) == 10
