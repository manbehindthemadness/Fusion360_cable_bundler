"""
Check exact original-ellipse continuity at vertical tangents against independent rational point pairs.
"""

from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from typing import Any

import pytest

from experiments.experiment_ribbon_complete.native_boundary_distance import ProfileGraph
from experiments.experiment_ribbon_complete.profile_conic import EllipseArc
from experiments.experiment_ribbon_complete.profile_continuity import ProfileContinuity
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def cap(shear: Fraction = Fraction(0), reverse: bool = False) -> EllipseArc:
    """
    Retain an exact unit-circle cap, optionally sheared in b or traversed in reverse, with one stationary-q endpoint.
    """
    controls = (
        (Fraction(1), Fraction(0)),
        (Fraction(1), Fraction(3, 4)),
        (Fraction(7, 25), Fraction(24, 25)),
    )
    data: Any = tuple((q, 2 * b + shear * q) for q, b in controls)
    if reverse:
        data = tuple(reversed(data))
    weights: Any = (1, Fraction(4, 5), 1)
    return EllipseArc(MaterialArc(data, weights, "cap"))


def point(conic: EllipseArc, parameter: Fraction) -> tuple[Fraction, Fraction]:
    """
    Evaluate independent exact rational points, without using the continuity certificate or conic square completion.
    """
    basis = ((1 - parameter) ** 2, 2 * parameter * (1 - parameter), parameter**2)
    factors = tuple(value * Fraction(weight) for value, weight in zip(basis, conic.arc.weights))
    coordinates = tuple(
        sum(Fraction(control[axis]) * value for control, value in zip(conic.arc.controls, factors))
        / sum(factors)
        for axis in range(2)
    )
    return coordinates[0], coordinates[1]


@pytest.mark.parametrize(
    "shear,reverse", [(Fraction(0), False), (Fraction(1, 4), False), (Fraction(-2), True)]
)
def test_stationary_endpoint_is_supported_without_a_finite_q_graph_slope(
    shear: Fraction, reverse: bool
) -> None:
    """
    All rational point pairs satisfy the bound, including the stationary endpoint and either material traversal.
    """
    conic = cap(shear, reverse)
    with pytest.raises(ValueError, match="certified monotone q"):
        ProfileGraph(conic, checkpoint)
    proof = ProfileContinuity(conic, checkpoint)
    assert proof.interval == (Fraction(7, 25), Fraction(1))
    assert proof.linear_coefficient == abs(shear)
    assert proof.radical_coefficient_mm == Fraction(8)
    points = [point(conic, Fraction(i, 16)) for i in range(17)]
    for first, second in combinations(points, 2):
        assert abs(first[1] - second[1]) <= proof.variation(abs(first[0] - second[0]))
    assert proof.variation(Fraction(0)) == Fraction(0)


def test_near_tip_variation_retains_the_square_root_rate_and_original_coordinates() -> None:
    """
    A finite linear rate cannot hide the true vertical tangent; the new bound retains it without moving the source.
    """
    conic = cap()
    proof = ProfileContinuity(conic, checkpoint)
    tip, close = point(conic, Fraction(0)), point(conic, Fraction(1, 1000000))
    dq, db = abs(tip[0] - close[0]), abs(tip[1] - close[1])
    assert db > 100000 * dq
    assert db <= proof.variation(dq)
    assert proof.conic is conic
    assert point(conic, Fraction(0)) == (Fraction(1), Fraction(0))
    assert proof.variation(Fraction(10)) == proof.variation(Fraction(18, 25))


def test_interior_q_turn_is_unresolved_rather_than_assigned_a_graph_branch() -> None:
    """
    A regular ellipse arc that turns inside the interval needs another chart, even when its endpoint q values coincide.
    """
    data: Any = (
        ((Fraction(4, 5), Fraction(-3, 5)), (Fraction(5, 4), 0), (Fraction(4, 5), Fraction(3, 5))),
        (1, Fraction(4, 5), 1),
        "turn",
    )
    with pytest.raises(ValueError, match="monotone original q"):
        ProfileContinuity(EllipseArc(MaterialArc(*data)), checkpoint)


@pytest.mark.parametrize("distance", [Fraction(-1), 0.1])
def test_distance_arguments_require_exact_nonnegative_physical_units(distance: Any) -> None:
    """
    Uncertainty arguments cannot be negative or silently reinterpreted from floating values.
    """
    proof = ProfileContinuity(cap(), checkpoint)
    with pytest.raises(ValueError, match="exact nonnegative"):
        proof.variation(distance)


def test_source_ownership_and_shared_resource_stop_are_preserved() -> None:
    """
    Coefficients are derived afresh from the original arc and work cannot bypass the caller's exhausted allocation.
    """
    conic = cap()
    renamed = EllipseArc(replace(conic.arc, label="other"))
    assert ProfileContinuity(renamed, checkpoint).conic is renamed

    def stop() -> None:
        """
        Refuse evaluation after the shared allocation stops.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        ProfileContinuity(conic, stop)
