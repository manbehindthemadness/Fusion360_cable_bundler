"""
Verify constraint glyphs carry measured values without changing route geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.api import Candidate, Evidence, analyze
from devtools.ribbon_analysis.constraint_geometry import Restriction, build, circle, layout
from devtools.ribbon_analysis.contracts import Targets


@dataclass(frozen=True)
class _Field:
    """
    Supply a known gentle cylindrical bend independently of any solver.
    """

    lines: int = 3
    diameter_mm: float = 1.0
    half_width_mm: float = 1.6

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Return a constant radius and regular material progress.
        """
        if not 0 <= u <= 1 or self.lines != 3:
            raise ValueError("Independent fixture domain required.")
        return 1 / 30, 0.0, 0.0


@dataclass(frozen=True)
class _Path:
    """
    Keep a radius-30 bend and unchanged parallel material lanes.
    """

    field: _Field = _Field()

    @staticmethod
    def lane(u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return the exact independent arc and normalized-parameter derivative.
        """
        return (
            Vector3(30 * math.sin(u), offset_mm, 30 * (1 - math.cos(u))),
            Vector3(30 * math.cos(u), 0, 30 * math.sin(u)),
        )


def _evidence() -> Evidence:
    """
    Freeze a deliberate endpoint miss for constraint diagnostics.
    """
    path = _Path()
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    end = path.lane(1, 0)[0].translated(x, 5)
    targets = Targets(
        "known arc", Vector3(0, 0, 0), end, x, Vector3(math.cos(1), 0, math.sin(1)), y, y, 3, 1
    )
    return analyze(Candidate("arc miss", path, targets, "independent known radius"), intervals=32)


def test_radius_glyph_and_measurements_use_the_actual_frozen_cubics() -> None:
    """
    Preserve endpoint misses and distinguish minimum radius from actual curvature.
    """
    evidence = _evidence()
    before = evidence.fingerprint
    panels = {o.key: o for o in build(evidence)}
    assert set(panels) == {
        "containment",
        "center_bend",
        "lane_bend",
        "material_progress",
        "targets",
        "solver_limits",
    }
    assert dict(panels["targets"].measurements)["center_gap_mm"] == pytest.approx(5)
    assert dict(panels["center_bend"].measurements)["actual_radius_mm"] == pytest.approx(
        30, rel=1e-5
    )
    assert dict(panels["lane_bend"].measurements)["minimum_radius_mm"] == 3
    assert dict(panels["material_progress"].measurements)["minimum_j"] == 1
    assert "unavailable" in panels["solver_limits"].notes[0]
    assert evidence.fingerprint == before
    point, tangent, normal = Vector3(1, 2, 3), Vector3(1, 0, 0), Vector3(0, 0, 1)
    glyph = circle(point, tangent, normal, 4)
    center = point.translated(normal, 4)
    assert (
        glyph.points[0] == glyph.points[-1]
        or magnitude(difference(glyph.points[0], glyph.points[-1])) < 1e-12
    )
    assert all(magnitude(difference(p, center)) == pytest.approx(4) for p in glyph.points)


def test_solver_bounds_are_explicit_metadata_and_missing_samples_stay_unmeasured() -> None:
    """
    Never infer a solver bound or material certificate from a smooth-looking guide.
    """
    evidence = replace(_evidence(), series=(), regions=())
    restriction = Restriction("carrier ratio", 5, 1, 5, "frozen solver policy")
    panels = {o.key: o for o in build(evidence, (restriction,))}
    assert not panels["material_progress"].measurements
    assert "not retained" in panels["material_progress"].notes[0]
    assert dict(panels["solver_limits"].measurements)["carrier ratio upper"] == 5
    assert "not prove" in panels["solver_limits"].notes[-1]
    with pytest.raises(ValueError, match="finite ordered bounds"):
        Restriction("bad", math.nan, 0, 1, "test")


def test_stationary_boundary_is_retained_as_unmeasured_curvature() -> None:
    """
    Keep singular diagnostic guides visible instead of rejecting the entire display.
    """
    from cable_bundler.routing.geometry import CubicBezier
    from devtools.ribbon_analysis.constraint_geometry import _bend
    from devtools.ribbon_analysis.traces import TracePath

    point = Vector3(0, 0, 0)
    guide = TracePath(
        -1, (CubicBezier(point, point, point, point),), (point,) * 4, (0.0,) * 4 + (1.0,) * 4
    )
    overlay = _bend(guide, 3, "lane_bend", "singular boundary")
    assert dict(overlay.measurements)["utilization"] is None
    assert dict(overlay.measurements)["stationary_samples"] == 3
    assert "unavailable (stationary)" in overlay.notes[1]


def test_simultaneously_visible_descriptions_have_disjoint_stable_slots() -> None:
    """
    Reserve space for every note without moving real witnesses or measuring again.
    """
    evidence = _evidence()
    overlays = build(evidence, (Restriction("carrier ratio", 5, 1, 5, "test"),))
    for upper, lower in zip(overlays, overlays[1:]):
        last_baseline = upper.anchor.y - 5 - 3 * (len(upper.notes) - 1)
        next_heading_top = lower.anchor.y
        assert last_baseline - 2 > next_heading_top
    assert layout(evidence, overlays) == overlays
    moved = layout(evidence, tuple(replace(o, anchor=Vector3(999, 999, 999)) for o in overlays))
    assert moved == overlays
    assert all(a.strokes == b.strokes for a, b in zip(overlays, moved))
    assert all(a.measurements == b.measurements for a, b in zip(overlays, moved))
