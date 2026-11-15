"""
Verify exact root partition topology and native-plane material orientation without native construction.
"""

from __future__ import annotations

from typing import Literal

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_complete.contracts import IncompleteRibbonInput
from experiments.experiment_ribbon_complete.root_profiles import bind_frame, partition
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_capture import inputs


@pytest.mark.parametrize("lines,diameter", ((1, 0.75), (2, 0.75), (5, 0.7), (10, 1.6)))
def test_root_partition_keeps_every_original_arc_and_cancels_internal_seams(
    lines: int, diameter: float
) -> None:
    """
    Every unchanged exterior arc belongs to one closed root; neighboring seams are exact reverses.
    """
    original = material_profile(lines, diameter)
    roots = partition(lines, diameter)
    assert [root.pin_number for root in roots] == list(range(1, lines + 1))
    exterior = [
        edge for root in roots for edge in root.edges if edge.source_profile_index is not None
    ]
    assert sorted(
        edge.source_profile_index for edge in exterior if edge.source_profile_index is not None
    ) == list(range(len(original)))
    for edge in exterior:
        assert edge.source_profile_index is not None
        assert edge.geometry == original[edge.source_profile_index]
    for root in roots:
        for first, second in zip(root.edges, root.edges[1:] + root.edges[:1]):
            assert first.geometry.controls[-1] == second.geometry.controls[0]
    for left, right in zip(roots, roots[1:]):
        a = next(
            edge.geometry for edge in left.edges if edge.geometry.label.startswith("right-seam")
        )
        b = next(
            edge.geometry for edge in right.edges if edge.geometry.label.startswith("left-seam")
        )
        assert a.controls == tuple(reversed(b.controls))
        assert a.weights == tuple(reversed(b.weights))


@pytest.mark.parametrize("side", ("start", "end"))
def test_actual_cap_frame_keeps_thickness_identity_at_both_ends(
    side: Literal["start", "end"],
) -> None:
    """
    Inward normals reverse between ends but the positive material thickness direction does not.
    """
    trunk = inputs()[2]
    inward = Vector3(1 if side == "start" else -1, 0, 0)
    center = getattr(trunk, side)
    # Native Plane.origin can be any point of that plane, not its cap center.
    origin = center.translated(Vector3(0, 1, 1), 100)
    frame = bind_frame(trunk, side, origin, inward)
    assert frame.origin == center
    assert frame.thickness == Vector3(0, 0, 1)
    assert dot(frame.width, Vector3(0, 1, 0)) > 0
    assert frame.maximum_control_deviation_mm == 0


@pytest.mark.parametrize("offset,accepted", ((0.009, True), (0.0101, False)))
def test_cap_binding_measures_native_section_placement_without_moving_input_targets(
    offset: float, accepted: bool
) -> None:
    """
    Preserve the fixed target and expose accepted plane displacement instead of snapping the route.
    """
    trunk = inputs()[2]
    plane_origin = trunk.start.translated(trunk.start_tangent, offset)
    fixed = trunk.start
    if accepted:
        frame = bind_frame(trunk, "start", plane_origin, trunk.start_tangent)
        assert frame.maximum_control_deviation_mm == pytest.approx(offset)
        assert magnitude(difference(frame.origin, fixed)) == pytest.approx(offset)
        assert trunk.start is fixed
    else:
        with pytest.raises(IncompleteRibbonInput, match="over0.01mm"):
            bind_frame(trunk, "start", plane_origin, trunk.start_tangent)


def test_wrong_cap_normal_cannot_be_repaired_by_reversing_material_order() -> None:
    """
    Reject an outward normal presented as inward rather than flip pin or thickness identity.
    """
    trunk = inputs()[2]
    with pytest.raises(IncompleteRibbonInput, match="orientation"):
        bind_frame(trunk, "start", trunk.start, Vector3(-1, 0, 0))
