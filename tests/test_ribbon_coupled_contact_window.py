"""
Keep both occupied carriers available to one bounded material-contact construction.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import plan
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window, select
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("members,expected", (((1, 5), (0, 7)), ((1, 3), (0, 5)), ((2, 5), (2, 7))))
def test_contact_span_keeps_both_carriers_and_all_intervening_material(
    members: tuple[int, int], expected: tuple[int, int]
) -> None:
    """
    A later colliding bend cannot become a fixed boundary outside the repair domain.
    """
    bend = CylindricalFold(1, 0.4, 0, 1.2, 0, 0)
    source = _route(
        (Straight(3), bend, Straight(2), bend, Straight(4), bend, Straight(1), bend, Straight(6))
    )
    window = select(source, members)
    assert (window.begin, window.end) == expected
    assert all(window.begin <= member < window.end for member in members)
    local = window.route
    assert all(a is b for a, b in zip(local.pieces, source.pieces[window.begin : window.end]))
    rebuilt = window.splice(local)
    assert rebuilt.targets is source.targets
    assert all(a is b for a, b in zip(rebuilt.pieces, source.pieces))


@pytest.mark.parametrize("tail,expected", ((1, (0, 5)), (3, (2, 7))))
def test_singleton_blocker_keeps_its_established_incident_pair_policy(
    tail: float, expected: tuple[int, int]
) -> None:
    """
    Hardware intrusion on one bend still chooses its existing larger adjacent workspace.
    """
    bend = CylindricalFold(1, 0.4, 0, 1.2, 0, 0)
    source = _route((Straight(1), bend, Straight(2), bend, Straight(9), bend, Straight(tail)))
    selected = select(source, (3,))
    assert (selected.begin, selected.end) == expected


def test_plan_rejects_one_sided_window_after_validating_both_real_preimages() -> None:
    """
    A custom selector cannot turn an actual two-member crossing into a one-sided repair contract.
    """
    bend = CylindricalFold(1, math.pi, 0, 1.2, 0, 0)
    source = _route((Straight(5), bend, Straight(2), bend, Straight(5)))
    point = Vector3(4, 0, 0)
    first = occupied_coordinates(source.pieces[0], point, 1, 1)
    last = occupied_coordinates(source.pieces[4], point, 1, 1)
    assert first is not None and last is not None
    evidence = ContactResult("penetration", 1, Penetration((0, 4), first, last, point))
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    selector = Mock(return_value=Window(source, 0, 2))
    with pytest.raises(ValueError, match="every current witness"):
        plan(source, evidence, hardware, lambda: None, select_window=selector)
    selector.assert_called_once_with(source, (0, 4))
    accepted = plan(source, evidence, hardware, lambda: None)
    assert (
        accepted is not None
        and accepted.window.begin == 0
        and accepted.window.end == len(source.pieces)
    )
