"""
Re-prove learned directions on actual full material without historical geometry replay.
"""

from __future__ import annotations

import math
from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import Side, regions
from experiments.experiment_ribbon_fold_route.contact import (
    ContactResult,
    ProbeOrder,
    inspect_contact,
)
from experiments.experiment_ribbon_fold_route.contact_affine_witness import AffineWitnesses
from experiments.experiment_ribbon_fold_route.contact_axes import (
    AxisContinuation,
    AxisLearning,
    ProposedAxes,
)
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import ContactGuidance
from experiments.experiment_ribbon_terminal_hardware.joint_evaluation import JointEvaluation
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from experiments.experiment_ribbon_terminal_hardware.retained_directions import RetainedDirections
from tests.test_ribbon_contact_refinement import _depth, _gate, _source
from tests.test_ribbon_flat_geometry_reuse import _constraint
from tests.test_ribbon_material_return import _witness
from tests.test_ribbon_probe_axis import _skew


@pytest.mark.parametrize("index", range(12))
def test_learned_directions_preserve_actual_contact_under_the_original_allowance(
    index: int,
) -> None:
    """
    Recover independently proposed skew directions without repeating any support search in certification.
    """
    route = _skew(index)
    axis = FlatProbe()(route, 0, 1, 32, None).axis_proposal
    directed = RetainedDirections(route, () if axis is None else ((0, 1, axis),))
    baseline = inspect_contact(route, maximum_pairs=2048)
    result = inspect_contact(
        route, maximum_pairs=2048, witness_probe=directed, probe_order=ProbeOrder.MATERIAL_CELLS
    )
    assert result.status == baseline.status
    assert result.pairs_checked <= baseline.pairs_checked
    if index in (6, 7, 8):
        assert result.pairs_checked == 1 < baseline.pairs_checked
        assert result.axis_tests == result.axis_separations == 1
    if result.witness is not None:
        assert all(
            occupied_coordinates(
                route.pieces[piece],
                result.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            is not None
            for piece in result.witness.pieces
        )


def test_preparation_resolves_only_owned_current_slots_and_retains_first_direction() -> None:
    """
    Wrapped and partial material bounds supply directions without transferring their gaps or phases.
    """
    bound = _constraint()
    model = bound.model
    route = model.route(model.initial)
    assert route is not None
    checkpoint = Mock()
    other = replace(bound, axis=Vector3(0, 0, 1))
    foreign = _constraint()
    prepared = RetainedDirections.prepare(
        route,
        model,
        model.initial,
        ((foreign, Side.BEFORE), (MaterialConstraint(bound), Side.AFTER), (other, Side.BEFORE)),
        checkpoint,
    )
    assert prepared is not None
    pair = tuple(regions(route).index(tag) for tag in bound.pair)
    assert prepared.axes == ((*pair, bound.axis),)
    assert prepared(route, *pair, 0, checkpoint).axis_proposal == bound.axis
    assert prepared(route, 0, len(route.pieces) - 1, 0, checkpoint).axis_proposal is None
    assert prepared(replace(route), *pair, 0, checkpoint).axis_proposal is None
    assert checkpoint.call_count >= 5


@pytest.mark.parametrize("change", ("short", "extra", "nonfinite", "moved"))
def test_stale_or_incomplete_current_pose_cannot_supply_retained_directions(change: str) -> None:
    """
    Reject missing, surplus, invalid or different geometry instead of transferring indexed guidance.
    """
    bound = _constraint()
    model = bound.model
    route = model.route(model.initial)
    assert route is not None
    values = {
        "short": model.initial[:-1],
        "extra": model.initial + (0.0,),
        "nonfinite": (math.nan,) + model.initial[1:],
        "moved": (model.initial[0] + 0.01,) + model.initial[1:],
    }[change]
    assert RetainedDirections.prepare(route, model, values, ((bound, Side.BEFORE),), Mock()) is None


def test_direction_reproof_keeps_pair_exhaustion_and_cancellation() -> None:
    """
    An unhelpful learned axis cannot omit subdivisions or finish after the original guard expires.
    """
    route = _skew(6)
    directed = RetainedDirections(route, ((0, 1, Vector3(1, 0, 0)),))
    limited = inspect_contact(
        route, maximum_pairs=1, witness_probe=directed, probe_order=ProbeOrder.MATERIAL_CELLS
    )
    assert limited.status == "unresolved" and limited.limit == "pairs"
    assert limited.pairs_checked == 1 and limited.axis_separations == 0
    with pytest.raises(TimeoutError, match="original guard"):
        inspect_contact(
            route,
            witness_probe=directed,
            probe_order=ProbeOrder.MATERIAL_CELLS,
            checkpoint=Mock(side_effect=TimeoutError("original guard")),
        )


def test_unowned_and_missing_material_supply_no_direction() -> None:
    """
    Empty or foreign guidance is inert even when the source geometry has an equivalent copy.
    """
    bound, foreign = _constraint(), _constraint()
    model = bound.model
    route = model.route(model.initial)
    assert route is not None
    for constraints in ((), ((foreign, Side.BEFORE),)):
        assert RetainedDirections.prepare(route, model, model.initial, constraints, Mock()) is None


@pytest.mark.parametrize("entry", ("witness", "contact", "uncertain"))
def test_closed_joint_entry_uses_incoming_contact_without_rediscovering_it(
    monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    """
    Verify real preparation and certificate wiring with explicit equation and physical-boundary doubles.

    A retained incoming strict crossing already justifies proof-first scheduling;
    depth uncertainty alone keeps the existing negative accelerator. Mocked
    certificate results here provide no physical or native geometry coverage.
    """
    source = _source()
    witness = _witness(0, 2, 0.5, 0.5)
    terminal = _gate(source)
    terminal.measure.return_value = Report("clear", 1)

    def equations(_self: JointEvaluation, _values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Reach actual closed-material certification without an optimization attempt.
        """
        return (0.0,) * 8

    monkeypatch.setattr(JointEvaluation, "equations", equations)
    checker = Mock(return_value=ContactResult("separated", 1))
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", checker)
    evidence = (
        witness
        if entry == "witness"
        else (_depth() if entry == "uncertain" else ContactResult("penetration", 1, witness))
    )
    result = joint_contact.recover(
        source,
        evidence,
        terminal,
        Mock(),
        Mock(),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=joint_contact.JointMode.PARENT_CEILING if entry == "witness" else ContactGuidance(()),
    )
    assert result is not None and result.contact is checker.return_value
    assert result.detail["flat_probe_preparations"]["capacity"] == 64
    kwargs = checker.call_args.kwargs
    assert isinstance(kwargs["affine_witnesses"], AffineWitnesses)
    assert result.detail["affine_witnesses"][0]["capacity"] == 32
    assert isinstance(kwargs["proposed_axes"], ProposedAxes)
    assert kwargs["proposed_axes"].continuation is AxisContinuation.MATERIAL_CELLS
    assert kwargs["proposed_axes"].learning is AxisLearning.LOCAL_SEPARATIONS
    if entry == "uncertain":
        assert isinstance(kwargs["witness_probe"], FlatProbe)
        assert kwargs["probe_order"] is ProbeOrder.ORIGINAL_PAIRS
    else:
        learned = kwargs["witness_probe"]
        assert isinstance(learned, RetainedDirections) and learned.axes
        assert learned.source is checker.call_args.args[0]
        assert kwargs["probe_order"] is ProbeOrder.MATERIAL_CELLS
    assert kwargs["maximum_pairs"] == 123 and result.detail["newton_steps"] == 0
