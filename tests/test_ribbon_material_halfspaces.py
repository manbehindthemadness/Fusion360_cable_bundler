"""
Refresh stale material directions only from current complete-region separation.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Union, cast
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import (
    Region,
    Separation,
    Side,
    regions,
)
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import material_halfspaces
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import FlatPart, FlatSeparation
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from tests.test_ribbon_aesthetic import _route

Constraint = Union[FlatSeparation, MaterialConstraint]


def _bound(scale: float, bank: float, angle: float, radius: float = 2.0) -> FlatSeparation:
    """
    Author two returning straight regions with a deliberately stale longitudinal projection axis.
    """
    source = _route(
        (
            Straight(10 * scale),
            fold(radius * scale, 1.2 * scale, angle, bank, scale),
            Straight(10 * scale),
        )
    )
    source = replace(
        source, targets=replace(source.targets, diameter_mm=scale), radius_mm=0.1 * scale
    )
    model = SignedJoints(source)
    tags = regions(source)
    part = FlatPart(FlatPhase.STRAIGHT, -scale / 2, scale / 2, scale / 2 + 1e-11)
    return FlatSeparation(model, (tags[0], tags[2]), (part, part), Vector3(1, 0, 0))


@pytest.mark.parametrize("scale", (0.01, 1.0, 100.0))
@pytest.mark.parametrize("bank", (-0.3, 0.0, 0.3))
@pytest.mark.parametrize("angle", (-math.pi, math.pi))
@pytest.mark.parametrize("wrapped", (False, True))
def test_already_separated_complete_material_replaces_only_stale_direction(
    scale: float, bank: float, angle: float, wrapped: bool
) -> None:
    """
    Preserve identities, full coverage, wrapper and input ownership while removing an artificial deficit.
    """
    flat = _bound(scale, bank, angle)
    values = flat.model.initial
    old_gap = flat.gap(values, Side.BEFORE)
    assert old_gap < 0
    old: Constraint = MaterialConstraint(flat) if wrapped else flat
    original = [(old, Side.BEFORE)]
    checks = Mock()
    result = material_halfspaces.separated_alternatives(
        original, values, checks, minimum_gap_mm=1e-8
    )
    assert result.changed == (0,) and result.attempts == 1
    new, side = result.constraints[0]
    assert isinstance(new, MaterialConstraint) == wrapped
    chosen = new.bound if isinstance(new, MaterialConstraint) else new
    assert type(chosen) is FlatSeparation
    selected = cast(FlatSeparation, chosen)
    assert selected is not flat and selected.model is flat.model
    assert selected.pair == flat.pair and selected.parts is flat.parts
    assert new.gap(values, side) * flat.model.scale >= 1e-8
    assert flat.gap(values, Side.BEFORE) == old_gap
    assert original == [(old, Side.BEFORE)] and result.constraints is not original
    assert checks.call_count > 3
    assert values == flat.model.initial


@pytest.mark.parametrize("radius", (0.25, 0.5, 0.5000000001))
def test_overlap_touching_and_sub_margin_gap_keep_original_constraint(radius: float) -> None:
    """
    Another axis cannot remove real overlap or invent the required positive clearance margin.
    """
    flat = _bound(1, 0, math.pi, radius)
    original: list[tuple[Constraint, Side]] = [(flat, Side.BEFORE)]
    result = material_halfspaces.separated_alternatives(
        original, flat.model.initial, lambda: None, minimum_gap_mm=1e-8
    )
    assert result.constraints == original
    assert result.constraints[0][0] is flat
    assert result.attempts == 1 and not result.changed


def test_satisfied_and_curved_guidance_are_not_reselected(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Leave satisfied axes and whole-piece curved material unchanged without invoking flat SAT work.
    """
    old = _bound(1, 0.2, math.pi)
    flat = old.separated_alternative(old.model.initial, lambda: None, minimum_gap_mm=1e-8)
    assert flat is not None
    curved = MaterialConstraint(Separation(old.model, old.pair, old.axis))
    original: list[tuple[Constraint, Side]] = [(flat, Side.BEFORE), (curved, Side.AFTER)]
    choose = Mock(side_effect=AssertionError("Unnecessary or unsupported axis selection"))
    monkeypatch.setattr(FlatSeparation, "separated_alternative", choose)
    result = material_halfspaces.separated_alternatives(
        original, old.model.initial, lambda: None, minimum_gap_mm=1e-8
    )
    assert result.constraints == original and result.attempts == 0 and not result.changed
    assert all(new is old for (new, _), (old, _) in zip(result.constraints, original))
    choose.assert_not_called()


def test_newly_occupied_straight_slot_keeps_its_stable_material_identity() -> None:
    """
    Re-enclose a current slot absent from the original primitive list without a witness remap.
    """
    source = _route((fold(2, 1.2, math.pi, 0, 1), Straight(10)))
    model = SignedJoints(source)
    part = FlatPart(FlatPhase.STRAIGHT, -0.5, 0.5, 0.5 + 1e-11)
    flat = FlatSeparation(model, (Region(0, True), Region(1, True)), (part, part), Vector3(1, 0, 0))
    values = list(model.initial)
    values[model.straight_indices[0]] = 2 / model.scale
    current = tuple(values)
    assert Region(0, True) not in regions(source)
    assert flat.gap(current, Side.BEFORE) < 0
    result = material_halfspaces.separated_alternatives(
        [(flat, Side.BEFORE)], current, lambda: None, minimum_gap_mm=1e-8
    )
    assert result.changed == (0,)
    chosen, side = result.constraints[0]
    assert chosen.pair == flat.pair and chosen.parts == flat.parts
    assert chosen.gap(current, side) * model.scale >= 1e-8


def test_cancellation_inside_direction_selection_propagates_without_mutating_guidance() -> None:
    """
    Charge per-direction work to the caller and never retain an interrupted alternative.
    """
    flat = _bound(1, 0.2, math.pi)
    original: list[tuple[Constraint, Side]] = [(flat, Side.BEFORE)]
    checks = 0

    def checkpoint() -> None:
        """
        Stop after entry, when the first candidate direction is being evaluated.
        """
        nonlocal checks
        checks += 1
        if checks == 3:
            raise TimeoutError("original shared CPU stop")

    with pytest.raises(TimeoutError, match="shared CPU"):
        material_halfspaces.separated_alternatives(
            original, flat.model.initial, checkpoint, minimum_gap_mm=1e-8
        )
    assert checks == 3 and original == [(flat, Side.BEFORE)]


@pytest.mark.parametrize("gap", (0.0, -1.0, math.inf, math.nan))
def test_refresh_requires_an_explicit_positive_existing_margin(gap: float) -> None:
    """
    Reject an invalid gap before any material placements or direction work.
    """
    with pytest.raises(ValueError, match="positive material gap"):
        material_halfspaces.separated_alternatives([], (), lambda: None, minimum_gap_mm=gap)
