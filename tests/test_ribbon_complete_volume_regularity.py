"""
Check full-thickness local material validity independently of boundary closeness.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from artifacts.verification.resume3216.basis import Basis
from artifacts.verification.resume3216.field import Midsurface
from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.c2_material import prepare
from experiments.experiment_ribbon_complete.volume_boundary import VolumeSpan
from experiments.experiment_ribbon_complete.volume_regularity import coupled_condition, enclose
from tests.test_ribbon_complete_volume_boundary import checkpoint, volume


def rotated_anisotropic_volume() -> VolumeSpan:
    """
    Rotate diag(1/440,1,1) by a fixed rational orthogonal matrix with nonzero cofactors.

    Its infinity-norm condition is approximately978, while separately bounding
    cofactor products loses cancellations and exceeds1024. Rounded stored world
    controls are retained, as in captured fields; there is no curve fitting.
    """
    columns = (
        (Fraction(1, 3), Fraction(2, 3), Fraction(-2, 3)),
        (Fraction(2, 3), Fraction(1, 3), Fraction(2, 3)),
        (Fraction(2, 3), Fraction(-2, 3), Fraction(-1, 3)),
    )
    surface = Midsurface(
        Basis((Fraction(0), Fraction(1))),
        tuple(
            tuple(
                Vector3(
                    *(float(Fraction(i, 440) * columns[0][k] + q * columns[1][k]) for k in range(3))
                )
                for q in (-2, 0, 2)
            )
            for i in range(6)
        ),
    )
    return VolumeSpan(
        prepare(surface, Fraction(2), "rotated anisotropic analytical field", checkpoint),
        0,
        (columns[2],) * 6,
    )


def test_exact_cofactor_cancellation_qualifies_a_rotated_conditioned_field() -> None:
    """
    A coordinate rotation cannot justify the older overlarge independent-product enclosure.
    """
    result = enclose(
        rotated_anisotropic_volume(),
        Fraction(1, 2),
        Fraction(5),
        Fraction(1),
        Fraction(0),
        checkpoint,
    )
    assert result.determinant_lower > Fraction(0)
    assert result.condition_upper is not None and result.condition_upper <= 1024
    assert result.status == "certified_local_jacobian_and_conditioning"


def test_opposite_thickness_norm_extrema_do_not_multiply_as_if_they_coexist() -> None:
    """
    Independent extrema give2000, while the complete coupled rational interval is bounded by1000.
    """
    norms = (Fraction(4), Fraction(2))
    cofactors = (Fraction(2), Fraction(2))
    determinants = (Fraction(2), Fraction(1, 250))
    bound = coupled_condition(norms, cofactors, determinants)
    assert max(norms) * max(cofactors) / min(determinants) == Fraction(2000)
    assert bound == Fraction(1000)
    for t in (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)):
        matrix = (1 - t) * norms[0] + t * norms[1]
        adjugate = (1 - t) * cofactors[0] + t * cofactors[1]
        denominator = (1 - t) * determinants[0] + t * determinants[1]
        assert matrix * adjugate / denominator <= bound
    with pytest.raises(ValueError, match="positive determinant"):
        coupled_condition(norms, cofactors, (Fraction(0), Fraction(1)))


@pytest.mark.parametrize("nonaffine", (False, True))
def test_complete_transverse_box_keeps_positive_material_jacobian(nonaffine: bool) -> None:
    """
    A nonaffine vertical midplane displacement retains determinant1 without an affine fit.
    """
    source = volume(nonaffine)
    result = enclose(source, Fraction(1, 2), Fraction(5), Fraction(1), Fraction(0), checkpoint)
    assert result.volume is source
    assert result.determinant_lower == result.determinant_upper == Fraction(1)
    assert result.condition_upper is not None and result.condition_upper <= 1024
    assert result.status == "certified_local_jacobian_and_conditioning"


@pytest.mark.parametrize("reach", (Fraction(1, 2), Fraction(1), Fraction(2)))
def test_thickness_collapse_is_not_waived_by_a_valid_midplane(reach: Fraction) -> None:
    """
    F=(s*(1-b),q,b) loses invertibility at b=1 although its midplane is unchanged.
    """
    source = volume()
    normal = tuple((Fraction(-i), Fraction(0), Fraction(1)) for i in range(6))
    source = replace(source, normal=normal)
    result = enclose(source, reach, Fraction(5), Fraction(1), Fraction(0), checkpoint)
    assert result.determinant_lower == 1 - reach
    assert result.determinant_upper == 1 + reach
    assert result.status == (
        "certified_local_jacobian_and_conditioning" if reach < 1 else "unresolved"
    )
    if reach >= 1:
        assert result.condition_upper is None


def test_zero_normal_and_shared_resource_stops_remain_unresolved() -> None:
    """
    Boundary algebra or a small residual cannot establish a nonsingular volume.
    """
    source = replace(volume(), normal=((Fraction(0),) * 3,) * 6)
    result = enclose(source, Fraction(1), Fraction(5), Fraction(1), Fraction(0), checkpoint)
    assert result.status == "unresolved" and result.determinant_lower == Fraction(0)

    def stop() -> None:
        """
        Propagate the caller's exhausted allocation before any new proof work.
        """
        raise RuntimeError("shared volume allocation exhausted")

    with pytest.raises(RuntimeError, match="shared volume allocation"):
        enclose(source, Fraction(1), Fraction(5), Fraction(1), Fraction(0), stop)
