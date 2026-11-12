"""
Reach late current material crossings through spatial ordering without a saved witness or clearance shortcut.
"""

from __future__ import annotations

import math
from dataclasses import replace
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import regions
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.restoration_order import (
    MaterialFocus,
    ordered_pairs,
)
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import screen
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from tests.test_ribbon_aesthetic import _route


def _late(leading: bool) -> tuple[FoldRoute, tuple[int, int]]:
    """
    Author a late return crossing after a distant three-turn prefix, optionally with an absent first slot.
    """
    prefix = (
        *((Straight(20),) if leading else ()),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(10),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(5),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(7),
        fold(2, 1.2, math.pi / 2, 0, 0),
    )
    source = _route(
        prefix
        + (Straight(10), fold(2, 1.2, math.pi, 0, 1), fold(2, 1.2, math.pi, 0, 1), Straight(10))
    )
    return source, (len(prefix) + 1, len(prefix) + 3)


@pytest.mark.parametrize("leading", (False, True))
def test_motion_priority_reaches_an_actual_late_crossing_without_incoming_material_constraints(
    leading: bool,
) -> None:
    """
    Verify actual current inverses inside the same32pool while a leading slot appears or changes.

    The callback selects one particular late crossing to measure ordering reach;
    it does not assert that the global prefix contains no other physical crossing.
    These are analytical discovery controls, not complete accepted configurations.
    """
    source, original_pair = _late(leading)
    model = StraightSlots(source)
    original_tags = regions(source)
    target_tags = tuple(original_tags[i] for i in original_pair)
    values = (model.initial[0] + 0.2 / model.scale,) + model.initial[1:]
    route = model.route(values)
    assert route is not None
    tags = regions(route)
    target = tuple(tags.index(tag) for tag in target_tags)
    assert target in tuple(ordered_pairs(route, None, lambda: None))[32:]
    focus = MaterialFocus.from_motion(route, model, values, lambda: None)
    assert focus is not None and focus.source is route and len(focus.priority) <= 32
    assert target in focus.priority
    retained: list[Penetration] = []

    def retain(witness: Penetration) -> bool:
        """
        Keep the intended late pair only after the existing checker verifies its original interiors.
        """
        if witness.pieces != target:
            return False
        retained.append(witness)
        return True

    global_result = screen(route, FlatProbe(), 32, lambda: None, retain)
    assert global_result.status == "unresolved" and not retained
    result = screen(route, FlatProbe(), 32, lambda: None, retain, focus=focus)
    assert result.status == "penetration" and result.witness is retained[0]
    assert result.pairs_checked <= 32 and result.witness is not None
    for index in target:
        assert (
            occupied_coordinates(
                route.pieces[index],
                result.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            is not None
        )
    global_order = tuple(ordered_pairs(route, None, lambda: None))
    actual = tuple(ordered_pairs(route, focus, lambda: None))
    assert len(actual) == len(set(actual)) == len(global_order) and set(actual) == set(global_order)
    assert tuple(ordered_pairs(replace(route), focus, lambda: None)) == global_order


def _moved() -> tuple[FoldRoute, StraightSlots, tuple[float, ...]]:
    """
    Supply one exact changed placement for cancellation and stale-identity protocol checks.
    """
    source, _ = _late(True)
    model = StraightSlots(source)
    values = (model.initial[0] + 0.2 / model.scale,) + model.initial[1:]
    route = model.route(values)
    assert route is not None
    return route, model, values


@pytest.mark.parametrize("invalid", ("unchanged", "values", "nan", "targets", "duplicate", "pose"))
def test_missing_or_stale_motion_cannot_invent_current_material_priority(invalid: str) -> None:
    """
    Require exact coordinate ownership and real motion; source mismatches leave ordinary discovery intact.
    """
    route, model, values = _moved()
    if invalid == "unchanged":
        values = model.initial
        route = model.route(values)
        assert route is not None
    elif invalid == "values":
        values = values[:-1]
    elif invalid == "nan":
        values = (math.nan,) + values[1:]
    elif invalid == "targets":
        route = replace(route, targets=replace(route.targets, name="another input"))
    elif invalid == "duplicate":
        route = replace(route, pieces=route.pieces + route.pieces[-1:])
    else:
        route = replace(route, pieces=route.pieces[::-1])
    assert MaterialFocus.from_motion(route, model, values, lambda: None) is None


def test_motion_preparation_keeps_caller_cancellation_and_never_grants_clearance() -> None:
    """
    Guard spatial preparation itself and preserve unresolved misses and shared support exhaustion.
    """
    route, model, values = _moved()
    with pytest.raises(InterruptedError, match="original guard"):
        MaterialFocus.from_motion(
            route, model, values, Mock(side_effect=InterruptedError("original guard"))
        )
    focus = MaterialFocus.from_motion(route, model, values, lambda: None)
    assert focus is not None
    for pool in (0, 1, 6, 32):
        result = screen(route, FlatProbe(), pool, lambda: None, lambda _: False, focus=focus)
        assert (
            result.status == "unresolved"
            and result.witness is None
            and result.pairs_checked <= pool
        )
    probe = FlatProbe(supports=2048)
    result = screen(route, probe, 32, lambda: None, lambda _: True, focus=focus)
    assert result.pairs_checked == 0 and result.status == "unresolved" and probe.supports == 2048
