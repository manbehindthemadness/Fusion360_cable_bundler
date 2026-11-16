"""
Check whole-bend source ownership and global reference/gradient separation certificates.
"""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction

import pytest

from artifacts.verification.resume3216.basis import Basis
from artifacts.verification.resume3216.field import Midsurface, build
from artifacts.verification.resume3216.spline import Spline, interpolate, linear
from artifacts.verification.resume3218.profile import Fields, prepare
from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_complete.c2_material import prepare as midplane
from experiments.experiment_ribbon_complete.scalar_reference import enclose as scalar_reference
from experiments.experiment_ribbon_complete.volume_field import BendVolume
from experiments.experiment_ribbon_complete.volume_injectivity import audit
from experiments.experiment_ribbon_complete.volume_regularity import enclose as local_bounds
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose


def checkpoint() -> None:
    """
    Leave the small analytical test domains independent of wall-clock assumptions.
    """


def test_small_value_error_cannot_hide_a_large_first_derivative_error() -> None:
    """
    A constant zero path approximates sine on a tiny interval but has the wrong derivative.
    """
    width = Fraction(1, 1000000)
    zero, one = (Fraction(0),) * 6, (Fraction(1),) * 6
    phase = tuple(width * i / 5 for i in range(6))
    bound = scalar_reference(zero, one, phase, Fraction(0), width, checkpoint)
    assert bound.sine < Fraction(1, 100000)
    assert bound.sine_first >= Fraction(99, 100)
    assert bound.phase_first == Fraction(0)


def candidate(shear: bool = False) -> BendVolume:
    """
    Author one small cylinder reference under a fixed nonsingular frame without solving endpoints.
    """
    pose = Pose(Vector3(1, 2, 3), Vector3(1, 0, 0), Vector3(0.25 if shear else 0, 1, 0))
    fold = CylindricalFold(2.0, 0.1, 0.2, 1.65, 0.5, 0.5)
    piece = PlacedPiece(pose, fold, "analytical only")
    budget = NativeBudget(maximum_seconds=10, maximum_rss_kib=4194304)
    fields = prepare(piece, budget)
    surface = build(fold, pose, 0.825, fields.sine, fields.cosine, fields.phase, budget)
    source = midplane(surface, Fraction(0.825), "analytical cylinder", checkpoint)
    return BendVolume(
        source,
        fields,
        Fraction(2),
        Fraction(1, 4),
        Fraction(math.cos(0.2)),
        Fraction(math.sin(0.2)),
        1,
        tuple(map(Fraction, (1, 2, 3))),
        tuple(map(Fraction, (1, 0, 0))),
        (Fraction(1, 4) if shear else Fraction(0), Fraction(1), Fraction(0)),
        Fraction(1, 2),
    )


@pytest.mark.parametrize("shear", (False, True))
def test_entire_cylinder_and_sheared_frame_are_globally_certified(shear: bool) -> None:
    """
    Full source intervals, not independent positive Jacobians or sampled points, support the result.
    """
    volume = candidate(shear)
    result = audit(volume, checkpoint)
    assert result.volume is volume and result.status == "certified_bend_global_injectivity"
    assert result.separation_lower is not None and result.separation_lower > Fraction(0)
    assert len(result.spans) == len(volume.source.spans)
    assert all(type(x) is Fraction for span in result.spans for row in span.entries for x in row)


def test_changed_world_field_cannot_inherit_the_reference_certificate() -> None:
    """
    Collapsing the longitudinal field preserves metadata but loses the global gradient margin.
    """
    volume = candidate()
    changed = Midsurface(
        volume.source.surface.basis,
        (volume.source.surface.rows[0],) * volume.source.surface.basis.count,
    )
    source = midplane(changed, volume.source.half_mm, "collapsed source", checkpoint)
    result = audit(replace(volume, source=source), checkpoint)
    assert result.status == "unresolved_gradient_margin"


def test_stale_basis_wrapped_domain_and_inverted_reference_are_not_accepted() -> None:
    """
    Discrete source ownership rejects; unsupported references stay unresolved rather than infeasible.
    """
    volume = candidate()
    clone = Basis(volume.source.surface.basis.breaks)
    stale = replace(volume.fields, sine=Spline(clone, volume.fields.sine.controls))
    with pytest.raises(ValueError, match="SAME original"):
        replace(volume, fields=stale)
    assert (
        audit(replace(volume, half_thickness_mm=Fraction(3)), checkpoint).status
        == "unresolved_reference_domain"
    )
    basis = Basis((Fraction(0), Fraction(7)))
    surface = Midsurface(basis, volume.source.surface.rows[:6])
    source = midplane(surface, volume.source.half_mm, "wrapped domain", checkpoint)
    fields = Fields(
        *(
            Spline(basis, curve.controls[:6])
            for curve in (volume.fields.sine, volume.fields.cosine, volume.fields.phase)
        )
    )
    assert (
        audit(replace(volume, source=source, fields=fields), checkpoint).status
        == "unresolved_reference_domain"
    )


def test_caller_resource_stop_propagates_without_partial_success() -> None:
    """
    No global certificate is returned after a shared allocation stops.
    """

    def stop() -> None:
        """
        Model the caller's exhausted allocation.
        """
        raise RuntimeError("global source allocation exhausted")

    with pytest.raises(RuntimeError, match="global source allocation"):
        audit(candidate(), stop)


def test_closed_return_with_positive_local_jacobians_cannot_inherit_global_injectivity() -> None:
    """
    A complete polynomial loop has coincident caps despite certified positive local volume Jacobians.
    """
    basis = Basis(tuple(Fraction(i, 4) for i in range(5)))
    values = ((0, 1), (1, 0), (0, -1), (-1, 0), (0, 1))
    budget = NativeBudget(maximum_seconds=10, maximum_rss_kib=4194304)
    sine = interpolate(
        basis, tuple((Fraction(s), Fraction(6 * c), Fraction(-36 * s)) for s, c in values), budget
    )
    cosine = interpolate(
        basis, tuple((Fraction(c), Fraction(-6 * s), Fraction(-36 * c)) for s, c in values), budget
    )
    surface = Midsurface(
        basis,
        tuple(
            tuple(Vector3(float(s), float(q), float(1 - c)) for q in (-1, 0, 1))
            for s, c in zip(sine.controls, cosine.controls)
        ),
    )
    volume = BendVolume(
        midplane(surface, Fraction(1), "closed return analytical control", checkpoint),
        Fields(sine, cosine, linear(basis)),
        Fraction(1),
        Fraction(1, 10),
        Fraction(1),
        Fraction(0),
        1,
        (Fraction(0),) * 3,
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        Fraction(0),
    )
    assert (
        surface.jet(Fraction(0), Fraction(1, 2)).point
        == surface.jet(Fraction(1), Fraction(1, 2)).point
    )
    for index in range(4):
        proof = local_bounds(
            volume.span(index), Fraction(1, 10), Fraction(1), Fraction(1), Fraction(0), checkpoint
        )
        assert proof.status == "certified_local_jacobian_and_conditioning"
    assert audit(volume, checkpoint).status == "unresolved_gradient_margin"
