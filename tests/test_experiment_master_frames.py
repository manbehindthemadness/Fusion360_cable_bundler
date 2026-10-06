"""
Protect exact master geometry and bounded shared bank contracts without Fusion.
"""

from __future__ import annotations

import math
from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, dot, magnitude
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_ribbon_cap_transition.master_frames import (
    QUINTIC_MAXIMUM_SLOPE,
    MasterScaffold,
    bounded_bank_angles,
    master_scaffold,
    transport_width,
)
from experiments.experiment_ribbon_cap_transition.regression_cases import comparison_cases
from experiments.experiment_ribbon_cap_transition.screen import _fits
from experiments.experiment_ribbon_cap_transition.tube_solver import solve_tube_ribbon
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame


def _route() -> RoutePreview:
    """
    Supply a small exact straight curve, not an independent ribbon trial.
    """
    curve = CubicBezier(Vector3(0, 0, 0), Vector3(10, 0, 0), Vector3(20, 0, 0), Vector3(30, 0, 0))
    return RoutePreview(
        UUID("00000000-0000-0000-0000-000000000001"),
        "unit scaffold",
        (curve.start, curve.end),
        (curve,),
    )


def test_master_nodes_use_exact_derivatives_and_preserve_signed_ends() -> None:
    """
    Keep positions/tangents exact and return fixed guide widths without search.
    """
    start, end = Vector3(0, 1, 0), Vector3(0, 0, 1)
    scaffold = master_scaffold(_route(), start, end, 1)
    assert len(scaffold.frames) == 32
    assert scaffold.frames[0].origin == Vector3(0, 0, 0)
    assert scaffold.frames[-1].origin == Vector3(30, 0, 0)
    assert scaffold.frames[0].width == start and scaffold.frames[-1].width == end
    assert all(frame.tangent == Vector3(1, 0, 0) for frame in scaffold.frames)
    assert all(magnitude(k) == 0 for k in scaffold.curvature_vectors)
    for frame in scaffold.frames:
        assert abs(dot(frame.width, frame.tangent)) < 1e-12
        assert magnitude(frame.width) == pytest.approx(1)


def test_bank_pass_reserves_future_endpoint_and_interpolation_rate() -> None:
    """
    Do not spend roll budget early and then teleport to the fixed end guide.
    """
    distances = (0.0, 1.0, 2.0, 3.0)
    angles = bounded_bank_angles((0, -2, -2, 0), distances, 1, 1)
    assert angles[0] == 0 and angles[-1] == 1
    assert all(abs(b - a) * QUINTIC_MAXIMUM_SLOPE <= 1 + 1e-12 for a, b in zip(angles, angles[1:]))


def test_impossible_end_roll_is_rejected_without_a_full_turn_fallback() -> None:
    """
    Retain the fixed orientation instead of loosening the rate or rerouting.
    """
    with pytest.raises(UnsafeRibbon, match="end roll"):
        bounded_bank_angles((0, 0, 0), (0, 1, 2), math.pi, 0.1)


def test_transport_is_minimal_rotation_and_rejects_antiparallel_tangents() -> None:
    """
    Preserve width sign through a tangent turn without an arbitrary roll.
    """
    width = transport_width(Vector3(0, 1, 0), Vector3(1, 0, 0), Vector3(0, 0, 1))
    assert magnitude(difference(width, Vector3(0, 1, 0))) < 1e-12
    with pytest.raises(UnsafeRibbon, match="antiparallel"):
        transport_width(Vector3(0, 1, 0), Vector3(1, 0, 0), Vector3(-1, 0, 0))


@pytest.mark.parametrize("distances", ((1, 2, 3), (0, 1, 1), (0, float("nan"), 2)))
def test_malformed_bank_coordinates_do_not_get_a_solution(distances: tuple[float, ...]) -> None:
    """
    Reject invalid scheduling coordinates as data errors rather than geometry passes.
    """
    with pytest.raises(ValueError):
        bounded_bank_angles((0, 0, 0), distances, 0, 1)


def test_tube_authoring_keeps_exact_caps_spacing_and_zero_translated_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test solver wiring with mocked certification/scaffold, not a full-case solve.
    """
    width = Vector3(0, 1, 0)
    case = replace(
        comparison_cases()[0], route=_route(), lines=3, start_width=width, end_width=width
    )
    fits = _fits(case)
    frames = tuple(
        RibbonFrame(Vector3(x, 0, 0), Vector3(1, 0, 0), width, Vector3(0, 0, 1))
        for x in (0, 15, 30)
    )

    def scaffold(
        _route_input: RoutePreview, _start: Vector3, _end: Vector3, _width: float
    ) -> MasterScaffold:
        """
        Supply already-fixed straight nodes without any numerical optimization.
        """
        return MasterScaffold(frames, (Vector3(0, 0, 0),) * 3, (0, 15, 30), (0, 0, 0), 1)

    def certificate(_route_input: RoutePreview, _reach: float) -> None:
        """
        Isolate authoring from the separately tested continuous input contract.
        """
        return None

    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.tube_solver.master_scaffold", scaffold
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.tube_solver.certify_curvature", certificate
    )
    shape = solve_tube_ribbon(case, *fits)
    assert shape.end_lead_mm == shape.spread == 0
    assert shape.maximum_pitch_ratio == pytest.approx(1)
    for i, lane in enumerate(shape.lanes):
        assert lane[0] is fits[0].centers[i] and lane[-1] is fits[1].centers[i]
    moved = replace(fits[0], centers=(Vector3(0, 0.1, 0), *fits[0].centers[1:]))
    with pytest.raises(ValueError, match="fixed ordered cap"):
        solve_tube_ribbon(case, moved, fits[1])
    malformed = replace(fits[0], centers=(Vector3(float("nan"), 0, 0), *fits[0].centers[1:]))
    with pytest.raises(ValueError, match="finite"):
        solve_tube_ribbon(case, malformed, fits[1])


def test_exact_lookup_retains_multiple_curve_traversal() -> None:
    """
    Keep an internal cubic boundary from mixing parameters of neighboring curves.
    """
    route = _route()
    second = CubicBezier(Vector3(30, 0, 0), Vector3(40, 0, 0), Vector3(50, 0, 0), Vector3(60, 0, 0))
    route = replace(route, curves=(*route.curves, second), points=(route.points[0], second.end))
    scaffold = master_scaffold(route, Vector3(0, 1, 0), Vector3(0, 1, 0), 1)
    assert tuple(frame.origin.x for frame in scaffold.frames) == pytest.approx(
        tuple(60 * i / 31 for i in range(32))
    )
