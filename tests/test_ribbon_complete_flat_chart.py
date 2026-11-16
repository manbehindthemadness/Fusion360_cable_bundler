"""
Verify physical flat coordinates and cap correspondence without normalized-lead singularities.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.flat_chart import (
    FlatChart,
    FlatRegion,
    MaterialCut,
    certify,
    lead,
    straight,
)
from experiments.experiment_ribbon_complete.flat_correspondence import (
    bend_cap_bound,
    consecutive_cap_bound,
)
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


def piece(origin: float = 0) -> PlacedPiece:
    """
    Keep a straight analytical piece with an explicitly sheared, nonsingular frame.
    """
    return PlacedPiece(
        Pose(Vector3(origin, 0, 0), Vector3(1, 0, 0), Vector3(0.25, 1, 0)),
        Straight(2),
        "unit straight",
    )


def test_exact_material_inverse_retains_same_chart_identity() -> None:
    """
    A nonsingular shear round-trips physical coordinates; an equal clone cannot inherit its proof.
    """
    chart = straight(piece())
    proof = certify(chart)
    coordinates = (Fraction(1, 3), Fraction(-2, 7), Fraction(1, 5))
    assert proof.status == "certified_affine_material_chart"
    assert chart.coordinates(chart.point(*coordinates), proof) == coordinates
    with pytest.raises(ValueError, match="SAME original"):
        replace(chart).coordinates(chart.point(*coordinates), proof)


def test_zero_lead_tip_does_not_make_physical_coordinates_singular() -> None:
    """
    At q=1 the longitudinal domain collapses to s=0, while the physical coordinate frame remains valid.
    """
    zero, one = Fraction(0), Fraction(1)
    chart = FlatChart(
        candidate(),
        FlatRegion.BEFORE,
        (zero,) * 3,
        ((one, zero, zero), (zero, one, zero), (zero, zero, one)),
        MaterialCut(zero),
        MaterialCut(one, -one),
    )
    assert chart.high.at(one) == chart.low.at(one) == zero
    proof = certify(chart)
    assert proof.condition_upper == one
    assert chart.coordinates(chart.point(zero, one, zero), proof) == (zero, one, zero)


@pytest.mark.parametrize("region", (FlatRegion.BEFORE, FlatRegion.AFTER))
def test_original_bend_labels_match_full_flat_shared_cap(region: FlatRegion) -> None:
    """
    Captured midplane/normal coefficients and analytic flat continuation agree to dimensional accuracy.
    """
    chart = lead(candidate(), region, Fraction(2))
    assert certify(chart).status == "certified_affine_material_chart"
    assert max(
        bend_cap_bound(chart, arc, checkpoint) for arc in material_profile(2, 0.75)
    ) <= Fraction(1, 100)


def test_consecutive_material_caps_keep_profile_labels_and_expose_position_gaps() -> None:
    """
    Position coincidence on original labels is measured without exempting neighboring interiors.
    """
    first, second, gap = straight(piece()), straight(piece(2)), straight(piece(3))
    for arc in material_profile(2, 0.75):
        assert consecutive_cap_bound(first, second, arc) == Fraction(0)
        assert consecutive_cap_bound(first, gap, arc) == Fraction(1)


def test_singular_material_frame_cannot_generate_certified_coordinates() -> None:
    """
    A collapsed cross-section remains unresolved despite any zero-length domain boundary.
    """
    chart = straight(piece())
    bad = replace(chart, columns=(chart.columns[0], chart.columns[0], (Fraction(0),) * 3))
    proof = certify(bad)
    assert proof.status == "unresolved" and proof.frame.rows is None
    with pytest.raises(ValueError, match="certified proof"):
        bad.coordinates((Fraction(0),) * 3, proof)


def test_absent_original_source_cannot_inherit_an_affine_coordinate_chart() -> None:
    """
    An otherwise invertible matrix does not replace the original material source identity.
    """
    invalid_metadata: dict[str, Any] = {"source": None}
    with pytest.raises(ValueError, match="source identity"):
        replace(straight(piece()), **invalid_metadata)
