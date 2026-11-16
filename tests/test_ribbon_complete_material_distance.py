"""
Verify common material-distance metrics, including staggered bends and hidden local stretch.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.material_distance import DistanceSpan, enclose, measure


def checkpoint() -> None:
    """
    Leave these bounded exact examples independent of runtime scheduling.
    """


def line(low: Fraction, high: Fraction, speed: Fraction = Fraction(1)) -> DistanceSpan:
    """
    Place a line with explicitly chosen spatial speed on a material interval.
    """
    return DistanceSpan(
        low,
        high,
        ((low * speed, Fraction(0), Fraction(0)), (high * speed, Fraction(0), Fraction(0))),
    )


def test_staggered_partitions_share_material_increments_without_matching_knots() -> None:
    """
    Distinct crease-entry locations do not require comparing equal local phase.
    """
    length = Fraction(3)
    for split in (Fraction(1, 4), Fraction(7, 4)):
        audit = measure((line(Fraction(0), split), line(split, length)), length, checkpoint)
        assert audit.upper_mm == Fraction(0)
        assert audit.seam_gaps_upper_mm == (Fraction(0),)


def test_equal_phase_speed_does_not_prove_equal_material_speed() -> None:
    """
    The same spatial line can have an incompatible material interval assignment.
    """
    first = line(Fraction(0), Fraction(1))
    wrong = DistanceSpan(Fraction(0), Fraction(2), first.controls)
    assert enclose(first, checkpoint).upper_mm == Fraction(0)
    assert enclose(wrong, checkpoint).upper_mm == Fraction(1)


def test_local_extension_and_contraction_do_not_cancel() -> None:
    """
    Equal full path lengths retain the sum of opposing local increment errors.
    """
    zero = Fraction(0)
    first = DistanceSpan(zero, Fraction(1), ((zero, zero, zero), (Fraction(3, 2), zero, zero)))
    last = DistanceSpan(
        Fraction(1), Fraction(2), ((Fraction(3, 2), zero, zero), (Fraction(2), zero, zero))
    )
    result = measure((first, last), Fraction(2), checkpoint)
    assert result.upper_mm == Fraction(1)


def test_stationary_space_and_missing_domains_cannot_inherit_a_unit_speed_pass() -> None:
    """
    Degenerate spatial controls still have a positive measured discrepancy; absent coverage rejects.
    """
    zero = (Fraction(0),) * 3
    assert enclose(
        DistanceSpan(Fraction(0), Fraction(2), (zero, zero)), checkpoint
    ).upper_mm == Fraction(2)
    with pytest.raises(ValueError, match="complete ordered"):
        measure((line(Fraction(1), Fraction(2)),), Fraction(2), checkpoint)


def test_source_seam_gap_remains_visible_and_shared_work_stops_propagate() -> None:
    """
    Metric success cannot silently certify a discontinuous source or renew its allocation.
    """
    first = line(Fraction(0), Fraction(1))
    second = DistanceSpan(
        Fraction(1),
        Fraction(2),
        ((Fraction(2), Fraction(0), Fraction(0)), (Fraction(3), Fraction(0), Fraction(0))),
    )
    result = measure((first, second), Fraction(2), checkpoint)
    assert result.upper_mm == Fraction(0) and result.seam_gaps_upper_mm == (Fraction(1),)

    def stop() -> None:
        """
        Model an exhausted caller allocation without granting a replacement.
        """
        raise RuntimeError("shared allocation exhausted")

    with pytest.raises(RuntimeError, match="shared allocation"):
        enclose(first, stop)


@pytest.mark.parametrize("degree", (2, 5))
def test_curved_polynomial_bound_preserves_the_same_world_curve_at_different_degrees(
    degree: int,
) -> None:
    """
    The exact curve (t,t²,0) has squared speed1+4t² and a conservative bound2.
    """
    controls = tuple(
        (Fraction(i, degree), Fraction(i * (i - 1), degree * (degree - 1)), Fraction(0))
        for i in range(degree + 1)
    )
    bound = enclose(DistanceSpan(Fraction(0), Fraction(1), controls), checkpoint)
    assert bound.upper_mm == Fraction(2)


def test_inconclusive_squared_speed_lower_bound_preserves_a_valid_enclosure() -> None:
    """
    A reversing curve has negative Bernstein speed-square controls and receives no invented floor.
    """
    zero = Fraction(0)
    controls = ((zero, zero, zero), (Fraction(-1, 2), zero, zero), (zero, zero, zero))
    bound = enclose(DistanceSpan(zero, Fraction(1), controls), checkpoint)
    assert bound.squared_speed_residual == (Fraction(0), Fraction(-2), Fraction(0))
    assert bound.upper_mm == Fraction(2)
