"""
Verify endpoint-only gym input independence and face/zone geometry contracts.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude
from devtools.ribbon_analysis.gym import Config, Goal, generate
from devtools.ribbon_analysis.gym.primitives import Dodecahedron
from devtools.ribbon_analysis.gym.scene import ZONES


def test_replay_has_no_route_and_two_distinct_outer_zones() -> None:
    """
    Preserve exact endpoint input replay without depending on a solver or path seed.
    """
    scene = generate()
    assert scene == generate()
    assert scene != generate(Config(seed=1))
    assert len(ZONES) == 26 and (0, 0, 0) not in ZONES
    assert scene.a.zone != scene.b.zone
    payload = scene.payload()
    assert payload["side_mm"] == 3 * payload["width_mm"]
    assert set(payload) == {
        "schema",
        "config",
        "width_mm",
        "side_mm",
        "zone_mm",
        "extent_mm",
        "a",
        "b",
        "zones",
        "faces",
        "solids",
        "targets",
        "drawing",
        "scope",
    }
    assert json.loads(json.dumps(payload))["targets"]["start"] == payload["targets"]["start"]


@pytest.mark.parametrize("seed", (0, 1, 4294967295))
@pytest.mark.parametrize("percentages", ((300, 300), (500, 150), (300, 600)))
def test_solids_stay_in_their_zones_and_touch_inward_barriers(
    seed: int, percentages: tuple[int, int]
) -> None:
    """
    Check actual polyhedron extrema in all26cells, including edge/corner contacts.
    """
    scene = generate(Config(seed=seed, void_percent=percentages[0], zone_percent=percentages[1]))
    for index, zone in enumerate(ZONES):
        bounds, solid = scene.zone_box(index), scene.solid(index)
        for axis, coordinate, center, size in zip(
            ("x", "y", "z"), zone, (bounds.center.x, bounds.center.y, bounds.center.z), bounds.size
        ):
            values = [getattr(point, axis) for point in solid.vertices]
            assert min(values) >= center - size / 2 - 1e-10
            assert max(values) <= center + size / 2 + 1e-10
            if coordinate:
                nearest = min(values) if coordinate > 0 else max(values)
                assert nearest == pytest.approx(coordinate * scene.config.side_mm / 2)


def test_regular_dodecahedron_faces_edges_and_outward_winding() -> None:
    """
    Independently verify twenty vertices,twelve regular pentagons and thirty shared edges.
    """
    solid = Dodecahedron(Vector3(3, 4, 5), 2)
    edges: set[tuple[Vector3, Vector3]] = set()
    lengths = []
    for face in range(12):
        origin, normal, across, points = solid.face(face)
        assert len(points) == 5
        assert dot(normal, difference(origin, solid.center)) > 0
        assert dot(normal, across) == pytest.approx(0, abs=1e-12)
        assert all(abs(dot(difference(point, origin), normal)) < 1e-10 for point in points)
        assert (
            dot(cross(difference(points[1], points[0]), difference(points[2], points[1])), normal)
            > 0
        )
        for first, last in zip(points, points[1:] + points[:1]):
            ordered = tuple(sorted((first, last), key=lambda point: (point.x, point.y, point.z)))
            edges.add((ordered[0], ordered[1]))
            lengths.append(magnitude(difference(first, last)))
    assert len(solid.vertices) == 20 and len(edges) == 30
    assert max(lengths) == pytest.approx(min(lengths))
    assert all(
        magnitude(difference(point, solid.center)) == pytest.approx(2 * 3**0.5)
        for point in solid.vertices
    )


@pytest.mark.parametrize("face", range(12))
def test_faces_preserve_target_center_and_ordered_orientation(face: int) -> None:
    """
    Derive normal departure/arrival and width directions from the selected face only.
    """
    original = generate()
    for roll in range(4):
        scene = original.choose("a", Goal(original.a.zone, face, roll))
        origin, normal, across = scene.pose(scene.a)
        face_center, _, _, corners = scene.solid(scene.a.zone).face(face)
        assert origin == face_center == scene.targets.start
        assert scene.targets.start_tangent == normal
        assert magnitude(across) == pytest.approx(1)
        assert dot(across, normal) == pytest.approx(0, abs=1e-12)
        assert all(abs(dot(difference(point, origin), normal)) < 1e-10 for point in corners)
        assert scene.b == original.b and scene.solid(scene.b.zone) == original.solid(
            original.b.zone
        )
        assert scene.targets.end == original.targets.end
    end = original.choose("b", Goal(original.b.zone, face))
    assert dot(end.targets.end_tangent, end.pose(end.b)[1]) == pytest.approx(-1)


def test_face_selection_and_scale_do_not_resample_solids() -> None:
    """
    Keep unrelated inputs stable while changing a face or nominal dimensional scale.
    """
    original = generate()
    changed = original.choose("a", replace(original.a, face=(original.a.face + 1) % 12))
    assert changed.solid(changed.a.zone) == original.solid(original.a.zone)
    scaled = generate(replace(original.config, diameter_mm=3))
    assert (scaled.a, scaled.b) == (original.a, original.b)
    assert scaled.targets.start.x == pytest.approx(2 * original.targets.start.x)
    assert scaled.config.side_mm == 2 * original.config.side_mm
    with pytest.raises(ValueError, match="different"):
        original.choose("a", Goal(original.b.zone, 0))


@pytest.mark.parametrize(
    "changes",
    (
        {"void_percent": 299},
        {"seed": True},
        {"lines": 0},
        {"diameter_mm": float("nan")},
        {"zone_percent": float("inf")},
        {"zone_percent": 0},
        {"diameter_mm": "1.5"},
    ),
)
def test_malformed_preview_dimensions_fail_before_render(changes: dict[str, Any]) -> None:
    """
    Reject malformed external inputs without resizing or silently clamping the gym.
    """
    with pytest.raises(ValueError):
        Config(**changes)


def test_void_and_zone_percentages_are_independent() -> None:
    """
    Interpret percentages against ribbon width without coupling the two controls.
    """
    config = Config(lines=4, diameter_mm=2, void_percent=450, zone_percent=125)
    assert config.width_mm == 8
    assert config.side_mm == 36
    assert config.zone_mm == 10
    assert config.extent_mm == 56
    assert replace(config, zone_percent=200).side_mm == config.side_mm
    assert replace(config, void_percent=600).zone_mm == config.zone_mm
