"""
Use existing straight travel for measured feature redistribution without changing physical acceptance.
"""

from __future__ import annotations

import math
from typing import Any, Literal
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.model import ClosurePolicy, retract_active
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import fold_recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.workspace import redistribution
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def model() -> SignedJoints:
    """
    Author an analytical four-fold route with an interior travel span and clustered turns.
    """
    route = _route(
        (
            Straight(2),
            fold(2, 1.2, 2, 0, 0),
            fold(2, 1.2, 0.5, 0, 0),
            Straight(20),
            fold(2, 1.2, -0.5, 0, 0),
            fold(2, 1.2, -2, 0, 0),
            Straight(2),
        )
    )
    return SignedJoints(route)


def _plane(model: SignedJoints, terminal: Literal["start", "end"]) -> FeaturePlane:
    """
    Supply an explicit own-terminal material feature for algebraic motion tests, not clearance claims.
    """
    hardware = Hardware.create(model.original.targets, Dimensions.scaled(model.original.targets))
    index = 0 if terminal == "start" else len(model.folds) - 1
    region = Region(index, False)
    return FeaturePlane(model, region, (region,), hardware.boxes[terminal == "end"], 0, Side.AFTER)


@pytest.mark.parametrize("terminals", (("start",), ("end",), ("start", "end")))
def test_workspace_motion_separates_features_and_recloses_compact_route(
    model: SignedJoints, terminals: tuple[Literal["start", "end"], ...]
) -> None:
    """
    Project a travel-neutral reference through real geometry without losing caps, fold identity or compactness.
    """
    values = model.initial
    plan = redistribution(model, values, [_plane(model, end) for end in terminals])
    assert plan is not None and plan.donor_slot == 2
    by_full = {full: i for i, full in enumerate(model.indices)}
    assert math.fsum(plan.reference[i] for i in model.straight_indices) == pytest.approx(0)
    assert math.fsum(
        plan.reference[i] for i, full in enumerate(model.indices) if full % 4 == 1
    ) == pytest.approx(0)
    assert plan.reference[by_full[0]] == plan.reference[by_full[16]] == 0
    direction = projected(model, values, model.jacobian(values), [0.0] * 6, list(plan.reference))
    assert direction is not None
    trial = advance(model, values, direction, step_limit(model, values, direction, 0.01))
    closed = retract_active(model, trial, lambda: None, closure_policy=ClosurePolicy.ORDERED_CAPS)
    assert closed is not None
    after = model.route(closed)
    assert after is not None and model.preserves(after)
    assert after.targets is model.original.targets and cap_error(after) < 1e-10
    assert after.material_length_mm <= model.original.material_length_mm * 1.01
    assert all(
        closed[by_full[4 * slot]] > values[by_full[4 * slot]] for slot in plan.receiving_slots
    )
    assert closed[by_full[8]] < values[by_full[8]]


def test_no_reference_without_an_actual_eligible_feature_and_existing_travel(
    model: SignedJoints,
) -> None:
    """
    Do not manufacture a distribution preference from clear, internal or terminal-straight features.
    """
    assert redistribution(model, model.initial, ()) is None
    plane = _plane(model, "start")
    internal = FeaturePlane(model, Region(1, False), (Region(1, False),), plane.box, 0, Side.AFTER)
    straight = FeaturePlane(model, Region(0, True), (Region(0, True),), plane.box, 0, Side.AFTER)
    assert redistribution(model, model.initial, (internal, straight)) is None
    no_travel = tuple(
        0.0 if full == 8 else value for full, value in zip(model.indices, model.initial)
    )
    assert redistribution(model, no_travel, (plane,)) is None


def test_workspace_rejects_mixed_models_and_nonfinite_coordinates(model: SignedJoints) -> None:
    """
    Keep the reference tied to the same immutable source and finite current coordinates.
    """
    other = SignedJoints(model.original)
    with pytest.raises(ValueError, match="same material model"):
        redistribution(model, model.initial, (_plane(other, "start"),))
    with pytest.raises(ValueError, match="finite coordinates"):
        redistribution(model, (float("nan"),) * len(model.initial), ())


def test_feature_motion_then_reclosure_converges_without_repeated_distribution(
    model: SignedJoints, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Use a workspace motion once, then spend the remaining corrections closing its nonlinear caps.
    """
    source = model.original

    def selected(current: SignedJoints, *args: Any, **kwargs: Any) -> FeaturePlane:
        """
        Bind an analytical feature-gap equation to the actual recovery model.
        """
        return _plane(current, "start")

    def gap(plane: FeaturePlane, values: tuple[float, ...]) -> float:
        """
        Require a tenth-millimeter internal gap while keeping real nonlinear cap geometry.
        """
        index = plane.model.indices.index(4)
        return values[index] - (0.1 - 1e-7) / plane.model.scale

    monkeypatch.setattr(FeaturePlane, "create", selected)
    monkeypatch.setattr(FeaturePlane, "gap", gap)
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    terminal.certify.return_value = Report("clear", 1)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.fold_recovery.inspect_contact",
        Mock(return_value=ContactResult("separated", 1)),
    )
    events: list[dict[str, Any]] = []
    result = fold_recovery.recover(
        source,
        Report("blocked", 1),
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm + 1,
        minimum_straight_mm=1e-5,
        remaining_pairs=700,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )
    assert result is not None and result.contact is not None
    assert cap_error(result.route) < 1e-10
    assert result.detail["newton_steps"] <= 24
    assert sum(event["status"] == "workspace_direction" for event in events) == 1
