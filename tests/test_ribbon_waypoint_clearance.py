"""
Verify shared joint projection and nonlinear guidance admission on analytical mechanisms.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.experiment_ribbon_constrained_construction.clearance_motion import ClearanceMotion
from experiments.experiment_ribbon_constrained_construction.clearance_planes import select
from experiments.experiment_ribbon_constrained_construction.waypoint_motion import (
    constrained_reference,
)
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_waypoint_kinematics import checkpoint, objective


def test_reference_projection_retains_caps_and_inequality_without_losing_free_descent() -> None:
    """
    A desired positive collision direction is removed while an independent objective move survives.
    """
    problem = objective()
    values = problem.model.initial
    rows = [[float(i == j) for j in range(len(values))] for i in range(7)]
    reference = [0.0] * len(values)
    reference[6], reference[7] = 1.0, 0.1
    delta = constrained_reference(problem, values, rows, (0.0,) * 7, reference, checkpoint)
    assert delta is not None
    assert delta[:7] == pytest.approx((0.0,) * 7, abs=1e-12)
    assert delta[7] == pytest.approx(0.1)
    for i, (value, change) in enumerate(zip(values, delta)):
        low, high = problem.model.bounds(i)
        assert low - 1e-12 <= value + change <= high + 1e-12


def test_geometry_derived_planes_are_bounded_and_report_omissions() -> None:
    """
    Current complete material, not saved collision pairs, determines all guidance relations.
    """
    problem = objective()
    hardware = Hardware.create(
        problem.model.original.targets, Dimensions.scaled(problem.model.original.targets)
    )
    selection = select(problem.model, hardware, problem.model.initial, checkpoint)
    assert 0 < len(selection.planes) <= 13
    assert selection.represented == len(selection.planes) + len(selection.capacity_omitted)
    assert all(p.residual(problem.model.initial) <= 1e-12 for p in selection.planes)
    assert len({p.name for p in selection.planes}) == len(selection.planes)
    pieces = len(problem.model.original.pieces)
    assert selection.represented + len(selection.unsupported) == (
        2 * pieces + (pieces - 1) * (pieces - 2) // 2
    )


def test_restoration_cannot_return_closed_but_guidance_violating_route() -> None:
    """
    Exact terminal closure alone never admits a route that violates an action's nonlinear bounds.
    """
    problem = objective()
    hardware = Hardware.create(
        problem.model.original.targets, Dimensions.scaled(problem.model.original.targets)
    )
    selection = select(problem.model, hardware, problem.model.initial, checkpoint)
    motion = ClearanceMotion(problem, hardware, lambda event: None)
    motion.planes = selection.planes
    assert motion.restore(problem.model.initial, checkpoint, 0, checkpoint) == problem.model.initial
    first = selection.planes[0]
    motion.planes = (replace(first, minimum_mm=first.gap_mm(problem.model.initial) + 1.0),)
    assert motion.restore(problem.model.initial, checkpoint, 0, checkpoint) is None
