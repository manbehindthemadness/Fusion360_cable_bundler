"""
Distinguish exact cap correspondence and bounded overlap from accepted contact.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.contact_flat_junction import certify_flat_cap
from experiments.experiment_ribbon_complete.flat_chart import straight
from tests.test_ribbon_complete_flat_chart import piece
from tests.test_ribbon_complete_volume_injectivity import checkpoint


@pytest.mark.parametrize("overlap", (Fraction(0), Fraction(1, 200)))
def test_exact_or_small_overlap_retains_both_collar_bounds_without_contact_acceptance(
    overlap: Fraction,
) -> None:
    """
    A real small overlap is measured as a collar, never silently classified as separation.
    """
    first = straight(piece())
    second = replace(straight(piece(2)), origin=(Fraction(2) - overlap, Fraction(0), Fraction(0)))
    result = certify_flat_cap(first, second, Fraction(1), Fraction(1, 4), checkpoint)
    assert result.first is first and result.second is second
    assert result.status == "certified_material_cap_collar"
    assert result.cap_position_upper_mm == overlap
    assert result.collars_mm == (overlap, overlap)
    assert "separated" not in result.status and "contact" not in result.status


def test_wide_mismatch_and_reversed_approach_are_unresolved() -> None:
    """
    Neither coincident caps nor an arbitrary dimensional bound can excuse wrong material flow.
    """
    first, second = straight(piece()), straight(piece(2.1))
    assert (
        certify_flat_cap(first, second, Fraction(1), Fraction(1, 4), checkpoint).status
        == "unresolved_cap_correspondence"
    )
    second = straight(piece(2))
    reversed_flow = replace(
        second, columns=(tuple(-x for x in second.columns[0]), second.columns[1], second.columns[2])
    )
    assert (
        certify_flat_cap(first, reversed_flow, Fraction(1), Fraction(1, 4), checkpoint).status
        == "unresolved_flat_cap_progress"
    )


def test_section_bounds_and_resource_stops_cannot_be_guessed() -> None:
    """
    The caller supplies exact complete-section coverage and retains resource ownership.
    """
    first, second = straight(piece()), straight(piece(2))
    with pytest.raises(ValueError, match="positive physical"):
        certify_flat_cap(first, second, Fraction(0), Fraction(1, 4), checkpoint)

    def stop() -> None:
        """
        Stop before any cap evidence is issued.
        """
        raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        certify_flat_cap(first, second, Fraction(1), Fraction(1, 4), stop)
