"""
Challenge the exact trim-domain certificate without Fusion or relaxed distance gates.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_joint_route.trim import rectangular_interior

SIDES = (((1.0, 0.0), (1.0, 1.0)), ((1.0, 1.0), (0.0, 1.0)), ((0.0, 1.0), (0.0, 0.0)))


def test_collapsed_tip_completes_actual_three_sided_parameter_boundary() -> None:
    """
    Certify the observed strict interior only with a separately proved collapsed side.
    """
    assert rectangular_interior((0, 1, 0, 1), SIDES, frozenset({"v0"}), (0.5, 0.03))
    assert not rectangular_interior((0, 1, 0, 1), SIDES, frozenset(), (0.5, 0.03))
    assert not rectangular_interior((0, 1, 0, 1), SIDES, frozenset({"u0"}), (0.5, 0.03))


@pytest.mark.parametrize(
    "point", [(0.5, -0.01), (0.5, 0.0), (0.5, 1.0), (1.01, 0.03), (0.0, 0.03), (0.5, 1e-10)]
)
def test_outside_or_boundary_queries_do_not_receive_an_interior_certificate(
    point: tuple[float, float],
) -> None:
    """
    Refuse to replace uncertain boundary classification with a permissive near-edge test.
    """
    assert not rectangular_interior((0, 1, 0, 1), SIDES, frozenset({"v0"}), point)


def test_partial_or_duplicate_sides_never_certify_the_rectangle() -> None:
    """
    Reject an incomplete or differently trimmed face even when the query looks central.
    """
    partial = (((1.0, 0.0), (1.0, 0.7)),) + SIDES[1:]
    assert not rectangular_interior((0, 1, 0, 1), partial, frozenset({"v0"}), (0.5, 0.03))
    assert not rectangular_interior(
        (0, 1, 0, 1), (SIDES[0], SIDES[0], SIDES[2]), frozenset({"v0"}), (0.5, 0.03)
    )


def test_parameter_scale_and_curve_direction_do_not_change_membership() -> None:
    """
    Preserve the certificate under UV scaling and reversal of coedge curve direction.
    """
    scaled = tuple(((a[0] * 3, a[1] * 2), (b[0] * 3, b[1] * 2)) for b, a in SIDES)
    assert rectangular_interior((0, 3, 0, 2), scaled, frozenset({"v0"}), (1.5, 0.06))


def test_full_rectangle_needs_no_collapsed_side_exception() -> None:
    """
    Retain ordinary four-boundary support with the same strict interior requirement.
    """
    full = SIDES + (((0.0, 0.0), (1.0, 0.0)),)
    assert rectangular_interior((0, 1, 0, 1), full, frozenset(), (0.5, 0.5))
