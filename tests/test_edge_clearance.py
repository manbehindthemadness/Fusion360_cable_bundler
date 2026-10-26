"""
Exercise remote crossings,neighbor exclusion and interior width-segment contacts.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.edge_clearance import Ruling, rulings, screen
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve, EdgeCandidate
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _checkpoint() -> None:
    """
    Keep pure geometry tests independent of host resources.
    """


def _pair(gap: float, material_gap: float) -> tuple[Ruling, ...]:
    """
    Cross two complete width rulings in projection with controlled material gap.
    """
    return (
        Ruling(0, Vector3(-5, 0, 0), Vector3(5, 0, 0), Vector3(0, -5, 0), Vector3(0, 5, 0)),
        Ruling(
            1,
            Vector3(0, -5, gap),
            Vector3(0, 5, gap),
            Vector3(material_gap, -5, 0),
            Vector3(material_gap, 5, 0),
        ),
    )


@pytest.mark.parametrize(
    "gap,contact", [(0, True), (1, True), (1.5, False), (2, False), (4, False)]
)
def test_full_width_interior_contact_is_not_missed(gap: float, contact: bool) -> None:
    """
    Detect crossings far from all four endpoints and retain a measurable witness.
    """
    result = screen(_pair(gap, 20), 1.5, _checkpoint)
    assert result["contact_detected"] is contact
    assert result["pairs"] == 1
    if gap < 3:
        assert result["witness"]["distance_mm"] == pytest.approx(gap)
    else:
        assert result["witness"] is None


def test_material_neighbors_are_explicitly_excluded() -> None:
    """
    Suppress a local closest pair while disclosing the intentionally missing check.
    """
    result = screen(_pair(0.1, 2), 1.5, _checkpoint)
    assert not result["contact_detected"]
    assert result["local_pairs_excluded"] == 1
    assert result["eligible_near_pairs"] == 0


@pytest.mark.parametrize("thickness", [0, -1, float("nan"), float("inf")])
def test_invalid_thickness_rejects(thickness: float) -> None:
    """
    Reject invalid external dimensions before testing any pairs.
    """
    with pytest.raises(ValueError):
        screen(_pair(1, 20), thickness, _checkpoint)


@pytest.mark.parametrize("stations", [129, 257])
def test_unfolded_coordinates_match_exact_parabola_arc(stations: int) -> None:
    """
    Check Simpson integration against a closed-form arc and full physical width.
    """
    curve = BoundaryCurve(tuple(Vector3(100 * i / 7, 30 * i * (i - 1) / 42, 0) for i in range(8)))
    case = EndpointCase(
        "parabolic_sampling",
        Vector3(0, 0, 0),
        Vector3(100, 30, 0),
        Vector3(1, 0, 0),
        unit(Vector3(100, 60, 0)),
        Vector3(0, 0, 1),
        Vector3(0, 0, 1),
    )
    candidate = EdgeCandidate(case, curve, None, True, {})
    samples = rulings(candidate, stations, _checkpoint)
    expected = 0.5 * (math.sqrt(13600) + 10000 / 60 * math.asinh(0.6))
    assert samples[-1].flat_start.x == pytest.approx(expected, rel=0, abs=1e-7)
    half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    for sample in (samples[0], samples[len(samples) // 2], samples[-1]):
        assert magnitude(difference(sample.end, sample.start)) == pytest.approx(2 * half)
        assert sample.flat_end.x == pytest.approx(sample.flat_start.x)


def test_prior_rejection_cannot_be_promoted_by_clearance() -> None:
    """
    Refuse incomplete geometry before attempting the new diagnostic.
    """
    case = EndpointCase(
        "rejected",
        Vector3(0, 0, 0),
        Vector3(80, 0, 0),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
    )
    candidate = EdgeCandidate(case, None, None, False, {})
    with pytest.raises(ValueError, match="prior material compatibility"):
        rulings(candidate, 129, _checkpoint)
