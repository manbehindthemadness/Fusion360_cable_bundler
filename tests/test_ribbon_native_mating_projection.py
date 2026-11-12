"""
Close authored native-bound material without deleting slots or freezing necessary inward freedom.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_fold_route.straight_closure import correction
from experiments.experiment_ribbon_terminal_hardware import joint_mating, joint_mating_native
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from tests.test_ribbon_aesthetic import _route


def _bound_return(
    scale: float, absent_middle: bool, change: float
) -> tuple[SignedJoints, tuple[float, ...], FoldRoute, float]:
    """
    Author redundant parallel straight directions with one native floor and a measured cap defect.

    This is a mating-mechanics control, not a self-contact or native construction test.
    """
    minimum = 1e-5
    first = math.nextafter(minimum, math.inf)
    bend = fold(2 * scale, 1.2, math.pi, 0, 0)
    middle = () if absent_middle else (Straight(5 * scale),)
    source = _route((Straight(first), bend, *middle, bend, Straight(5 * scale)))
    model = SignedJoints(source)
    floor = minimum_coordinate(minimum, model.scale)
    assert floor is not None
    values = list(model.initial)
    values[0] = floor
    values[model.straight_indices[-1]] += change / model.scale
    coordinates = tuple(values)
    route = model.route(coordinates)
    assert route is not None and not ordered_mating_caps(route.pieces, route.targets)
    return model, coordinates, route, minimum


@pytest.mark.parametrize("scale", (0.5, 1.0, 20.0, 1000.0))
@pytest.mark.parametrize("absent_middle", (False, True))
def test_native_floor_is_respected_while_other_occupied_slots_close_the_caps(
    monkeypatch: pytest.MonkeyPatch, scale: float, absent_middle: bool
) -> None:
    """
    An unconstrained least-norm defect correction would shrink the first slot below its native floor.
    """
    model, values, route, minimum = _bound_return(scale, absent_middle, 5e-8)
    unbounded = correction(
        route.pieces,
        route.targets,
        tuple(values[i] * model.scale for i in model.straight_indices),
        lambda: None,
    )
    assert unbounded is not None and values[0] * model.scale + unbounded[0] <= minimum
    original = Mock(side_effect=AssertionError("Select one bounded kernel before projection"))
    monkeypatch.setitem(vars(joint_mating), "correction", original)
    restored = joint_mating.restore(
        route,
        model,
        values,
        (0.0,) * 6,
        lambda: None,
        minimum_straight_mm=minimum,
        length_ceiling_mm=None,
        fixed=frozenset(),
    )
    assert restored is not None
    placed = model.route(restored)
    assert placed is not None and ordered_mating_caps(placed.pieces, placed.targets)
    assert placed.targets is route.targets and model.preserves(placed)
    assert all(
        restored[i] == values[i] for i in range(len(values)) if i not in model.straight_indices
    )
    assert all(
        restored[i] == 0 if values[i] == 0 else restored[i] * model.scale > minimum
        for i in model.straight_indices
    )
    original.assert_not_called()


@pytest.mark.parametrize("scale", (0.5, 1.0, 20.0))
def test_native_floor_does_not_freeze_a_slot_that_can_grow(scale: float) -> None:
    """
    Bounds retain positive inward motion instead of treating every active floor as a permanent pin.
    """
    model, values, route, minimum = _bound_return(scale, False, -5e-8)
    restored = joint_mating.restore(
        route,
        model,
        values,
        (0.0,) * 6,
        lambda: None,
        minimum_straight_mm=minimum,
        length_ceiling_mm=None,
        fixed=frozenset(),
    )
    assert restored is not None and restored[0] > values[0]
    placed = model.route(restored)
    assert placed is not None and ordered_mating_caps(placed.pieces, placed.targets)


@pytest.mark.parametrize("all_fixed", (False, True))
def test_real_bounded_projection_preserves_permanent_native_pins(all_fixed: bool) -> None:
    """
    A fixed floor remains exact; all fixed slots leave an unresolved defect instead of moving targets.
    """
    model, values, route, minimum = _bound_return(1, False, 5e-8)
    fixed = frozenset(model.straight_indices) if all_fixed else frozenset({0})
    restored = joint_mating.restore(
        route,
        model,
        values,
        (0.0,) * 6,
        lambda: None,
        minimum_straight_mm=minimum,
        length_ceiling_mm=None,
        fixed=fixed,
    )
    if all_fixed:
        assert restored is None
    else:
        assert restored is not None and restored[0] == values[0]
        placed = model.route(restored)
        assert placed is not None and ordered_mating_caps(placed.pieces, placed.targets)


def test_declined_projection_and_permanent_pins_cannot_allocate_another_kernel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep one projector call, original fixed coordinates and source cancellation authoritative.
    """
    model, values, route, minimum = _bound_return(1, False, 5e-8)
    original = Mock(side_effect=AssertionError("No affine fallback after bounded decline"))
    projector = Mock(return_value=None)
    monkeypatch.setitem(vars(joint_mating), "correction", original)
    monkeypatch.setitem(vars(joint_mating_native), "active_step", projector)
    assert (
        joint_mating.restore(
            route,
            model,
            values,
            (0.0,) * 6,
            lambda: None,
            minimum_straight_mm=minimum,
            length_ceiling_mm=None,
            fixed=frozenset(),
        )
        is None
    )
    assert projector.call_count == 1
    original.assert_not_called()
    projector.reset_mock()
    assert (
        joint_mating.restore(
            route,
            model,
            values,
            (0.0,) * 6,
            lambda: None,
            minimum_straight_mm=minimum,
            length_ceiling_mm=None,
            fixed=frozenset(model.straight_indices),
        )
        is None
    )
    with pytest.raises(InterruptedError, match="source guard"):
        joint_mating.restore(
            route,
            model,
            values,
            (0.0,) * 6,
            Mock(side_effect=InterruptedError("source guard")),
            minimum_straight_mm=minimum,
            length_ceiling_mm=None,
            fixed=frozenset(),
        )
