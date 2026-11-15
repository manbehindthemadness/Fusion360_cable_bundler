"""
Verify continuous transverse boundary plans without claiming complete branch compliance.
"""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.profile_transition import build
from experiments.experiment_ribbon_complete.root_profiles import partition
from experiments.experiment_ribbon_complete.transition_certificate import certify
from tests.test_ribbon_complete_lengths import checkpoint


@pytest.mark.parametrize("lines", (1, 2, 5, 10))
def test_original_roots_and_round_terminations_have_continuous_orientation_certificate(
    lines: int,
) -> None:
    """
    Preserve every original edge and certify positive chart weights/orientation for the whole morph.
    """
    diameter = 0.75
    for profile in partition(lines, diameter):
        center = (profile.pin_number - (lines + 1) / 2) * diameter
        edges = build(profile, center, diameter / 2)
        for edge in edges:
            proof = certify(edge, checkpoint)
            assert proof.status == "certified"
            assert proof.minimum_weight > 0 and proof.minimum_clockwise_numerator > 0
            assert 0 <= proof.terminal_radius_error_mm <= Fraction(1, 100)
            for v in (0, 0.125, 0.5, 0.875, 1):
                root = edge.jet(0, v)
                q, b = edge.source.geometry.point(v)
                assert (root.point[0] + center, root.point[1]) == pytest.approx(
                    (q, b), abs=0.01, rel=0
                )
                final = edge.jet(1, v)
                assert math.hypot(*final.point) == pytest.approx(diameter / 2, abs=0.01, rel=0)
                assert root.longitudinal == root.longitudinal_second == (0, 0)
                assert final.longitudinal == final.longitudinal_second == (0, 0)


def test_profile_seams_share_the_same_continuous_material_coordinate() -> None:
    """
    Exact shared chart endpoints remain joined throughout the morph, not only at the caps.
    """
    profile = partition(5, 0.75)[0]
    edges = build(profile, -1.5, 0.375)
    for first, second in zip(edges, edges[1:] + edges[:1]):
        for u in (0, 0.1, 0.5, 0.9, 1):
            assert first.jet(u, 1).point == second.jet(u, 0).point
            assert first.jet(u, 1).longitudinal == second.jet(u, 0).longitudinal


def test_longitudinal_jets_describe_actual_rational_shape_motion() -> None:
    """
    Quotient derivatives agree with independent geometric finite differences at the user accuracy.
    """
    edge = build(partition(2, 10)[0], -5, 5)[0]
    u, v, step = 0.37, 0.42, 0.001
    middle = edge.jet(u, v)
    before, after = edge.jet(u - step, v), edge.jet(u + step, v)
    first = tuple((b - a) / (2 * step) for a, b in zip(before.point, after.point))
    second = tuple(
        (a - 2 * b + c) / step**2 for a, b, c in zip(before.point, middle.point, after.point)
    )
    assert middle.longitudinal == pytest.approx(first, abs=0.01, rel=0)
    assert middle.longitudinal_second == pytest.approx(second, abs=0.01, rel=0)
    assert any(abs(x) > 0.01 for x in middle.longitudinal)


def test_certificate_cannot_ignore_a_changed_interior_control_row() -> None:
    """
    Endpoint-only data cannot certify a different surface hidden between the caps.
    """
    edge = build(partition(1, 0.75)[0], 0, 0.375)[0]
    changed = tuple((x + 1, y, w) for x, y, w in edge.rows[1])
    with pytest.raises(ValueError, match="provenance-matched"):
        replace(edge, rows=(edge.rows[0], changed) + edge.rows[2:])


def test_unclosed_root_chart_is_not_silently_repaired() -> None:
    """
    A missing root edge stays an invalid plan rather than being bridged or snapped.
    """
    profile = partition(2, 0.75)[0]
    with pytest.raises(ValueError, match="shared chart vertices"):
        build(replace(profile, edges=profile.edges[:-1]), -0.375, 0.375)
