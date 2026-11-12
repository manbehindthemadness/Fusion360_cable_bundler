"""
Test actual fixed-fold mating correction using independent analytical material chains.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import cast
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_feature_insertion import allocation
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.mating_allocation import polish
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


def _straight(diameter: float) -> Model:
    """
    Author a straight target independently of the intentionally inaccurate allocation.
    """
    source = _route((Straight(10 * diameter),))
    return Model(
        Boundary(replace(source.targets, diameter_mm=diameter), diameter),
        Topology("authored", (), None),
    )


@pytest.mark.parametrize("diameter", (0.5, 1.0, 20.0, 1000.0))
@pytest.mark.parametrize("offset_mm", (-5e-8, 6e-10, 5e-8))
def test_actual_cap_polish_enables_unchanged_strict_hardware_proof(
    diameter: float, offset_mm: float
) -> None:
    """
    Real recomposition closes both caps and enables analytic mating under the same64cell allowance.
    """
    model = _straight(diameter)
    values = (10.0 + offset_mm / diameter,)
    original = FoldRoute(model.source.targets, model.pieces(values), model.source.radius_mm)
    hardware = Hardware.create(original.targets, Dimensions.scaled(original.targets))
    assert 1e-10 < cap_error(original) < 1e-7
    assert not ordered_mating_caps(original.pieces, original.targets)
    if offset_mm > 0:
        assert inspect(original, hardware, maximum_cells=64).status == "unresolved"
    result = polish(model, values, 1e-5, lambda: None)
    assert result is not None
    assert result != values
    coordinates = cast(tuple[float, ...], result)
    route = FoldRoute(original.targets, model.pieces(coordinates), original.radius_mm)
    assert route.targets is original.targets
    assert ordered_mating_caps(route.pieces, route.targets)
    report = inspect(route, hardware, maximum_cells=64)
    assert report.status == "clear" and report.cells_checked == 2


def test_exact_allocation_has_no_affine_correction(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Already eligible geometry retains its coordinates without any extra linear proposal.
    """
    project = Mock(side_effect=AssertionError("unexpected correction"))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_fold_route.straight_closure.affine_projection",
        project,
    )
    values = (10.0,)
    assert polish(_straight(1), values, 1e-5, lambda: None) is values
    project.assert_not_called()


def test_fixed_fold_correction_preserves_absent_slot_and_exact_fold_geometry() -> None:
    """
    A two-turn chain distributes tiny closure correction among occupied straight slots only.
    """
    bends = (fold(2, 1.2, math.pi / 2, 0, 0), fold(2, 1.2, math.pi / 2, 0, 0))
    source = _route((Straight(3), bends[0], bends[1], Straight(5)))
    model = Model(Boundary(source.targets, 2), Topology("authored folded", bends, None))
    values = (3 + 5e-8, 0.0, 0.0, 0.0, 5.0)
    result = polish(model, values, 1e-5, lambda: None)
    assert result is not None
    assert result != values
    coordinates = cast(tuple[float, ...], result)
    assert coordinates[1:4] == values[1:4]
    assert model.topology.folds == bends
    assert ordered_mating_caps(model.pieces(coordinates), source.targets)


@pytest.mark.parametrize("failure", ("rank", "frame", "large", "floor", "budget"))
def test_ineligible_or_unrepresentable_correction_never_claims_mating(failure: str) -> None:
    """
    Unreachable position/frame and original size/quality limits stay unresolved without alternate search.
    """
    model = _straight(1)
    values = (10.0 + 5e-8,)
    minimum = 1e-5
    budget = None
    if failure in ("rank", "frame"):
        targets = replace(
            model.source.targets,
            **(
                {"end": model.source.targets.end.translated(Vector3(0, 0, 1), 5e-8)}
                if failure == "rank"
                else {"end_width": Vector3(0, 0, 1)}
            ),
        )
        model = replace(model, source=Boundary(targets, 1))
    elif failure == "large":
        values = (10.001,)
    elif failure == "floor":
        minimum = 10.0
    else:
        values = (10.0 - 5e-8,)
        budget = 10.0 - 3e-8
    assert polish(model, values, minimum, lambda: None, maximum_straight_mm=budget) is None


def test_checkpoint_interrupt_propagates_before_geometry() -> None:
    """
    The caller's source/resource/cancellation failure cannot be treated as a declined polish.
    """
    checkpoint = Mock(side_effect=RuntimeError("original guard"))
    with pytest.raises(RuntimeError, match="original guard"):
        polish(_straight(1), (10 + 5e-8,), 1e-5, checkpoint)


@pytest.mark.parametrize("values", ((math.nan,), (-1.0,), (), (1, 0)))
def test_malformed_allocation_is_rejected(values: tuple[float, ...]) -> None:
    """
    Public correction entry validates complete finite nonnegative coordinates.
    """
    with pytest.raises(ValueError):
        polish(_straight(1), values, 1e-5, lambda: None)


def test_failed_actual_recomposition_cannot_retry_the_affine_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An ineffective linear proposal remains unresolved; a small algebraic residual is no certificate.
    """
    project = Mock(return_value=[0.0])
    monkeypatch.setattr(
        "experiments.experiment_ribbon_fold_route.straight_closure.affine_projection",
        project,
    )
    assert polish(_straight(1), (10 + 5e-8,), 1e-5, lambda: None) is None
    assert project.call_count == 1


@pytest.mark.parametrize("measured", (False, True))
def test_selected_guide_and_cone_allocations_retain_consistent_values_score_and_masks(
    monkeypatch: pytest.MonkeyPatch, measured: bool
) -> None:
    """
    Polish after selection only; the original mask traversal is neither repeated nor expanded.
    """
    bends = (fold(2, 1.2, math.pi / 2, 0, 0), fold(2, 1.2, math.pi / 2, 0, 0))
    source = _route((Straight(3), bends[0], bends[1], Straight(5)))
    boundary = Boundary(source.targets, 2)
    chain = Chain(
        Topology("authored guide", bends, None), (1,), (source.pieces[1].end_pose(),), 2, (0, 0)
    )
    values = (3 + 6e-10, 0.0, 0.0, 0.0, 5.0)
    least = Mock(
        side_effect=lambda hard, right, objective, wanted, size, **kw: (
            [values[0], 0, 5] if size == 3 else None
        )
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_feature_insertion.allocation.least_squares", least
    )
    events = []
    result = (
        allocation.closure_allocation(boundary, chain, values, 1e-5, lambda: None, events.append)
        if measured
        else allocation.fit(boundary, chain, 1e-5, lambda: None, events.append)
    )
    assert result is not None and result.values != values
    assert result.chain is chain and result.masks == 8
    assert ordered_mating_caps(result.route.pieces, source.targets)
    assert result.route.pieces == Model(boundary, chain.topology).pieces(result.values)
    point = allocation.sites(Model(boundary, chain.topology), chain, result.values)[0]
    delta = (
        point.x - chain.targets[0].origin.x,
        point.y - chain.targets[0].origin.y,
        point.z - chain.targets[0].origin.z,
    )
    assert result.score == math.fsum(term * term for term in delta)
    assert least.call_count == (0 if measured else 8)
    assert len(
        [event for event in events if event["stage"] == "feature_allocation" and "mask" in event]
    ) == (0 if measured else 8)
    receipt = next(event for event in events if event["stage"] == "feature_mating_allocation")
    assert receipt["status"] == "closed" and receipt["accepted_affine_corrections"] == 1
    assert receipt["newton_steps"] == 0 and receipt["values"] == result.values
