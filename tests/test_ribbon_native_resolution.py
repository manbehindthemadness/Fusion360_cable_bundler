"""
Separate point comparison tolerance from independent native straight construction.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.solve import Result as Construction
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.native_length import (
    minimum_coordinate,
    minimum_straight_length,
    subminimum_straights,
)
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.smoothing_contact import Result as Smoothed
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("tolerance", (1e-7, 1e-5, 0.01))
@pytest.mark.parametrize("scale", (0.001, 1.0, 1000.0))
def test_constructed_slot_remains_distinguishable_after_endpoint_uncertainty(
    tolerance: float, scale: float
) -> None:
    """
    Keep a full point-comparison interval after reserving one at each endpoint.
    """
    floor = minimum_straight_length(tolerance)
    coordinate = minimum_coordinate(floor, scale)
    assert coordinate is not None
    length = coordinate * scale
    assert length > floor
    assert length - 2 * tolerance > tolerance
    assert math.nextafter(tolerance, math.inf) < 2 * tolerance


@pytest.mark.parametrize("tolerance", (0, -1, True, math.nan, math.inf, 1e308))
def test_invalid_or_overflowing_native_floor_is_rejected(tolerance: float) -> None:
    """
    Reject malformed host dimensions before any construction work.
    """
    with pytest.raises(ValueError):
        minimum_straight_length(tolerance)


def test_only_independent_straights_receive_the_construction_floor() -> None:
    """
    Preserve absent slots and flat leads inside an independently authored bend.
    """
    floor = minimum_straight_length(1e-5)
    route = _route((fold(2, 1.2, 0.8, 0.2, 1), Straight(floor), Straight(1)))
    assert subminimum_straights(route, floor) == (1,)
    assert subminimum_straights(_route((fold(2, 1.2, 0.8, 0.2, 1),)), floor) == ()


@pytest.mark.parametrize(
    "unsafe_first,unsafe_smoothing", ((False, True), (True, True), (False, False))
)
def test_entry_propagates_floor_and_keeps_certificates_with_their_geometry(
    monkeypatch: pytest.MonkeyPatch, unsafe_first: bool, unsafe_smoothing: bool
) -> None:
    """
    Decline tiny optional geometry without borrowing its completed contact evidence.
    """
    tolerance = 1e-5
    first = _route(
        (Straight(tolerance if unsafe_first else 2), fold(2, 1.2, 0.8, 0.2, 1), Straight(3))
    )
    candidate = (
        _route((Straight(tolerance), fold(2, 1.2, 0.8, 0.2, 1), Straight(3)))
        if unsafe_smoothing
        else first
    )
    construction = Construction(
        first, None, "separated", 1, 0.0, 1, 0, ContactResult("separated", 7), 7
    )
    construct = Mock(return_value=construction)
    recovery = Mock(return_value=(construction, None))
    monkeypatch.setitem(vars(solver_v2), "construct", construct)
    monkeypatch.setitem(vars(solver_v2), "recover_construction", recovery)
    monkeypatch.setitem(
        vars(solver_v2),
        "smooth_with_contact",
        Mock(return_value=Smoothed(candidate, {}, ContactResult("separated", 99))),
    )
    result = solver_v2.solve(
        first.targets,
        Settings(first_pass_optimization=False, terminal_hardware=False),
        lambda: None,
        lambda _: None,
        native_point_tolerance_mm=tolerance,
    )
    assert construct.call_args.args[3] == recovery.call_args.args[2] == 3 * tolerance
    assert result.detail["native_point_tolerance_mm"] == tolerance
    assert result.detail["native_minimum_straight_mm"] == 3 * tolerance
    if unsafe_first:
        assert result.route is None and result.inspection_route is first
        assert result.detail["native_subminimum_straights"] == [0]
    else:
        assert result.route is first
        assert result.detail["contact_measurement"]["pairs_checked"] == (
            7 if unsafe_smoothing else 99
        )
        assert result.detail["final_contact_source"] == (
            "unchanged_first_pass" if unsafe_smoothing else "identical_accepted_smoothing_geometry"
        )
