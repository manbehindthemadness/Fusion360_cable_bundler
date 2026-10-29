"""
Check physical bend-plane circles and shared frozen geometry in both diagnostic views.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, magnitude
from devtools.ribbon_analysis.inspection.archive import snapshot_payload
from devtools.ribbon_analysis.inspection.panels import bend_witness, witnesses
from devtools.ribbon_analysis.inspection.session import Session
from devtools.ribbon_analysis.traces import TracePath
from experiments.experiment_ribbon_diagnostic_viewer import examples


@pytest.mark.parametrize("vertical", (False, True))
def test_circles_touch_the_curve_and_retain_the_actual_bend_plane(vertical: bool) -> None:
    """
    Use an exact parabola with known peak radius and rotate its bend plane in space.
    """
    controls = tuple(
        Vector3(0, x, y) if vertical else Vector3(x, y, 0)
        for x, y in ((0, 0), (1 / 3, 0), (2 / 3, 1 / 3), (1, 1))
    )
    guide = TracePath(0, (CubicBezier(*controls),), controls, (0,) * 4 + (1,) * 4)
    overlay = bend_witness(guide, 0.25, "Known parabola")
    assert dict(overlay.measurements)["actual_radius_mm"] == pytest.approx(0.5)
    for stroke, radius in zip(overlay.strokes, (0.25, 0.5)):
        assert stroke.role == ("limit" if radius == 0.25 else "actual")
        assert stroke.points[0] == overlay.anchor
        assert magnitude(difference(stroke.points[-1], overlay.anchor)) < 1e-14
        center = stroke.points[0].translated(difference(stroke.points[32], stroke.points[0]), 0.5)
        assert all(
            magnitude(difference(point, center)) == pytest.approx(radius) for point in stroke.points
        )
        assert all((point.x if vertical else point.z) == 0 for point in stroke.points)


@pytest.mark.parametrize("bend", (0.0, 1e-6))
def test_straight_and_gentle_paths_do_not_invent_or_enlarge_the_actual_circle(bend: float) -> None:
    """
    Keep absent/infinite radii explicit and retain omitted large radii numerically.
    """
    controls = (Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(2, bend, 0), Vector3(3, bend, 0))
    overlay = bend_witness(TracePath(0, (CubicBezier(*controls),), controls, ()), 1, "Gentle")
    assert all(stroke.role != "actual" for stroke in overlay.strokes)
    if bend:
        assert dict(overlay.measurements)["actual_radius_mm"] > 8
        assert any("omitted" in note for note in overlay.notes)
    else:
        assert not overlay.strokes and any("Straight" in note for note in overlay.notes)


def test_palette_and_native_witnesses_share_the_same_unchanged_snapshot(tmp_path: Path) -> None:
    """
    Expose the identical physical polylines to both renderers without re-solving.
    """
    session = Session(examples.create(tmp_path / "example", "ribbon", lambda: None))
    snapshot = session.snapshot
    assert snapshot is not None
    before = snapshot_payload(snapshot)
    state = session.state()
    assert state["witnesses"] == [
        asdict(overlay) for overlay in witnesses(snapshot, session.targets)
    ]
    assert len(state["witnesses"]) == 4
    assert all(
        any(stroke["role"] == "limit" for stroke in overlay["strokes"])
        for overlay in state["witnesses"][:3]
    )
    assert snapshot_payload(snapshot) == before
