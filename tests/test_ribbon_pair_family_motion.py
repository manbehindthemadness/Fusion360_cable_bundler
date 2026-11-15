"""
Verify eliminated orientation, dependent angular bounds and nonrenewable correction accounting.
"""

from __future__ import annotations

import math
from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_paired_return import allocation, continuation
from experiments.experiment_ribbon_paired_return.family_model import CoupledJoints, FamilyJoints
from experiments.experiment_ribbon_paired_return.ledger import Exhausted, Ledger
from experiments.experiment_ribbon_paired_return.native_model import NativeJoints
from experiments.experiment_ribbon_paired_return.trust import LocalBox, interior_terms, radius
from experiments.experiment_ribbon_terminal_hardware.active_projection import active_step
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import Difference, jacobian
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from experiments.experiment_ribbon_terminal_hardware.redistributed_projection import (
    GuidancePolicy,
    redistributed_step,
    strict_descent,
)


def _route(
    scale: float,
    sign: int,
    turns: tuple[tuple[float, float], ...] = ((0.7, -0.1), (-1.4, 0.3), (2.1, -0.2)),
) -> FoldRoute:
    """
    Compose three independent factors with unequal banks and fixed physical radii.
    """
    start = Pose(Vector3(2 * scale, -3 * scale, 5 * scale), Vector3(0, 1, 0), Vector3(0, 0, 1))
    pose = start
    pieces = []
    for index, (angle, bank) in enumerate(turns):
        for shape in (
            Straight(0.7 * scale),
            CylindricalFold(
                (0.6 + 0.1 * index) * scale,
                sign * angle,
                bank,
                3.15 * scale,
                0.8 * scale,
                0.9 * scale,
            ),
        ):
            piece = PlacedPiece(pose, shape, "Independent family motion")
            pieces.append(piece)
            pose = piece.end_pose()
    targets = Targets(
        "Analytical family model",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        4,
        0.75 * scale,
    )
    return FoldRoute(targets, tuple(pieces), 0.6 * scale)


@pytest.mark.parametrize("scale", [0.5, 1, 100])
@pytest.mark.parametrize("sign", [-1, 1])
def test_family_coordinates_preserve_full_frame_and_all_other_bends(
    scale: float, sign: int
) -> None:
    """
    Eliminate orientation while allowing position and the selected pair's banks to change.
    """
    route = _route(scale, sign)
    model = FamilyJoints(route, (1, 2))
    values = list(model.initial)
    values[model.bank_index] += 0.01
    assert model.admissible(tuple(values))
    result = model.route(tuple(values))
    assert result is not None
    before, after = route.pieces[-1].end_pose(), result.pieces[-1].end_pose()
    assert magnitude(difference(before.tangent, after.tangent)) < 1e-10
    assert magnitude(difference(before.width, after.width)) < 1e-10
    assert model.residual(tuple(values))[3:] == (0.0, 0.0, 0.0)
    original = [p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold)]
    changed = [p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)]
    assert changed[0] == original[0]
    assert [(p.radius_mm, p.width_mm) for p in changed] == [
        (p.radius_mm, p.width_mm) for p in original
    ]
    assert model.allows_step(model.initial, tuple(values))


def test_family_bank_derivatives_include_dependent_angles() -> None:
    """
    Compare independent central samples with the complete model's derivative contracts.
    """
    model = FamilyJoints(_route(1, 1), (1, 2))
    values = model.initial
    rows = jacobian(
        model,
        values,
        model.residual,
        6,
        set(),
        lambda: None,
        admissible=model.admissible,
        difference=Difference.CENTRAL,
    )
    bank = model.bank_index
    low, high = list(values), list(values)
    low[bank] -= 1e-6
    high[bank] += 1e-6
    for axis in range(3):
        expected = (model.residual(tuple(high))[axis] - model.residual(tuple(low))[axis]) / 2e-6
        assert rows[axis][bank] == pytest.approx(expected, rel=1e-5, abs=1e-7)
    gradient = model.length_gradient(values)
    lengths = []
    for probe in (low, high):
        candidate = model.route(tuple(probe))
        assert candidate is not None
        lengths.append(candidate.material_length_mm / model.scale)
    assert gradient[bank] == pytest.approx((lengths[1] - lengths[0]) / 2e-6, rel=1e-5)
    assert all(gradient[i] == 1 for i in model.straight_indices)


def test_dependent_angle_bounds_and_invalid_target_orientation() -> None:
    """
    A reduced coordinate cannot hide a larger angular step or an unmatched target frame.
    """
    route = _route(1, 1)
    model = FamilyJoints(route, (1, 2))
    trial = list(model.initial)
    trial[model.bank_index] += 0.3
    assert not model.allows_step(model.initial, tuple(trial))
    with pytest.raises(ValueError, match="target frames"):
        FamilyJoints(
            replace(
                route,
                targets=replace(
                    route.targets,
                    end_width=Vector3(0, 0, 0).translated(route.targets.end_width, -1),
                ),
            ),
            (1, 2),
        )


def test_each_numerical_action_debits_six_steps_and_never_renews_global_pool() -> None:
    """
    Separate failed fixed allocation, per-action correction and shared Newton ceilings.
    """
    ledger = Ledger(Work(3, 2048, 0.35, 2, 7), 8, lambda: None)
    ledger.start_action()
    for _ in range(6):
        ledger.start_newton()
    with pytest.raises(Exhausted, match="newton_budget"):
        ledger.start_newton()
    ledger.start_action()
    ledger.start_newton()
    with pytest.raises(Exhausted, match="newton_budget"):
        ledger.start_newton()
    assert ledger.updates == 2 and ledger.newton_steps == 7 and ledger.roots == 0


def test_small_free_bank_step_cannot_hide_large_dependent_angle_motion() -> None:
    """
    A sub-limit bank move still rejects when eliminated angles would exceed the shared bound.
    """
    model = FamilyJoints(_route(1, 1, ((0.7, -0.1), (2.5, 0.3), (0.6, -0.2))), (1, 2))
    values = list(model.initial)
    values[model.bank_index] += 0.1
    before = model.factors(model.initial[model.bank_index])
    after = model.factors(values[model.bank_index])
    assert before is not None and after is not None
    assert max(abs(a.angle_radians - b.angle_radians) for a, b in zip(before, after)) > 0.2
    assert not model.allows_step(model.initial, tuple(values))


def test_native_floors_apply_only_to_material_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A positive bank coordinate is not mistaken for positive straight material.
    """
    route = _route(1, 1)
    model = FamilyJoints(route, (1, 2))
    monkeypatch.setitem(vars(allocation), "prepare", Mock(return_value=()))
    ledger = Ledger(Work(1, 2048, 0.35, 2, 6), 0, lambda: None)
    physical = allocation.constraints(
        model,
        route,
        (),
        (),
        Hardware.create(route.targets, Dimensions.scaled(route.targets)),
        1e-5,
        ledger,
    )
    assert physical is not None
    assert len(physical) == sum(model.initial[i] > 0 for i in model.straight_indices)
    trial = list(model.initial)
    trial[model.bank_index] += 0.01
    assert tuple(f(model.initial) for f in physical) == tuple(f(tuple(trial)) for f in physical)


@pytest.mark.parametrize("scale", [0.5, 1, 100])
@pytest.mark.parametrize("sign", [-1, 1])
def test_owned_disjoint_pairs_share_motion_without_losing_ordered_orientation(
    scale: float, sign: int
) -> None:
    """
    Keep every previously owned bank free while preserving material and action identity.
    """
    route = _route(scale, sign, ((0.7, -0.1), (-1.4, 0.3), (2.1, -0.2), (-0.8, 0.25)))
    pairs = ((2, 3), (0, 1))
    model = CoupledJoints(route, pairs)
    assert model.pairs == pairs and len(model.bank_indices) == 2
    values = list(model.initial)
    for index, delta in zip(model.bank_indices, (0.005, -0.005)):
        values[index] += delta
    assert model.admissible(tuple(values)) and model.allows_step(model.initial, tuple(values))
    result = model.route(tuple(values))
    assert result is not None and result.targets is route.targets
    old, new = route.pieces[-1].end_pose(), result.pieces[-1].end_pose()
    assert magnitude(difference(old.tangent, new.tangent)) < 1e-10
    assert magnitude(difference(old.width, new.width)) < 1e-10
    original = [p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold)]
    changed = [p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)]
    assert [(p.radius_mm, p.width_mm) for p in changed] == [
        (p.radius_mm, p.width_mm) for p in original
    ]
    assert all(a.angle_radians * b.angle_radians > 0 for a, b in zip(original, changed))
    for bank in model.bank_indices:
        low, high = list(values), list(values)
        low[bank] -= 1e-6
        high[bank] += 1e-6
        before, after = model.route(tuple(low)), model.route(tuple(high))
        assert before is not None and after is not None
        expected = (after.material_length_mm - before.material_length_mm) / (2e-6 * model.scale)
        assert model.length_gradient(tuple(values))[bank] == pytest.approx(expected, rel=1e-5)


@pytest.mark.parametrize("pairs", [(), ((0, 1), (1, 2)), ((0, 2),)])
def test_invalid_owned_pair_domains_decline(pairs: tuple[tuple[int, int], ...]) -> None:
    """
    Empty, overlapping or nonconsecutive domains cannot invent coupled event identity.
    """
    with pytest.raises(ValueError):
        CoupledJoints(_route(1, 1), pairs)


def test_angular_bound_covers_every_owned_pair() -> None:
    """
    Motion in an earlier pair receives the same bound as the most recent pair.
    """
    route = _route(1, 1, ((0.7, -0.1), (-1.4, 0.3), (2.1, -0.2), (-0.8, 0.25)))
    model = CoupledJoints(route, ((2, 3), (0, 1)))
    trial = list(model.initial)
    trial[model.bank_indices[1]] += 0.3
    assert not model.allows_step(model.initial, tuple(trial))


def test_failed_projection_is_charged_without_new_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A numerical decline consumes one existing action and step, never another orientation root.
    """
    anchor = _route(1, 1)
    model = NativeJoints(anchor, 1e-5)
    values = list(model.initial)
    values[model.bank_indices[0]] += 0.05
    source = model.route(tuple(values))
    assert source is not None
    monkeypatch.setitem(
        vars(continuation), "constraints", Mock(return_value=(lambda coordinates: -1.0,))
    )
    projection = Mock(return_value=None)
    monkeypatch.setitem(vars(continuation), "redistributed_step", projection)
    ledger = Ledger(Work(2, 2048, 0.35, 2, 6), 8, lambda: None)
    ledger.start_action()
    events = []
    result = continuation.correct(
        source,
        anchor,
        (1, 2),
        (),
        (),
        Hardware.create(anchor.targets, Dimensions.scaled(anchor.targets)),
        1e-5,
        ledger,
        events.append,
    )
    assert result is None and projection.call_count == 1
    assert ledger.updates == 2 and ledger.newton_steps == 1 and ledger.roots == 0
    assert events[-1]["reason"] == "linear_projection_unresolved"


def test_intermediate_caps_can_improve_when_exact_linear_closure_is_unavailable() -> None:
    """
    Bounded restoration supplies descent without certifying an impossible final endpoint.
    """

    class UnitBounds:
        """
        Bound one mathematical coordinate without constructing any material geometry.
        """

        @staticmethod
        def bounds(index: int) -> tuple[float, float]:
            """
            Keep the only coordinate inside its declared finite interval.
            """
            assert index == 0
            return 0.0, 1.0

    model = UnitBounds()
    rows = [[1.0], [0.0], [0.0], [0.0], [0.0], [0.0], [-1.0]]
    residual = (-2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert active_step(model, (0.0,), rows, residual, lambda: None) is None
    delta = redistributed_step(
        model,
        (0.0,),
        rows,
        residual,
        lambda: None,
        guidance_policy=GuidancePolicy.RESTORATION_MERIT,
    )
    assert delta is not None and 0 < delta[0] <= 1
    predicted = tuple(r + row[0] * delta[0] for row, r in zip(rows, residual))
    assert strict_descent(residual, predicted, GuidancePolicy.RESTORATION_MERIT)
    assert predicted[0] != 0


def test_positive_native_material_is_a_hard_coordinate_bound() -> None:
    """
    Numerical restoration cannot trade native size against a remaining cap error.
    """
    route = _route(1, 1)
    model = CoupledJoints(route, ((1, 2),), 1e-5)
    positive = next(i for i in model.straight_indices if model.initial[i] > 0)
    floor, _ = model.bounds(positive)
    assert floor * model.scale > 1e-5
    trial = list(model.initial)
    trial[positive] = floor / 2
    assert not model.admissible(tuple(trial))
    assert model.bounds(model.bank_indices[0])[0] < 0


@pytest.mark.parametrize("scale", [0.5, 1, 100])
@pytest.mark.parametrize("sign", [-1, 1])
def test_signed_native_joints_release_internal_frames_without_material_changes(
    scale: float, sign: int
) -> None:
    """
    Compensating banks can change orientation while signs, radii and native floors remain hard.
    """
    route = _route(scale, sign)
    model = NativeJoints(route, 1e-5 * scale)
    values = list(model.initial)
    values[model.bank_indices[0]] += 0.001
    changed = model.route(tuple(values))
    assert changed is not None and model.admissible(tuple(values))
    assert model.preserves(changed) and model.allows_step(model.initial, tuple(values))
    assert max(abs(term) for term in model.residual(tuple(values))[3:]) > 1e-5
    positive = next(i for i in model.straight_indices if model.initial[i] > 0)
    values[positive] = model.bounds(positive)[0] / 2
    assert not model.admissible(tuple(values))


def test_positive_native_extension_is_retained_through_fixed_derivatives() -> None:
    """
    Extending an activated slot preserves positive material and removes its derivative freedom.
    """
    model = NativeJoints(_route(1, 1), 1e-5)
    slot = model.straight_indices[-1]
    assert model.initial[slot] == 0
    values = list(model.initial)
    values[slot] = model.native_floor
    model.native_pins[slot] = values[slot]
    assert values[slot] * model.scale > 1e-5 and model.admissible(tuple(values))
    assert model.bounds(slot) == (values[slot], values[slot])
    rows = jacobian(
        model, tuple(values), model.residual, 6, {slot}, lambda: None, admissible=model.admissible
    )
    assert all(row[slot] == 0 for row in rows)


def test_hard_native_faces_do_not_duplicate_physical_projection_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep a retained material row while native violations remain rejected by coordinate bounds.
    """
    from experiments.experiment_ribbon_fold_route.contact import Penetration

    route = _route(1, 1)
    model = CoupledJoints(route, ((1, 2),), 1e-5)
    monkeypatch.setitem(vars(allocation), "prepare", Mock(return_value=()))
    plane = Mock()
    plane.gap.return_value = 1.0
    monkeypatch.setattr(allocation.FlatSeparation, "create", Mock(return_value=plane))
    witness = Penetration((0, 2), (0, 0, 0), (0, 0, 0), Vector3(0, 0, 0))
    physical = allocation.constraints(
        model,
        route,
        (allocation.MaterialEvidence(route, witness),),
        (),
        Hardware.create(route.targets, Dimensions.scaled(route.targets)),
        1e-5,
        Ledger(Work(1, 2048, 0.35, 2, 6), 0, lambda: None),
    )
    assert physical is not None and len(physical) == 1
    assert physical[0](model.initial) < 0 and plane.gap.called
    values = list(model.initial)
    positive = next(i for i in model.straight_indices if values[i] > 0)
    values[positive] = model.bounds(positive)[0] / 2
    assert not model.admissible(tuple(values))


@pytest.mark.parametrize("sign", [-1, 1])
def test_untouched_disjoint_pairs_can_compensate_without_new_events(sign: int) -> None:
    """
    Free regular untouched material while retaining owned order, signs and exact cap frames.
    """
    route = _route(1, sign, ((0.7, -0.1), (-1.4, 0.3), (2.1, -0.2), (0.8, 0.2), (-1.1, -0.3)))
    owned = ((3, 4),)
    selection = CoupledJoints(route, owned)
    pairs = selection.compensation_pairs()
    assert pairs == ((3, 4), (0, 1))
    model = CoupledJoints(route, pairs)
    values = list(model.initial)
    values[model.bank_indices[-1]] += 0.001
    changed = model.route(tuple(values))
    assert changed is not None and model.preserves(changed)
    assert len(changed.pieces) == len(model.pieces(model.initial))
    before, after = route.pieces[-1].end_pose(), changed.pieces[-1].end_pose()
    assert magnitude(difference(before.tangent, after.tangent)) < 1e-10
    assert magnitude(difference(before.width, after.width)) < 1e-10


@pytest.mark.parametrize("motion", [0.001, 0.1, 1.0])
def test_endpoint_disagreement_contracts_the_next_correction(motion: float) -> None:
    """
    A nonlinear model miss larger than remaining cap merit reduces the next step at any scale.
    """
    rows = [[-1.0]] + [[0.0]] * 5
    residual = (2 * motion, 0.0, 0.0, 0.0, 0.0, 0.0)
    observed = (0.1 * motion, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert 0 < radius((0.0,), (motion,), rows, residual, observed) < motion


def test_exact_linear_prediction_allows_only_bounded_growth() -> None:
    """
    Accurate previous predictions permit expansion without restarting an unbounded trial ray.
    """
    rows = [[-1.0]] + [[0.0]] * 5
    residual = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    observed = (0.5, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert radius((0.0,), (0.5,), rows, residual, observed) == 1.0


@pytest.mark.parametrize("previous", [0.01, 1.0, math.inf])
@pytest.mark.parametrize("motion", [1e-8, 1e-6])
def test_accurate_face_limited_step_preserves_unrelated_motion(
    previous: float, motion: float
) -> None:
    """
    A tiny physical-face step supplies no evidence that the existing local model needs contraction.
    """
    rows = [[-1.0]] + [[0.0]] * 5
    residual = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    observed = (1.0 - motion + 1e-12, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert radius((0.0,), (motion,), rows, residual, observed, previous_radius=previous) == previous


def test_cap_model_failure_still_contracts_an_existing_wide_box() -> None:
    """
    Earlier accurate steps cannot retain a wide box after actual cap-model disagreement.
    """
    rows = [[-1.0]] + [[0.0]] * 5
    residual = (2.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    observed = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert 0 < radius((0.0,), (1.0,), rows, residual, observed, previous_radius=math.inf) < 1.0


@pytest.mark.parametrize("scale", [1e-6, 1.0, 1e6])
def test_linear_headroom_retains_caps_touching_boundary_and_positive_guidance(scale: float) -> None:
    """
    Reserve a fraction of existing slack without a new physical clearance distance or altered cap equations.
    """
    terms = tuple(scale * value for value in (-1.0, 2.0, 0.0, 0.0, 0.0, 0.0, -0.2, -0.3, 0.0, 0.1))
    projected = interior_terms(terms, frozenset({7}))
    assert projected[:6] == terms[:6]
    assert projected[6] == terms[6] / 2 and projected[7:] == terms[7:]


def test_measured_boundary_loss_changes_only_the_next_already_allocated_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A rejected curved-boundary trial activates interior guidance without another trial or Newton allowance.

    Geometry and derivative boundaries are doubled; actual scalar nonlinear
    residuals still decide every accepted step and final inequality readiness.
    """
    anchor = _route(1, 1)
    state = {"value": 0.0}

    def route_at(values: tuple[float, ...]) -> FoldRoute:
        """
        Track one analytical coordinate while leaving the geometry boundary explicitly doubled.
        """
        state["value"] = values[0]
        return anchor

    model = Mock(initial=(0.0,), straight_indices=(0,), bank_indices=(), native_pins={}, scale=1.0)
    model.route.side_effect = route_at
    model.residual.side_effect = lambda v: (1.0 - v[0], 0.0, 0.0, 0.0, 0.0, 0.0)
    model.bounds.return_value = (0.0, 2.0)
    model.admissible.return_value = model.allows_step.return_value = True
    monkeypatch.setitem(vars(continuation), "NativeJoints", Mock(return_value=model))
    monkeypatch.setitem(
        vars(continuation), "constraints", Mock(return_value=(lambda v: v[0] ** 2 - 0.9,))
    )
    monkeypatch.setitem(
        vars(continuation),
        "ordered_mating_caps",
        Mock(side_effect=lambda *args: state["value"] >= 0.7),
    )
    monkeypatch.setitem(vars(continuation), "cap_error", Mock(return_value=0.0))
    monkeypatch.setitem(
        vars(continuation),
        "jacobian",
        Mock(side_effect=lambda _model, v, *args, **kwargs: [[-1.0]] + [[0.0]] * 5 + [[2 * v[0]]]),
    )
    monkeypatch.setitem(vars(continuation), "mating_cap_jacobian", Mock(return_value=None))
    projected = Mock(side_effect=((1.0,), (0.25,)))
    monkeypatch.setitem(vars(continuation), "redistributed_step", projected)
    ledger = Ledger(Work(1, 2048, 0.35, 2, 6), 0, lambda: None)
    ledger.start_action()
    records = []
    result = continuation.correct_started(
        anchor,
        anchor,
        (),
        (),
        (),
        Hardware.create(anchor.targets, Dimensions.scaled(anchor.targets)),
        1e-5,
        ledger,
        records.append,
    )
    assert result is anchor and ledger.updates == 1 and ledger.newton_steps == 2
    assert projected.call_args_list[0].args[3][-1] == -0.9
    assert projected.call_args_list[1].args[3][-1] == pytest.approx(-0.325)
    assert records[0]["interior_slack_rows"] == () and records[1]["interior_slack_rows"] == (6,)
    assert state["value"] == 0.75


@pytest.mark.parametrize("completed", [False, True])
@pytest.mark.parametrize("gap", [4e-8, 4e-6, 0.01])
def test_native_ready_orientation_uses_one_charged_mating_correction(
    monkeypatch: pytest.MonkeyPatch, completed: bool, gap: float
) -> None:
    """
    Close an actual tiny positional gap through existing straight material, without an angular fallback.

    Physical guidance is a boundary double; real geometry, readiness, mating
    correction and original cap certification remain active.
    """
    original = _route(1, 1)
    source = replace(
        original,
        targets=replace(
            original.targets,
            end=original.targets.end.translated(original.targets.start_tangent, gap),
        ),
    )
    monkeypatch.setitem(
        vars(continuation), "constraints", Mock(return_value=(lambda coordinates: -1.0,))
    )
    angular = Mock(
        side_effect=AssertionError("Ready mating replaces the ordinary angular projection")
    )
    monkeypatch.setitem(vars(continuation), "redistributed_step", angular)
    if not completed:
        monkeypatch.setitem(vars(continuation), "restore_mating", Mock(return_value=None))
    ledger = Ledger(Work(1, 2048, 0.35, 2, 1), 0, lambda: None)
    ledger.start_action()
    records = []
    result = continuation.correct_started(
        source,
        source,
        (),
        (),
        (),
        Hardware.create(source.targets, Dimensions.scaled(source.targets)),
        1e-5,
        ledger,
        records.append,
    )
    assert ledger.updates == ledger.newton_steps == 1 and not angular.called
    assert (result is not None) == completed
    if completed:
        assert result is not None
        assert continuation.ordered_mating_caps(result.pieces, result.targets)
        assert result.targets is source.targets and result.targets != original.targets
        assert any(event["stage"] == "paired_mating" for event in records)
    else:
        assert records[-1]["reason"] == "mating_correction_unresolved"


def test_local_projection_retains_original_faces_and_chooses_small_descent() -> None:
    """
    Optimize inside local motion bounds rather than clipping a distant optimum afterward.
    """

    class UnitBounds:
        """
        Supply an explicit physical box independent of local projection bounds.
        """

        @staticmethod
        def bounds(index: int) -> tuple[float, float]:
            """
            Use the same unit interval for both analytical coordinates.
            """
            return ((0.0, 1.0), (0.0, 1.0))[index]

    local = LocalBox(UnitBounds(), (0.0, 0.5), 0.01)
    assert local.bounds(0) == (0.0, 0.01)
    assert local.bounds(1) == (0.49, 0.51)
    rows = [[1.0, 1.0]] + [[0.0, 0.0]] * 5 + [[-1.0, 0.0]]
    residual = (-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    delta = redistributed_step(
        local,
        (0.0, 0.5),
        rows,
        residual,
        lambda: None,
        guidance_policy=GuidancePolicy.RESTORATION_MERIT,
    )
    assert delta is not None
    assert all(
        local.bounds(i)[0] <= value + change <= local.bounds(i)[1]
        for i, (value, change) in enumerate(zip(local.values, delta))
    )
    predicted = tuple(r + sum(a * b for a, b in zip(row, delta)) for r, row in zip(residual, rows))
    assert strict_descent(residual, predicted, GuidancePolicy.RESTORATION_MERIT)


@pytest.mark.parametrize("actions,required", [(1, 7), (2, 7), (2, 6)])
@pytest.mark.parametrize("already_spent", [0, 4])
def test_continuation_uses_remaining_actions_without_renewal(
    monkeypatch: pytest.MonkeyPatch, actions: int, required: int, already_spent: int
) -> None:
    """
    Charge step seven before motion, stop at the original pool, and avoid unnecessary actions.

    Geometry and derivatives are explicit boundary doubles; this verifies budget
    ownership, not a material or physical feasibility certificate.
    """
    anchor = _route(1, 1)
    state = {"value": 0.0}

    def route_at(values: tuple[float, ...]) -> FoldRoute:
        """
        Retain the synthetic numerical coordinate separately from doubled geometry.
        """
        state["value"] = values[0]
        return anchor

    def residual_at(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Supply a strictly decreasing scalar cap equation for the accounting test.
        """
        residual = (1 - values[0], 0.0, 0.0, 0.0, 0.0, 0.0)
        return residual

    model = Mock(initial=(0.0,), straight_indices=(0,), bank_indices=(), native_pins={}, scale=1.0)
    model.route.side_effect = route_at
    model.residual.side_effect = residual_at
    model.bounds.return_value = (0.0, 1.0)
    model.admissible.return_value = model.allows_step.return_value = True
    monkeypatch.setitem(vars(continuation), "NativeJoints", Mock(return_value=model))
    monkeypatch.setitem(
        vars(continuation), "constraints", Mock(return_value=(lambda values: -1.0,))
    )
    monkeypatch.setitem(
        vars(continuation),
        "ordered_mating_caps",
        Mock(side_effect=lambda *args: state["value"] >= 0.1 * (required - 0.5)),
    )
    monkeypatch.setitem(vars(continuation), "cap_error", Mock(return_value=0.0))
    monkeypatch.setitem(vars(continuation), "jacobian", Mock(return_value=[[-1.0]] + [[0.0]] * 6))
    monkeypatch.setitem(vars(continuation), "mating_cap_jacobian", Mock(return_value=None))
    projected = Mock(return_value=(0.1,))
    monkeypatch.setitem(vars(continuation), "redistributed_step", projected)
    ledger = Ledger(Work(actions, 2048, 0.35, 2, 24), 0, lambda: None)
    if already_spent:
        ledger.start_action()
        for _ in range(already_spent):
            ledger.start_newton()
    records = []
    correct = continuation.correct_remaining if already_spent else continuation.correct_owned
    result = correct(
        anchor,
        anchor,
        ((1, 2),),
        (),
        (),
        Hardware.create(anchor.targets, Dimensions.scaled(anchor.targets)),
        1e-5,
        ledger,
        records.append,
    )
    spent = min(required, 6 * actions - already_spent)
    assert projected.call_count == spent and ledger.newton_steps == spent + already_spent
    assert ledger.updates == (spent + already_spent + 5) // 6 and ledger.roots == 0
    assert (result is anchor) == (required <= 6 * actions - already_spent)
    assert all(event["trust_radius"] is None for event in records if event["status"] == "update")
