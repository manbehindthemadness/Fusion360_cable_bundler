"""
Check bounded canonical inverse recovery without confusing residuals with native membership.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from artifacts.verification.resume3216.field import Midsurface
from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.c2_material import prepare
from experiments.experiment_ribbon_complete.volume_field import BendVolume
from experiments.experiment_ribbon_complete.volume_injectivity import audit
from experiments.experiment_ribbon_complete.volume_inverse import recover
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


def shifted(volume: BendVolume, offset: float) -> BendVolume:
    """
    Translate stored source controls only to test proposals against actual canonical geometry.
    """
    surface = Midsurface(
        volume.source.surface.basis,
        tuple(
            tuple(Vector3(p.x + offset, p.y, p.z) for p in row)
            for row in volume.source.surface.rows
        ),
    )
    return replace(
        volume,
        source=prepare(surface, volume.source.half_mm, "translated analytical field", checkpoint),
    )


@pytest.mark.parametrize("shear", (False, True))
@pytest.mark.parametrize("sign", (-1, 1))
def test_cap_and_interior_material_coordinates_obey_exact_conditional_error(
    shear: bool, sign: int
) -> None:
    """
    Exact stored targets round-trip on both signs and nonorthogonal reference frames.
    """
    volume = candidate(shear)
    if sign < 0:
        surface = Midsurface(
            volume.source.surface.basis,
            tuple(
                tuple(Vector3(p.x, p.y, 6 - p.z) for p in row) for row in volume.source.surface.rows
            ),
        )
        volume = replace(
            volume,
            sign=-1,
            source=prepare(
                surface, volume.source.half_mm, "reflected analytical field", checkpoint
            ),
        )
    proof = audit(volume, checkpoint)
    steps = []

    def take_step() -> None:
        """
        Account for actual Newton corrections in this bounded analytical root sequence.
        """
        steps.append(1)

    theta = volume.source.surface.basis.breaks[-1]
    for phase, q, b in (
        (Fraction(0), Fraction(-2, 5), Fraction(0)),
        (theta / 3, Fraction(1, 5), Fraction(1, 10)),
        (theta, Fraction(2, 5), Fraction(-1, 10)),
    ):
        target = volume.jet(phase, q, b).point
        result = recover(volume, proof, target, take_step, checkpoint)
        assert result.volume is volume and result.proof is proof
        assert result.status == "within_dimensional_tolerance"
        assert max(
            result.residual_upper_mm, result.material_error_upper_if_in_image_mm
        ) <= Fraction(1, 100)
        wanted = (
            (volume.radius_mm * phase - volume.sine * q) / volume.cosine + volume.before_mm,
            q,
            b,
        )
        squared = sum((a - z) ** 2 for a, z in zip(wanted, result.material_coordinates))
        assert squared <= result.material_error_upper_if_in_image_mm**2
    assert len(steps) <= 18


def test_newton_corrects_reference_proposals_using_actual_translated_control_field() -> None:
    """
    A valid globally injective translation cannot inherit analytic-reference inverse labels.
    """
    volume = shifted(candidate(), 0.02)
    proof = audit(volume, checkpoint)
    target = volume.jet(Fraction(1, 20), Fraction(1, 10), Fraction(1, 20)).point
    steps = []

    def take_step() -> None:
        """
        Debit each numerical correction without giving a new root or search budget.
        """
        steps.append(1)

    result = recover(volume, proof, target, take_step, checkpoint)
    assert result.status == "within_dimensional_tolerance" and 0 < len(steps) <= 6
    assert result.material_error_upper_if_in_image_mm <= Fraction(1, 100)


def test_wrong_proof_outside_target_and_malformed_world_data_do_not_pass() -> None:
    """
    Finite exhaustion is unresolved, and source identity cannot be replaced by equal metadata.
    """
    volume = candidate()
    proof = audit(volume, checkpoint)
    target = volume.jet(Fraction(1, 20), Fraction(0), Fraction(0)).point
    with pytest.raises(ValueError, match="SAME original"):
        recover(replace(volume), proof, target, checkpoint, checkpoint)
    with pytest.raises(ValueError, match="SAME original"):
        recover(
            volume, replace(proof, separation_lower=Fraction(0)), target, checkpoint, checkpoint
        )
    with pytest.raises(ValueError, match="exact finite"):
        recover(volume, proof, (Fraction(0), Fraction(0)), checkpoint, checkpoint)
    with pytest.raises(ValueError, match="numerical proposal range"):
        recover(
            volume, proof, (Fraction(10**1000), Fraction(0), Fraction(0)), checkpoint, checkpoint
        )
    outside = (target[0], target[1], target[2] + 10)
    assert recover(volume, proof, outside, checkpoint, checkpoint).status == "unresolved"


def test_caller_checkpoint_and_step_stop_propagate_without_an_inverse_receipt() -> None:
    """
    Neither a stored proof nor a good proposal bypasses the caller's shared resource limits.
    """
    volume = shifted(candidate(), 0.02)
    proof = audit(volume, checkpoint)
    target = volume.jet(Fraction(1, 20), Fraction(0), Fraction(0)).point

    def stop() -> None:
        """
        Model a stopped shared allocation before further numerical work.
        """
        raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        recover(volume, proof, target, checkpoint, stop)
    with pytest.raises(RuntimeError, match="caller stopped"):
        recover(volume, proof, target, stop, checkpoint)
