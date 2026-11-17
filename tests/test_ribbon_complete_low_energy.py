"""
Challenge the fixed low-energy transition's geometry, exact energy and ending-only certificate.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from uuid import UUID

from artifacts.verification.resume3204.polynomial import multiply
from experiments.experiment_ribbon_complete.ending_material import audit, bound
from experiments.experiment_ribbon_complete.execution import prepare
from experiments.experiment_ribbon_complete.profile_transition import TransitionTiming, build
from experiments.experiment_ribbon_complete.spatial_frame import split_at
from experiments.experiment_ribbon_complete.spatial_transition import compose
from experiments.experiment_ribbon_complete_gym.fixture import author
from tests.test_ribbon_complete_execution import checkpoint, targets, trunk
from tests.test_ribbon_complete_gym_job import scene


def test_fixed_septic_is_monotone_c2_and_has_lower_exact_energy() -> None:
    """
    The nonmonotone control polygon describes a monotone actual blend with exact flat cap jets.
    """
    controls = tuple(Fraction(v) for v in TransitionTiming.LOW_ENERGY.value)
    first = tuple(7 * (b - a) for a, b in zip(controls, controls[1:]))
    square = multiply(first, first)
    assert sum(square) / len(square) == Fraction(1015, 858) < Fraction(10, 7)
    # beta'=105*u²*(1-u)²*(1-10*u*(1-u)/3); the last factor is>=1/6.
    for parameter in (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)):
        derivative = split_at(first, parameter)[0][-1]
        assert derivative == 105 * parameter**2 * (1 - parameter) ** 2 * (
            1 - Fraction(10, 3) * parameter * (1 - parameter)
        )
        assert derivative >= 0
    assert controls[:3] == (0, 0, 0) and controls[-3:] == (1, 1, 1)


def test_profile_source_geometry_and_cap_jets_remain_fixed() -> None:
    """
    The same declared root and circle survive both policies, with no input or radius adjustment.
    """
    source = targets()
    root = source.roots[0]
    old = build(root.profile, root.center_q_mm, source.trunk.diameter_mm / 2)
    new = build(
        root.profile,
        root.center_q_mm,
        source.trunk.diameter_mm / 2,
        timing=TransitionTiming.LOW_ENERGY,
    )
    for a, b in zip(old, new):
        assert a.source is b.source and a.terminal == b.terminal
        assert a.rows[0] == b.rows[0] and a.rows[-1] == b.rows[-1]
        for end in (0.0, 1.0):
            for v in (0.0, 0.5, 1.0):
                assert a.jet(end, v) == b.jet(end, v)


def test_actual_ending_certificate_never_clears_trunk_or_physical_gates() -> None:
    """
    Certify actual low-energy tensors while retaining missing complete-ribbon qualification.
    """
    plan = prepare(
        author(scene(), UUID(int=3353)),
        trunk,
        checkpoint,
        lambda event: None,
        timing=TransitionTiming.LOW_ENERGY,
    )
    result = audit(plan, checkpoint)
    assert result["within_allowance"] and result["upper_mm"] is not None
    upper = result["upper_mm"]
    assert isinstance(upper, str) and Fraction(upper) <= Fraction(1, 100)
    assert "trunk" in str(result["scope"]) and all(
        "native_fidelity" in branch.outstanding for branch in plan.branches
    )
    patch = plan.branches[0].patches[0][0]
    moving = replace(patch.frame, width=(patch.frame.width[0], patch.frame.width[0]))
    coordinate = Fraction(0)
    # An off-midplane edge endpoint cannot receive the midline-only certificate.
    assert bound(compose(patch.section, moving, checkpoint), coordinate, checkpoint) is None
