"""
Check whole-profile support compatibility and reject unproved substitutions.
"""

from dataclasses import replace

import pytest

from experiments.experiment_ribbon_complete.contact_profile_cover import certify
from experiments.experiment_ribbon_fold_route.material_profile import material_profile


def checkpoint() -> None:
    """
    Complete a bounded analytical checkpoint without external resources.
    """


@pytest.mark.parametrize("lines", (1, 2, 5, 10))
def test_original_filled_profile_has_positive_support_cover(lines: int) -> None:
    """
    Original rational boundaries retain ownership and cover both filled halves.
    """
    arcs = material_profile(lines, 0.75)
    proof = certify(arcs, lines, 0.75, checkpoint)
    assert proof.status == "certified_positive_support_cover"
    assert proof.arcs is arcs
    assert len(proof.disk_indices) == len(arcs)


def test_outward_curve_cannot_inherit_original_disk_support() -> None:
    """
    Closed endpoints do not excuse an interior bulge outside the original support.
    """
    arcs = material_profile(2, 0.75)
    first = arcs[0]
    altered = replace(
        first, controls=(first.controls[0], (first.controls[1][0], 2.0), first.controls[2])
    )
    assert certify((altered,) + arcs[1:], 2, 0.75, checkpoint).status == "unresolved_disk_cover"


def test_missing_boundary_is_not_a_filled_section() -> None:
    """
    Omitting an arc leaves an open contour and cannot establish section coverage.
    """
    assert (
        certify(material_profile(2, 0.75)[1:], 2, 0.75, checkpoint).status
        == "unresolved_open_outline"
    )


def test_nonpositive_rational_weight_rejects_before_support() -> None:
    """
    Convex-hull support cannot be reused when positive weights are absent.
    """
    arcs = material_profile(2, 0.75)
    with pytest.raises(ValueError, match="positive-weight"):
        certify((replace(arcs[0], weights=(1.0, 0.0, 1.0)),) + arcs[1:], 2, 0.75, checkpoint)
