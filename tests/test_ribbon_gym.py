"""
Verify endpoint-only gym input independence and face/zone geometry contracts.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from cable_bundler.routing.geometry import difference, dot, magnitude
from devtools.ribbon_analysis.gym import Config, Goal, generate
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
def test_solids_stay_in_their_zones_and_leave_center_empty(seed: int) -> None:
    """
    Keep each full virtual solid outside the central void and inside its own cell.
    """
    scene = generate(Config(seed=seed))
    side = scene.config.side_mm
    for index, zone in enumerate(ZONES):
        box = scene.box(index)
        for coordinate, center, size in zip(
            zone, (box.center.x, box.center.y, box.center.z), box.size
        ):
            assert (coordinate - 0.5) * side <= center - size / 2
            assert center + size / 2 <= (coordinate + 0.5) * side
            assert size >= scene.config.width_mm


@pytest.mark.parametrize("face", range(6))
def test_faces_preserve_target_center_and_ordered_orientation(face: int) -> None:
    """
    Derive normal departure/arrival and width directions from the selected face only.
    """
    original = generate()
    for roll in range(4):
        scene = original.choose("a", Goal(original.a.zone, face, roll))
        origin, normal, across = scene.pose(scene.a)
        face_center, _, _, corners = scene.box(scene.a.zone).face(face)
        assert origin == face_center == scene.targets.start
        assert scene.targets.start_tangent == normal
        assert magnitude(across) == pytest.approx(1)
        assert dot(across, normal) == 0
        assert all(abs(dot(difference(point, origin), normal)) < 1e-10 for point in corners)
        assert scene.b == original.b and scene.box(scene.b.zone) == original.box(original.b.zone)
        assert scene.targets.end == original.targets.end
    end = original.choose("b", Goal(original.b.zone, face))
    assert dot(end.targets.end_tangent, end.pose(end.b)[1]) == -1


def test_face_selection_and_scale_do_not_resample_boxes() -> None:
    """
    Keep unrelated inputs stable while changing a face or nominal dimensional scale.
    """
    original = generate()
    changed = original.choose("a", replace(original.a, face=(original.a.face + 1) % 6))
    assert changed.box(changed.a.zone) == original.box(original.a.zone)
    scaled = generate(replace(original.config, diameter_mm=3))
    assert (scaled.a, scaled.b) == (original.a, original.b)
    assert scaled.targets.start.x == pytest.approx(2 * original.targets.start.x)
    assert scaled.config.side_mm == 2 * original.config.side_mm
    with pytest.raises(ValueError, match="different"):
        original.choose("a", Goal(original.b.zone, 0))


@pytest.mark.parametrize(
    "changes",
    (
        {"void_widths": 2.99},
        {"seed": True},
        {"lines": 0},
        {"diameter_mm": float("nan")},
        {"void_widths": float("inf")},
        {"diameter_mm": "1.5"},
    ),
)
def test_malformed_preview_dimensions_fail_before_render(changes: dict[str, Any]) -> None:
    """
    Reject malformed external inputs without resizing or silently clamping the gym.
    """
    with pytest.raises(ValueError):
        Config(**changes)
