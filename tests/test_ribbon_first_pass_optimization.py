"""
Verify first-pass length optimization independently of aesthetic smoothing.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_aesthetic.layout_model import Model as AestheticModel
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold
from experiments.experiment_ribbon_joint_route.optimization import (
    CONTACT_PAIRS,
    GuideProgress,
    optimize,
)
from experiments.experiment_ribbon_locked_solver import Settings, solve
from experiments.experiment_ribbon_spline_guide.guide import Guide


def _route(geometries: tuple[Piece, ...]) -> FoldRoute:
    """
    Derive fixed ordered targets from analytical material geometry without archive dependencies.
    """
    first = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pose = first
    pieces = []
    for geometry in geometries:
        piece = PlacedPiece(pose, geometry, "analytical first pass")
        pieces.append(piece)
        pose = piece.end_pose()
    target = Targets(
        "analytical first pass",
        first.origin,
        pose.origin,
        first.tangent,
        pose.tangent,
        first.width,
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(target, tuple(pieces), 1.0)


def _spatial_route() -> FoldRoute:
    """
    Supply nonparallel travel around two differently banked folds.
    """
    return _route(
        (
            Straight(6),
            fold(1, 1.2, 0.9, 0.3, 0),
            Straight(8),
            fold(1.5, 1.2, -1.4, -0.25, 0),
            Straight(10),
        )
    )


def test_first_pass_contracts_nonparallel_geometry_with_free_angles_and_banks() -> None:
    """
    Shorten an actual material route while preserving caps, guide progress and local compatibility.
    """
    source = _spatial_route()
    guide = Guide.create(source.targets)
    events: list[dict[str, Any]] = []
    result = optimize(source, guide, lambda: None, events.append)
    assert result.accepted > 0 and result.route.material_length_mm < source.material_length_mm
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
    assert result.route.targets == source.targets
    assert result.guide_cost <= result.initial_guide_cost + 1e-10
    before = [
        (p.geometry.angle_radians, p.geometry.bank_radians)
        for p in source.pieces
        if isinstance(p.geometry, CylindricalFold)
    ]
    after = [
        (p.geometry.angle_radians, p.geometry.bank_radians)
        for p in result.route.pieces
        if isinstance(p.geometry, CylindricalFold)
    ]
    assert after != before
    assert all(
        math.nextafter(p.geometry.radius_mm, math.inf) >= source.radius_mm
        for p in result.route.pieces
        if isinstance(p.geometry, CylindricalFold)
    )
    assert any(e["status"] == "accepted" for e in events)
    assert result.contacts <= 12 and result.iterations <= 16


@pytest.mark.parametrize("status", ("unresolved", "penetration"))
def test_failed_optimization_contact_retains_the_validated_first_pass(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    A cheaper contact budget can reject a candidate but cannot waive full-profile separation.
    """
    calls: list[int] = []

    def contact(
        route: FoldRoute, *, maximum_pairs: int, checkpoint: Callable[[], None]
    ) -> ContactResult:
        """
        Represent a bounded unsuccessful optimization-only certificate.
        """
        del route
        checkpoint()
        calls.append(maximum_pairs)
        return ContactResult(status, maximum_pairs)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_joint_route.optimization.inspect_contact", contact
    )
    source = _spatial_route()
    result = optimize(source, Guide.create(source.targets), lambda: None, lambda event: None)
    assert result.route is source and result.accepted == 0
    assert calls and all(pairs == CONTACT_PAIRS for pairs in calls)
    assert len(calls) <= 12


def test_routing_can_reverse_angles_without_changing_aesthetic_bounds() -> None:
    """
    Keep routing degrees of freedom distinct from the existing aesthetic policy.
    """
    source = _spatial_route()
    routing, aesthetic = FlexibleModel(source), AestheticModel(source)
    assert routing.bounds(1) == (-math.pi, math.pi)
    assert aesthetic.bounds(1) == (1e-6, math.pi)
    assert routing.bounds(5) == (-math.pi, math.pi)
    assert aesthetic.bounds(5) == (-math.pi, -1e-6)
    assert aesthetic.label_prefix == "Layout-relaxed material piece"
    values = list(routing.initial)
    values[1] = values[5] = 0.0
    flattened = routing.pieces(tuple(values))
    assert len(flattened) == 1 and isinstance(flattened[0].geometry, Straight)


def test_first_pass_optimization_runs_when_aesthetic_smoothing_is_disabled() -> None:
    """
    Account routing optimization inside construction regardless of the aesthetic setting.
    """
    target = Targets(
        "cold corner",
        Vector3(0, 0, 0),
        Vector3(10, 0, 12),
        Vector3(1, 0, 0),
        Vector3(0, 0, 1),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        1,
        1.0,
    )
    result = solve(target, Settings(0), lambda: None, lambda event: None)
    assert result.route is result.first_pass and result.route is not None
    assert "optimization" in result.detail["construction"]
    assert result.detail["stages"] == {"smoothing": "disabled"}


@pytest.mark.parametrize("smoothing", (0, 1))
def test_disabling_first_pass_optimization_skips_only_length_optimization(
    monkeypatch: pytest.MonkeyPatch, smoothing: float
) -> None:
    """
    Return a valid coarse route and independently honor the aesthetic smoothing setting.
    """

    def forbidden(*args: Any, **kwargs: Any) -> None:
        """
        Detect an optimizer call despite the explicit disabled control.
        """
        del args, kwargs
        raise AssertionError("First-pass optimization is disabled")

    monkeypatch.setattr("experiments.experiment_ribbon_joint_route.solve.optimize", forbidden)
    source = _spatial_route()
    result = solve(
        source.targets, Settings(smoothing, False, False), lambda: None, lambda event: None
    )
    assert result.route is not None and result.first_pass is not None
    assert result.detail["construction"]["optimization"] == {"reason": "disabled", "seconds": 0.0}
    assert cap_error(result.route) < 1e-7
    assert (result.detail["stages"].get("smoothing") == "disabled") == (smoothing == 0)


def test_direct_straight_and_external_resource_stops_are_preserved() -> None:
    """
    Leave a minimal straight unchanged and propagate a run controller's interruption.
    """
    source = _route((Straight(10),))
    guide = Guide.create(source.targets)
    result = optimize(source, guide, lambda: None, lambda event: None)
    assert result.route is source and result.accepted == result.contacts == 0
    assert GuideProgress.capture(source, guide).cost(source) < 1e-12

    def stop() -> None:
        """
        Model a hard external source/time/memory stop.
        """
        raise TimeoutError("first pass unit stop")

    with pytest.raises(TimeoutError, match="first pass unit stop"):
        optimize(source, guide, stop, lambda event: None)


def test_expensive_coarse_certificate_keeps_valid_geometry_without_optimization_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Avoid repeated bounded checks on a case whose coarse proof already exceeds the optional budget.
    """

    def forbidden(*args: Any, **kwargs: Any) -> ContactResult:
        """
        Detect an unnecessary optimization contact invocation.
        """
        del args, kwargs
        raise AssertionError("Baseline exceeds optimization work budget")

    monkeypatch.setattr(
        "experiments.experiment_ribbon_joint_route.optimization.inspect_contact", forbidden
    )
    source = _spatial_route()
    result = optimize(
        source,
        Guide.create(source.targets),
        lambda: None,
        lambda event: None,
        baseline_contact=ContactResult("separated", CONTACT_PAIRS + 1),
    )
    assert result.route is source and result.reason == "baseline_contact_budget"
    assert result.iterations == result.accepted == result.contacts == 0
