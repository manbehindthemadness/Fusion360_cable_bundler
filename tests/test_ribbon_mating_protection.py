"""
Separate actual mating-boundary guidance from whole-bend hardware clearance on authored material.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy, cap_region
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.check import inspect, mating_frame
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware, Terminal
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import prepare, uncovered
from tests.test_ribbon_aesthetic import _route


def _halfturn(scale: float, sign: float) -> FoldRoute:
    """
    Author one regular half turn with flat leads and exact independently declared cap frames.
    """
    source = _route((fold(2 * scale, 1.2 * scale, sign * math.pi, 0, scale),))
    return replace(source, targets=replace(source.targets, diameter_mm=scale), radius_mm=scale)


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_clear_halfturn_keeps_mating_boundary_without_claiming_whole_bend_support(
    scale: float, sign: float
) -> None:
    """
    Common cap points forbid positive whole-piece gaps even when finite cells prove hardware clearance.
    """
    source = _halfturn(scale, sign)
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    cell = Cell(
        0,
        Span(0, 1),
        Span(-source.half_width_mm, source.half_width_mm),
        Span(-scale / 2, scale / 2),
    )
    report = inspect(source, hardware, maximum_cells=512)
    assert report.status == "clear"
    guards = prepare(model, hardware, [], lambda: None)
    assert len(guards) == 2
    for guard in guards:
        box = guard.plane.box
        at_end = box.terminal is Terminal.END
        point = source.pieces[0].surface(1.0 if at_end else 0.0, 0.0)[0]
        local = tuple(dot(difference(point, box.pose.origin), axis) for axis in box.axes)
        assert all(bound.low <= value <= bound.high for bound, value in zip(box.bounds, local))
        assert mating_frame(source, box)
        assert not cap_region(source.pieces[0], cell, at_end, CapPolicy.ANALYTIC_SUPPORT)
        gap = guard.plane.gap(model.initial)
        assert gap < 0
        assert guard.minimum_gap == gap
        assert guard.residual(model.initial) == 0
        assert guard.basis.value == "source_mating_boundary"
        assert not hasattr(guard, "status") and not hasattr(guard, "witness")


@pytest.mark.parametrize("terminal", (Terminal.START, Terminal.END))
@pytest.mark.parametrize("defect", ("position", "frame", "nonfinite"))
def test_unmatched_or_nonfinite_cap_cannot_inherit_mating_boundary_guidance(
    terminal: Terminal, defect: str
) -> None:
    """
    Piece identity alone is insufficient; the actual ordered terminal frame must match.
    """
    source = _halfturn(1, 1)
    name = "start" if terminal is Terminal.START else "end"
    if defect == "position":
        source = replace(
            source,
            targets=replace(
                source.targets,
                **{name: getattr(source.targets, name).translated(Vector3(0, 1, 0), 1e-4)},
            ),
        )
    elif defect == "frame":
        source = replace(
            source, targets=replace(source.targets, **{name + "_width": Vector3(0, 0, 1)})
        )
    else:
        piece = source.pieces[0]
        source = replace(
            source,
            pieces=(replace(piece, pose=replace(piece.pose, origin=Vector3(math.nan, 0, 0))),),
        )
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    guard = next(
        g for g in prepare(model, hardware, [], lambda: None) if g.plane.box.terminal is terminal
    )
    assert not mating_frame(source, guard.plane.box)
    assert guard.minimum_gap == 1e-7 / model.scale
    assert guard.basis.value == "enclosure_clearance"


def test_nonmating_folds_and_witnessed_members_keep_their_ordinary_rules() -> None:
    """
    Terminal straights prevent a remote fold inheriting cap allowance; actual observed members override it.
    """
    source = _route((Straight(2), fold(2, 1.2, math.pi, 0, 1), Straight(2)))
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    guards = prepare(model, hardware, [], lambda: None)
    assert len(guards) == 2
    assert all(
        g.minimum_gap == 1e-7 / model.scale and g.basis.value == "enclosure_clearance"
        for g in guards
    )
    owned = _halfturn(1, 1)
    owner = SignedJoints(owned)
    boxes = Hardware.create(owned.targets, Dimensions.scaled(owned.targets))
    protected = prepare(owner, boxes, [], lambda: None)
    observed = [protected[0].plane]
    remainder = prepare(owner, boxes, observed, lambda: None)
    assert len(remainder) == 1 and remainder == uncovered(protected, observed)


def test_mating_boundary_preference_cannot_hide_actual_hardware_penetration() -> None:
    """
    The same matched caps can retain non-worsening guidance while the strict full checker rejects intrusion.
    """
    source = _route((replace(fold(2, 1.2, math.pi, 0, 1), after_mm=2.0),))
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    guards = prepare(model, hardware, [], lambda: None)
    assert all(g.residual(model.initial) <= 0 for g in guards)
    report = inspect(source, hardware, maximum_cells=512)
    assert report.status == "blocked" and report.witness is not None
    assert report.witness.terminal == "start" and report.witness.point.x < 0
