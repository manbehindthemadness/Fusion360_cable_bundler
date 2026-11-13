"""
Select an untried bend carrying a current outgoing crossing without sweeping alternatives.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import cast

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.material_return_selection import (
    UnreflectedReturns,
    select_fold,
)
from tests.test_ribbon_aesthetic import _route


def _departure(scale: float, bank: float, lane: float) -> tuple[FoldRoute, Penetration]:
    """
    Author material-incidence evidence at the mocked strict-contact boundary, not a geometry pass.
    """
    source = _route(
        (
            fold(2 * scale, 1.2 * scale, 0.6, bank, scale),
            Straight(3 * scale),
            fold(2 * scale, 1.2 * scale, -2.4, -bank, scale),
            Straight(2 * scale),
            fold(2 * scale, 1.2 * scale, 0.5, bank, scale),
        )
    )
    source = replace(source, targets=replace(source.targets, diameter_mm=scale), radius_mm=scale)
    q = lane * scale / 2
    first = cast(CylindricalFold, source.pieces[0].geometry)
    last = cast(CylindricalFold, source.pieces[4].geometry)
    _, first_exit = first.bend_interval(q)
    last_entry, _ = last.bend_interval(q)
    witness = Penetration(
        (0, 4), ((1 + first_exit) / 2, q, 0.0), (last_entry / 2, q, 0.0), Vector3(0, 0, 0)
    )
    return source, witness


@pytest.mark.parametrize("scale", (1e-3, 1.0, 1e3))
@pytest.mark.parametrize("bank", (-0.4, 0.0, 0.4))
@pytest.mark.parametrize("lane", (-1.0, 0.0, 1.0))
def test_repeated_interval_turn_can_yield_to_its_untried_outgoing_carrier(
    scale: float, bank: float, lane: float
) -> None:
    """
    Keep first decisions intact while current departure incidence can select a different untried event.
    """
    source, witness = _departure(scale, bank, lane)
    assert select_fold(source, witness) == 1
    assert UnreflectedReturns(frozenset()).select(source, witness) == 1
    assert UnreflectedReturns(frozenset({2})).select(source, witness) == 1
    assert UnreflectedReturns(frozenset({1})).select(source, witness) == 0
    assert UnreflectedReturns(frozenset({0, 1})).select(source, witness) is None
    assert UnreflectedReturns(frozenset({0, 1, 2})).select(source, witness) is None


@pytest.mark.parametrize("phase", ("before", "curved", "straight", "custom"))
def test_non_departure_or_custom_material_grants_no_untried_alternative(phase: str) -> None:
    """
    Do not reinterpret a partial turn, incoming flat, free straight or specialized material as departure.
    """
    source, witness = _departure(1.0, 0.4, 1.0)
    geometry = cast(CylindricalFold, source.pieces[0].geometry)
    entry, end = geometry.bend_interval(witness.first[1])
    if phase in ("before", "curved"):
        u = entry / 2 if phase == "before" else (entry + end) / 2
        witness = replace(witness, first=(u, witness.first[1], 0.0))
    elif phase == "straight":
        witness = replace(witness, pieces=(1, 4), first=(0.5, witness.first[1], 0.0))
    else:

        class CustomFold(CylindricalFold):
            """
            Retain a distinct material dispatch contract that this base-only choice cannot assume.
            """

        pieces = list(source.pieces)
        pieces[0] = replace(pieces[0], geometry=CustomFold(**asdict(geometry)))
        source = replace(source, pieces=tuple(pieces))
    assert select_fold(source, witness) == 1
    assert UnreflectedReturns(frozenset({1})).select(source, witness) is None


def test_lane_specific_exit_controls_the_incident_choice() -> None:
    """
    A constant material section may leave one occupied lane flat while another remains curved.
    """
    source, witness = _departure(1.0, 0.4, 1.0)
    geometry = cast(CylindricalFold, source.pieces[0].geometry)
    lower_exit = geometry.bend_interval(0.5)[1]
    upper_exit = geometry.bend_interval(-0.5)[1]
    assert lower_exit < upper_exit
    u = (lower_exit + upper_exit) / 2
    after = replace(witness, first=(u, 0.5, 0.0))
    curved = replace(witness, first=(u, -0.5, 0.0))
    policy = UnreflectedReturns(frozenset({1}))
    assert policy.select(source, after) == 0
    assert policy.select(source, curved) is None


@pytest.mark.parametrize("scale", (10.0, 1e3, 1e6))
@pytest.mark.parametrize("error", ("position", "halfturn"))
def test_open_caps_cannot_preempt_current_reclosure_with_an_outside_interval_turn(
    scale: float, error: str
) -> None:
    """
    Small normalized residuals and zero half-turn skew cannot authorize the new incident action.
    """
    source, witness = _departure(scale, 0.4, 1.0)
    target = source.targets
    if error == "position":
        target = replace(target, end=target.end.translated(Vector3(1, 0, 0), scale * 5e-11))
    else:
        tangent = target.end_tangent
        target = replace(target, end_tangent=Vector3(-tangent.x, -tangent.y, -tangent.z))
    source = replace(source, targets=target)
    assert select_fold(source, witness) == 1
    assert UnreflectedReturns(frozenset()).select(source, witness) == 1
    assert UnreflectedReturns(frozenset({1})).select(source, witness) is None
