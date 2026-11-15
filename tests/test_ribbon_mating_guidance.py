"""
Keep intended straight mating contact compatible with whole-member correction guidance.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import Region, Side
from experiments.experiment_ribbon_terminal_hardware.check import inspect, mating_frame
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import member_planes
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware, Terminal
from experiments.experiment_ribbon_terminal_hardware.probe_domain import ProbeDomain
from tests.test_ribbon_terminal_protection import _two_folds


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
@pytest.mark.parametrize("terminal", tuple(Terminal))
def test_own_straight_uses_fixed_mating_halfspace_without_positive_clearance(
    scale: float, sign: float, terminal: Terminal
) -> None:
    """
    Independently authored mirrored/scaled routes touch their fixed cap without a false deficit.
    """
    route = _two_folds(scale, sign, 2.0)
    model = SignedJoints(route)
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    box = next(box for box in hardware.boxes if box.terminal is terminal)
    ordinal = 0 if terminal is Terminal.START else len(model.folds)
    member = Region(ordinal, True)
    stale = FeaturePlane(model, member, (member,), box, 1, Side.BEFORE)
    selected = member_planes([stale, stale], model, model.initial)
    assert len(selected) == 1
    plane = selected[0]
    assert plane.reference == member and plane.members == (member,)
    assert plane.box is box and plane.model is model
    assert plane.mating_straight and plane.minimum_gap_mm == 0
    assert plane.family == 0 and plane.side is Side.AFTER
    assert mating_frame(route, box)
    # Outward interval padding remains conservative even at exact mating contact.
    assert abs(plane.gap(model.initial) * model.scale) < 1e-8 * scale
    assert 1e-7 / model.scale - plane.gap(model.initial) > 0
    opposite = next(box for box in hardware.boxes if box.terminal is not terminal)
    assert replace(plane, box=opposite).minimum_gap_mm == 1e-7
    fold = Region(0, False)
    assert replace(plane, reference=fold, members=(fold,)).minimum_gap_mm == 1e-7
    assert replace(plane, members=(member, fold)).minimum_gap_mm == 1e-7


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("extension", (0.01, 1.0))
def test_mating_guidance_does_not_hide_a_real_intrusion_or_grant_a_frame_match(
    scale: float, extension: float
) -> None:
    """
    Extending the final straight through the unchanged cap creates negative guidance and actual intrusion.
    """
    route = _two_folds(scale, 1.0, 2.0)
    model = SignedJoints(route)
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    box = hardware.boxes[1]
    member = Region(len(model.folds), True)
    prototype = FeaturePlane(model, member, (member,), box, 0, Side.AFTER)
    plane = member_planes([prototype], model, model.initial)[0]
    values = list(model.initial)
    values[-1] += scale * extension / model.scale
    moved = model.route(tuple(values))
    assert moved is not None and moved.targets == route.targets
    assert plane.gap(tuple(values)) * model.scale < -scale * extension * 0.9
    assert not mating_frame(moved, box)
    domain = ProbeDomain(moved, ((Terminal.END, len(moved.pieces) - 1),))
    report = inspect(moved, hardware, probe_domain=domain)
    assert report.status != "clear"
    if extension == 1.0:
        assert report.status == "blocked" and report.witness is not None
        assert report.witness.terminal == "end"
