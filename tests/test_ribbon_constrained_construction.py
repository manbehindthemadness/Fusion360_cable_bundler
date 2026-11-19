"""
Verify coupled clearance/length allocation and advisory diagnostic CPU timing.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_constrained_construction.linear import Problem, Row, minimize
from experiments.experiment_ribbon_constrained_construction.support import (
    fold_support,
    outside_box,
    separated,
)
from experiments.experiment_ribbon_constrained_construction.timing import DiagnosticClock
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


def checkpoint() -> None:
    """
    Supply a no-op boundary for finite, host-independent analytical tests.
    """


@pytest.mark.parametrize("scale", (0.1, 1.0, 100.0))
def test_clearance_creates_optimum_inside_closure_edge(scale: float) -> None:
    """
    Closure-only vertices both collide; simultaneous inequalities retain the interior route allocation.

    Closure x+0.5*y=10 and exclusions x>=2,y>=3 leave a feasible segment.
    Its shortest total-length endpoint x=8.5,y=3 is not a closure-only vertex.
    Neither collision filtering original vertices nor guide fitting to x=0 finds it.
    """
    problem = Problem(
        (1, 1),
        (Row("end closure", (1, 0.5), 10 * scale),),
        (Row("connector exclusion", (1, 0), 2 * scale), Row("self separation", (0, 1), 3 * scale)),
    )
    result = minimize(problem, checkpoint)
    assert result.status == "complete"
    assert result.values == pytest.approx((8.5 * scale, 3 * scale))
    assert result.cost == pytest.approx(11.5 * scale)
    assert result.vertices_checked == result.total_active_sets
    assert all(min(x - 2 * scale, y - 3 * scale) < 0 for x, y in ((0, 20 * scale), (10 * scale, 0)))


def test_contradictory_dependent_equalities_do_not_return_a_route() -> None:
    """
    Dependent endpoint rows are checked with their original right sides.
    """
    problem = Problem((1, 1), (Row("one", (1, 1), 1), Row("two", (2, 2), 3)), ())
    result = minimize(problem, checkpoint)
    assert result.status == "no_checked_vertex" and result.values is None


def test_work_limit_preserves_incomplete_status_and_checkpoint_errors_propagate() -> None:
    """
    Finite algebraic exhaustion and external stops cannot be reported as completed optimization.
    """
    problem = Problem(
        (1, 1), (Row("sum", (1, 1), 10),), (Row("left", (1, 0), 2), Row("right", (0, 1), 3))
    )
    result = minimize(problem, checkpoint, maximum_vertices=1)
    assert result.status == "work_limit" and result.values is not None
    assert result.vertices_checked == 1 < result.total_active_sets

    def stopped() -> None:
        """
        Simulate an external source/cancellation/memory stop.
        """
        raise RuntimeError("external guard")

    with pytest.raises(RuntimeError, match="external guard"):
        minimize(problem, stopped)


@pytest.mark.parametrize("cost", ((0,), (math.inf,), (True,), ()))
def test_malformed_objective_is_rejected(cost: tuple[float, ...]) -> None:
    """
    Positive finite length weights are required for the stated finite-minimum contract.
    """
    with pytest.raises(ValueError):
        Problem(cost, (), ())


@pytest.mark.parametrize("axis", (Vector3(1, 0, 0), Vector3(0, 1, 0), unit(Vector3(1, 2, 3))))
@pytest.mark.parametrize("lengths", ((0.0, 0.0, 0.0), (2.0, 5.0, 3.0)))
def test_fold_support_tracks_actual_occupied_bounds_and_missing_straight_slots(
    axis: Vector3, lengths: tuple[float, ...]
) -> None:
    """
    Predicted affine intervals match independent recomposition, including oblique folds and zero slots.
    """
    source = _route((fold(2, 1.2, 1, 0.2, 0), fold(2, 1.2, -0.7, -0.3, 0)))
    folds = tuple(p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold))
    model = Model(Boundary(source.targets, 2), Topology("analytic", folds, None))
    values = tuple(lengths[i // 2] if i % 2 == 0 else 0.0 for i in range(model.size))
    placed = tuple(p for p in model.pieces(values) if isinstance(p.geometry, CylindricalFold))
    supports = tuple(fold_support(model, i, axis) for i in range(2))
    for piece, support in zip(placed, supports):
        bound = projection(piece, Cell(0, Span(0, 1), Span(-0.6, 0.6), Span(-0.5, 0.5)), axis)
        offset = math.fsum(a * b for a, b in zip(support.translation_mm, lengths))
        # Interval padding depends on world translation. This tighter arithmetic
        # comparison tests affine guidance, not physical dimensional acceptance.
        assert support.low_mm + offset == pytest.approx(bound.low, abs=1e-8)
        assert support.high_mm + offset == pytest.approx(bound.high, abs=1e-8)
    row = separated(*supports)
    measured_gap = (
        supports[1].low_mm
        - supports[0].high_mm
        + math.fsum(
            (b - a) * v
            for a, b, v in zip(supports[0].translation_mm, supports[1].translation_mm, lengths)
        )
    )
    assert math.fsum(a * b for a, b in zip(row.coefficients, lengths)) - row.right == pytest.approx(
        measured_gap
    )
    box = Hardware.create(source.targets, Dimensions.scaled(source.targets)).boxes[1]
    before, after = outside_box(supports[1], box)
    assert before.coefficients == tuple(-c for c in after.coefficients)


def test_cpu_overrun_allows_construction_callback_but_wall_and_host_guards_stop() -> None:
    """
    Over-target CPU can reach geometry output within finite wall/host limits and remains recorded.
    """
    times = {"wall": 0.0, "cpu": 0.0}
    calls: list[str] = []
    clock = DiagnosticClock(
        checkpoint,
        maximum_wall_seconds=2,
        wall_clock=lambda: times["wall"],
        cpu_clock=lambda: times["cpu"],
    )
    times.update(wall=0.8, cpu=0.7)
    clock.check()
    calls.append("diagnostic geometry")
    assert calls == ["diagnostic geometry"]
    assert clock.timing().cpu_overrun_seconds == pytest.approx(0.3)
    times["wall"] = 2
    with pytest.raises(TimeoutError):
        clock.check()

    def host_stop() -> None:
        """
        Preserve host failures independently of diagnostic CPU policy.
        """
        raise RuntimeError("memory stop")

    guarded = DiagnosticClock(host_stop, maximum_wall_seconds=2)
    with pytest.raises(RuntimeError, match="memory stop"):
        guarded.check()


def test_declared_clearance_alternatives_share_one_finite_allocation_pool() -> None:
    """
    Disjunctions choose a feasible arrangement before geometry, without any contact-driven repair.
    """
    from experiments.experiment_ribbon_constrained_construction.disjunction import Work, allocate
    from experiments.experiment_ribbon_constrained_construction.envelopes import Exclusion

    problem = Problem((1, 1), (Row("closure", (1, 0.5), 10),), ())
    groups = (
        Exclusion(
            "hardware",
            ((Row("left alternative", (1, 0), 2),), (Row("right alternative", (0, 1), 30),)),
        ),
        Exclusion("material", ((Row("separate", (0, 1), 3),),)),
    )
    work = Work(maximum_vertices=100, maximum_nodes=20)
    result = allocate(problem, groups, checkpoint, work)
    assert result.values == pytest.approx((8.5, 3))
    assert result.inspection == pytest.approx((10, 0))
    assert result.status == "supplied_constraints_satisfied"
    assert work.vertices <= 100 and work.nodes <= 20
    limited = allocate(problem, groups, checkpoint, Work(maximum_vertices=1, maximum_nodes=1))
    assert limited.status == "work_limit" and limited.values is None


def test_whole_straight_cannot_cross_box_with_both_caps_outside() -> None:
    """
    A single separation alternative must include both straight cap slabs, not choose sides per cap.
    """
    from dataclasses import replace

    from experiments.experiment_ribbon_constrained_construction.envelopes import (
        constraints,
        satisfied,
    )

    source = _route((fold(2, 1.2, math.pi / 2, 0, 0),))
    targets = replace(
        source.targets,
        end=Vector3(5, 0, 0),
        end_tangent=Vector3(1, 0, 0),
        end_width=Vector3(0, 1, 0),
    )
    model = Model(Boundary(targets, 2), Topology("analytical", (source.pieces[0].geometry,), None))
    hardware = Hardware.create(targets, Dimensions(2, 2, 1))
    groups = constraints(model, hardware, checkpoint)
    straight_end_hardware = next(
        group for group in groups if group.name == "part 0 versus end hardware"
    )
    assert not satisfied(straight_end_hardware, (10, 0))
    assert satisfied(straight_end_hardware, (3, 0))
