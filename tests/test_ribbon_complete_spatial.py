"""
Verify explicit spatial boundary geometry, root orientation and coordinate-proof limits.

Analytical frame fixtures are not independent complete-ribbon configurations.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Literal

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_complete.profile_transition import build
from experiments.experiment_ribbon_complete.root_profiles import bind_frame, partition
from experiments.experiment_ribbon_complete.spatial_certificate import certify
from experiments.experiment_ribbon_complete.spatial_frame import ChartOrientation, FrameSpan
from experiments.experiment_ribbon_complete.spatial_transition import bind_root, compose
from tests.test_ribbon_complete_capture import inputs
from tests.test_ribbon_complete_lengths import checkpoint

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


def frame(low: Fraction = Fraction(0), high: Fraction = Fraction(1)) -> FrameSpan:
    """
    Supply explicit straight frame controls in their local span parameter.
    """
    return FrameSpan(
        low,
        high,
        (Vector3(float(low) * 10, 0, 0), Vector3(float(high) * 10, 0, 0)),
        (Y,),
        (Z,),
        ChartOrientation.POSITIVE,
    )


@pytest.mark.parametrize("side", ("start", "end"))
def test_root_binding_preserves_material_thickness_when_outgoing_tangents_reverse(
    side: Literal["start", "end"],
) -> None:
    """
    Both cap sides keep q/b identity; negative handedness is explicit rather than silently mirrored.
    """
    targets = inputs()[2]
    inward = X if side == "start" else Vector3(-1, 0, 0)
    cap = bind_frame(targets, side, getattr(targets, side), inward)
    origin = cap.point(-0.375, 0)
    outward = difference(Vector3(0, 0, 0), inward)
    sign = ChartOrientation.NEGATIVE if side == "start" else ChartOrientation.POSITIVE
    fields = FrameSpan(
        Fraction(0),
        Fraction(1),
        (origin, origin.translated(outward, 3)),
        (cap.width,),
        (cap.thickness,),
        sign,
    )
    for edge in build(partition(2, 0.75)[0], -0.375, 0.375):
        patch = compose(edge, fields, checkpoint)
        bind_root(patch, cap)
        assert certify(patch, checkpoint).status == "certified"
        for v in (0, 0.5, 1):
            q, b = edge.source.geometry.point(v)
            assert magnitude(difference(patch.jet(0, v).point, cap.point(q, b))) <= 0.01
            assert (
                magnitude(
                    difference(
                        patch.jet(0, v).along, Vector3(outward.x * 3, outward.y * 3, outward.z * 3)
                    )
                )
                <= 0.01
            )


def test_subspans_preserve_global_shape_progress_and_derivative_scale() -> None:
    """
    A midpoint split neither restarts the root-to-circle morph nor halves its global velocity.
    """
    edge = build(partition(2, 10)[0], -5, 5)[0]
    whole = compose(edge, frame(), checkpoint)
    parts = (
        compose(edge, frame(Fraction(0), Fraction(1, 2)), checkpoint),
        compose(edge, frame(Fraction(1, 2), Fraction(1)), checkpoint),
    )
    for part in parts:
        proof = certify(part, checkpoint)
        assert proof.status == "certified" and proof.minimum_signed_jacobian == Fraction(10)
        for fraction in (0, 0.3, 1):
            u = float(part.frame.low + (part.frame.high - part.frame.low) * Fraction(fraction))
            for v in (0, 0.25, 0.8, 1):
                a, b = whole.jet(u, v), part.jet(u, v)
                assert magnitude(difference(a.point, b.point)) <= 0.01
                assert magnitude(difference(a.along, b.along)) <= 0.01
                assert magnitude(difference(a.along_second, b.along_second)) <= 0.01


def test_curved_field_geometry_and_quotient_jets_are_not_replaced_by_station_interpolation() -> (
    None
):
    """
    Preserve a nonplanar polynomial center field and verify actual world derivatives geometrically.
    """
    edge = build(partition(1, 2)[0], 0, 1)[0]
    controls = tuple(Vector3(i * 2.5, 0, 2 / 6 if i == 2 else 0) for i in range(5))
    patch = compose(edge, replace(frame(), center=controls), checkpoint)
    assert certify(patch, checkpoint).status == "certified"
    u, v, h = 0.37, 0.3, 0.001
    a, b, c = patch.jet(u - h, v), patch.jet(u, v), patch.jet(u + h, v)
    first = Vector3(
        (c.point.x - a.point.x) / (2 * h),
        (c.point.y - a.point.y) / (2 * h),
        (c.point.z - a.point.z) / (2 * h),
    )
    second = Vector3(
        (a.point.x - 2 * b.point.x + c.point.x) / h**2,
        (a.point.y - 2 * b.point.y + c.point.y) / h**2,
        (a.point.z - 2 * b.point.z + c.point.z) / h**2,
    )
    assert magnitude(difference(first, b.along)) <= 0.01
    assert magnitude(difference(second, b.along_second)) <= 0.01


def test_coordinate_regular_geometry_is_not_a_material_length_certificate() -> None:
    """
    Positive chart Jacobian does not erase the extra length required by a moving boundary point.
    """
    edge = build(partition(2, 10)[0], -5, 5)[0]
    short = replace(frame(), center=(Vector3(0, 0, 0), X))
    patch = compose(edge, short, checkpoint)
    assert certify(patch, checkpoint).status == "certified"
    chord = magnitude(difference(patch.jet(1, 0).point, patch.jet(0, 0).point))
    assert chord > 1.01  # Already a lower bound exceeding the1mm center-path length.


def test_collapsing_frame_is_not_repaired_by_unit_vector_normalization() -> None:
    """
    An exact midspan width collapse stays uncertified even with valid endpoint sections.
    """
    edge = build(partition(1, 0.75)[0], 0, 0.375)[0]
    fields = replace(frame(), width=(Y,) * 3 + (Vector3(0, -1, 0),) * 3)
    patch = compose(edge, fields, checkpoint)
    assert certify(patch, checkpoint).status == "unresolved"
    assert magnitude(patch.jet(0.5, 0.5).around) <= 0.01


def test_coordinate_certificate_rejects_changed_world_geometry_under_the_same_frame() -> None:
    """
    A frame proof cannot certify unrelated homogeneous controls with matching metadata.
    """
    edge = build(partition(1, 0.75)[0], 0, 0.375)[0]
    patch = compose(edge, frame(), checkpoint)
    changed = tuple((p[0] + 100 * p[3], p[1], p[2], p[3]) for p in patch.rows[2])
    altered = replace(patch, rows=patch.rows[:2] + (changed,) + patch.rows[3:])
    with pytest.raises(ValueError, match="changed spatial control"):
        certify(altered, checkpoint)


def test_root_frame_motion_cannot_hide_a_bad_cap_approach() -> None:
    """
    A correct center tangent does not waive lateral boundary motion at the cap.
    """
    targets = inputs()[2]
    cap = bind_frame(targets, "end", targets.end, Vector3(-1, 0, 0))
    origin = cap.point(-0.375, 0)
    fields = FrameSpan(
        Fraction(0),
        Fraction(1),
        (origin, origin.translated(X, 3)),
        (Y, Vector3(0, 1, 1)),
        (Z,),
        ChartOrientation.POSITIVE,
    )
    patch = compose(build(partition(2, 0.75)[0], -0.375, 0.375)[0], fields, checkpoint)
    assert certify(patch, checkpoint).status == "certified"
    with pytest.raises(ValueError, match="boundary flow"):
        bind_root(patch, cap)


def test_frame_jacobian_cannot_certify_an_unqualified_section_map() -> None:
    """
    A regular ambient frame does not waive a reversing transverse boundary parameter.
    """
    profile = partition(1, 0.75)[0]
    first = profile.edges[0]
    bad_arc = replace(
        first.geometry, controls=(first.geometry.controls[0], (0, -2), first.geometry.controls[-1])
    )
    changed = replace(profile, edges=(replace(first, geometry=bad_arc),) + profile.edges[1:])
    patch = compose(build(changed, 0, 0.375)[0], frame(), checkpoint)
    proof = certify(patch, checkpoint)
    assert proof.minimum_signed_jacobian > 0
    assert proof.section_status == proof.status == "unresolved"
