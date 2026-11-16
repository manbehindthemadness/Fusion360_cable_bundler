"""
Verify exact volume/profile composition and continuous outgoing-control correspondence.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from math import comb

import pytest

from artifacts.verification.resume3216.basis import Basis
from artifacts.verification.resume3216.field import Midsurface
from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.c2_material import prepare
from experiments.experiment_ribbon_complete.volume_boundary import VolumeSpan, boundary, enclose
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc


def checkpoint() -> None:
    """
    Leave these fixed analytical examples independent of timing assumptions.
    """


def volume(nonaffine: bool = False) -> VolumeSpan:
    """
    Retain exact stored affine or genuinely quadratic transverse world controls.
    """
    surface = Midsurface(
        Basis((Fraction(0), Fraction(1))),
        tuple(
            tuple(Vector3(float(i), float(q), float(nonaffine and q != 0)) for q in (-2, 0, 2))
            for i in range(6)
        ),
    )
    source = prepare(surface, Fraction(2), "unit original field", checkpoint)
    return VolumeSpan(source, 0, ((Fraction(0), Fraction(0), Fraction(1)),) * 6)


def arc() -> MaterialArc:
    """
    Keep a rational quadratic with a nonunit interior weight.
    """
    return MaterialArc(((-1.0, 0.0), (0.0, 1.0), (1.0, 0.0)), (1.0, 0.75, 1.0), "unit")


def evaluate(values: tuple[tuple[Fraction, ...], ...], t: Fraction) -> tuple[Fraction, ...]:
    """
    Evaluate with an independent explicit binomial Bernstein sum.
    """
    degree = len(values) - 1
    return tuple(
        sum(
            (p[k] * comb(degree, i) * t**i * (1 - t) ** (degree - i) for i, p in enumerate(values)),
            Fraction(0),
        )
        for k in range(len(values[0]))
    )


def test_affine_volume_has_identical_rational_outgoing_boundary() -> None:
    """
    Algebraic degree elevation preserves every outgoing position without approximation.
    """
    field, profile = volume(), arc()
    outgoing = tuple(
        tuple((row[0][0], Fraction(q), Fraction(b)) for q, b in profile.controls)
        for row in field.source.spans[0]
    )
    receipt = enclose(field, profile, outgoing, checkpoint)
    assert receipt.upper_mm == Fraction(0)
    assert (
        receipt.volume is field and receipt.arc is profile and receipt.outgoing_controls is outgoing
    )


def test_quadratic_midplane_terms_survive_rational_profile_composition() -> None:
    """
    Direct source evaluation agrees with the degree-four homogeneous composition.
    """
    field, profile = volume(True), arc()
    net = boundary(field, profile)
    u, v = Fraction(2, 7), Fraction(3, 11)
    weights = tuple(Fraction(w) for w in profile.weights)
    source_profile = tuple(
        (Fraction(q) * w, Fraction(b) * w, w) for (q, b), w in zip(profile.controls, weights)
    )
    qh, bh, w = evaluate(source_profile, v)
    q, b = qh / w, bh / w
    midpoint = evaluate(tuple(evaluate(row, (q / 2 + 1) / 2) for row in field.source.spans[0]), u)
    homogeneous = evaluate(tuple(evaluate(row, v) for row in net), u)
    actual = tuple(x / homogeneous[3] for x in homogeneous[:3])
    assert actual == (midpoint[0], midpoint[1], midpoint[2] + b)


def test_changed_thickness_field_is_not_hidden_by_midplane_identity() -> None:
    """
    A zero thickness direction preserves b0 but visibly disagrees with the outgoing boundary.
    """
    field, profile = volume(), arc()
    outgoing = tuple(
        tuple((row[0][0], Fraction(q), Fraction(b)) for q, b in profile.controls)
        for row in field.source.spans[0]
    )
    collapsed = replace(field, normal=((Fraction(0),) * 3,) * 6)
    assert enclose(collapsed, profile, outgoing, checkpoint).upper_mm > Fraction(1, 100)


def test_invalid_span_weights_and_missing_outgoing_controls_reject() -> None:
    """
    Incomplete correspondence never becomes an empty successful bound.
    """
    field, profile = volume(), arc()
    with pytest.raises(ValueError, match="original midplane"):
        replace(field, index=1)
    with pytest.raises(ValueError, match="positive-weight"):
        boundary(field, replace(profile, weights=(1.0, 0.0, 1.0)))
    with pytest.raises(ValueError, match="Complete exact outgoing"):
        enclose(field, profile, (), checkpoint)
