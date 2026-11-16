"""
Exercise canonical-map contact support without importing analytic-fold witnesses.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.contact_cell import enclose, separated, upper
from experiments.experiment_ribbon_complete.contact_profile_cover import certify
from experiments.experiment_ribbon_complete.flat_chart import MaterialCut, straight
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_flat_chart import piece
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


def box(low: float = 0.0, high: float = 0.1) -> Cell:
    """
    Keep physical width/thickness bounds inside the analytical cylinder's owner.
    """
    return Cell(0, Span(low, high), Span(-0.8, 0.8), Span(-0.2, 0.2))


def test_affine_map_and_float_conversion_are_enclosed_separately() -> None:
    """
    Exact affine geometry needs no curvature remainder; conversion remains charged.
    """
    chart = straight(piece())
    proof = enclose(chart, box(0, 2), checkpoint)
    assert proof.region is chart and proof.residual_mm == Fraction(0)
    assert proof.model.error == 0
    changed = replace(chart, origin=(Fraction(1, 3), Fraction(0), Fraction(0)))
    rounded = enclose(changed, box(0, 2), checkpoint)
    assert rounded.residual_mm == Fraction(0)
    assert (
        Fraction(rounded.model.error) >= abs(Fraction(1, 3) - Fraction(rounded.model.origin.x)) > 0
    )


@pytest.mark.parametrize("low,high", ((0.0, 0.1), (0.03125, 0.0625), (0.05, 0.05)))
def test_actual_multispan_bend_is_inside_whole_cell_residual(low: float, high: float) -> None:
    """
    Independent exact evaluations check interior, endpoint and collapsed-face behavior.
    """
    volume = candidate(True)
    proof = enclose(volume, box(low, high), checkpoint)
    assert proof.region is volume and proof.residual_mm >= 0
    for t in (Fraction(0), Fraction(1, 3), Fraction(1)):
        u = Fraction(low) + (Fraction(high) - Fraction(low)) * t
        for q in (Fraction(-0.8), Fraction(1, 7), Fraction(0.8)):
            jet = volume.source.surface.jet(u, (q / volume.source.half_mm + 1) / 2)
            for b in (Fraction(-0.2), Fraction(1, 13), Fraction(0.2)):
                actual = tuple(jet.point[k] + b * volume.normals[k].jet(u)[0] for k in range(3))
                residual = sum(
                    abs(
                        actual[k]
                        - proof.origin[k]
                        - sum(c[k] * x for c, x in zip(proof.columns, (u, q, b)))
                    )
                    for k in range(3)
                )
                assert residual <= proof.residual_mm


def test_support_proves_separation_but_never_clears_overlapping_interiors() -> None:
    """
    Identical owners overlap, while a translated flat has a strict full-profile gap.
    """
    first = enclose(straight(piece()), box(0, 2), checkpoint)
    remote = enclose(straight(piece(4)), box(0, 2), checkpoint)
    profile = certify(material_profile(2, 0.75), 2, 0.75, checkpoint)
    normal, anchor = Vector3(1, 0, 0), Vector3(0, 0, 0)
    assert separated(first, remote, profile, normal, anchor)
    assert not separated(first, first, profile, normal, anchor)
    assert not separated(first, remote, profile, Vector3(0, 0, 0), anchor)
    with pytest.raises(ValueError, match="support cover"):
        separated(first, remote, replace(profile, status="unresolved"), normal, anchor)


def test_invalid_domain_and_exhausted_allocation_cannot_return_a_model() -> None:
    """
    No clamping, source replacement or separate work pool hides unsupported input.
    """
    volume = candidate()
    for cell in (box(-0.1, 0.1), box(0, 0.2), box(float("nan"), 0.1)):
        with pytest.raises(ValueError):
            enclose(volume, cell, checkpoint)

    def stop() -> None:
        """
        Propagate the caller's exhausted shared resource allocation unchanged.
        """
        raise RuntimeError("shared allocation exhausted")

    with pytest.raises(RuntimeError, match="shared allocation"):
        enclose(volume, box(), stop)


def test_both_slanted_cuts_bound_support_without_changing_the_map() -> None:
    """
    The exact correlated coordinate s-q lies in [2,3] despite a much wider s box.
    """
    chart = replace(
        straight(piece()),
        low=MaterialCut(Fraction(2), Fraction(1)),
        high=MaterialCut(Fraction(3), Fraction(1)),
    )
    model = enclose(chart, box(0, 4), checkpoint)
    profile = certify(material_profile(2, 0.75), 2, 0.75, checkpoint)
    anchor = Vector3(0, 0, 0)
    lower = upper(model, profile, Vector3(-1, 1.25, 0), anchor)
    higher = upper(model, profile, Vector3(1, -1.25, 0), anchor)
    assert lower is not None and -2 <= lower < -2 + 1e-12
    assert higher is not None and 3 <= higher < 3 + 1e-12
    assert not separated(model, model, profile, Vector3(1, -1.25, 0), anchor)
    assert model.region is chart and model.residual_mm == Fraction(0)


def test_only_a_strictly_empty_cut_box_is_discarded() -> None:
    """
    Outside boxes are empty; an included cap face remains occupied and cannot clear itself.
    """
    chart = straight(piece())
    profile = certify(material_profile(2, 0.75), 2, 0.75, checkpoint)
    anchor, normal = Vector3(0, 0, 0), Vector3(1, 0, 0)
    empty = enclose(chart, box(-2, -1), checkpoint)
    assert upper(empty, profile, normal, anchor) == float("-inf")
    face = enclose(chart, box(0, 0), checkpoint)
    assert not separated(face, face, profile, normal, anchor)
