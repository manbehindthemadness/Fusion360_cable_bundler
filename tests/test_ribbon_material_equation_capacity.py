"""
Use original physical equation capacity without an unrelated material-bound count ceiling.
"""

from __future__ import annotations

import math
from itertools import combinations
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    MaterialGuidance,
    ReturnLength,
)
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate


@pytest.mark.parametrize(
    ("requested", "allow_release"), ((5, True), (9, True), (10, False), (10, True), (11, True))
)
def test_material_bounds_use_only_remaining_original_physical_equation_capacity(
    requested: int, allow_release: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Retain independently identified guidance beyond four without exceeding thirteen physical rows.

    Real ordered material and complete constraints follow controlled projection
    and measurement boundaries. The supplied measurements are protocol doubles,
    not independent geometry or occupancy validation. Open caps must still keep
    native/hardware/contact certification unattempted throughout this test.
    """
    pieces = tuple(
        item for _ in range(5) for item in (Straight(5), fold(2, 1.2, math.pi / 2, 0, 0))
    ) + (Straight(5),)
    source = _route(pieces)
    terminal = _gate(source)
    pairs = iter(combinations(range(0, len(source.pieces), 2), 2))
    initial = next(pairs)
    raw_equations: list[Callable[[tuple[float, ...]], tuple[float, ...]]] = []
    observed_rows: list[int] = []
    projection_calls = 0
    invalidated = Mock()

    def violated(_bound: MaterialConstraint, _values: tuple[float, ...], _side: Side) -> float:
        """
        Isolate the capacity boundary when no current complete bound has positive slack.
        """
        return -1.0

    if not allow_release:
        monkeypatch.setattr(MaterialConstraint, "gap", violated)

    def evaluation(
        equations: Callable[[tuple[float, ...]], tuple[float, ...]],
        _admissible: Callable[[tuple[float, ...]], bool],
    ) -> SimpleNamespace:
        """
        Retain actual row assembly while isolating finite descent from endpoint fitting.
        """
        raw_equations.append(equations)
        return SimpleNamespace(
            equations=lambda values: (math.exp(-values[0]),) + (0.0,) * 6,
            admissible=lambda values: all(math.isfinite(value) for value in values),
            constraints_changed=invalidated,
        )

    def projection(
        _model: Any, values: tuple[float, ...], *_args: Any, **_kwargs: Any
    ) -> tuple[float, ...] | None:
        """
        Allow only the declared original motion prefix and inspect every actual physical-row count.
        """
        nonlocal projection_calls
        projection_calls += 1
        assert raw_equations
        evaluate = raw_equations[-1]
        observed_rows.append(len(evaluate(values)))
        if projection_calls >= requested:
            return None
        return (0.01,) + (0.0,) * (len(values) - 1)

    def witness(route: FoldRoute, pair: tuple[int, int]) -> Penetration:
        """
        Supply declared interior material coordinates through the controlled checker boundary.
        """
        return Penetration(
            pair, (0.5, 0.0, 0.0), (0.5, 0.0, 0.0), route.pieces[pair[0]].surface(0.5, 0)[0]
        )

    def discover(
        route: FoldRoute,
        _probe: FlatProbe,
        maximum_pairs: int,
        checkpoint: Callable[[], None],
        retain: Callable[[Penetration], bool],
        **_options: Any,
    ) -> ContactResult:
        """
        Offer one different complete material pair after each allowed update, charging one comparison.
        """
        checkpoint()
        assert maximum_pairs > 0
        if projection_calls == 10:
            previous_release = next(
                event for event in events if event["status"] == "material_guidance_released"
            )
            tags = regions(route)
            pair = tuple(tags.index(Region(**tag)) for tag in previous_release["pair"])
            assert len(pair) == 2
            measured = witness(route, (pair[0], pair[1]))
        else:
            measured = witness(route, next(pairs))
        assert retain(measured)
        return ContactResult("penetration", 1, witness=measured)

    monkeypatch.setitem(vars(joint_contact), "JointEvaluation", evaluation)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projection)
    monkeypatch.setitem(vars(joint_contact), "screen_restoration", discover)
    monkeypatch.setitem(
        vars(joint_contact),
        "joint_jacobian",
        lambda _model, values, *_args, **_kwargs: [[0.0] * len(values) for _ in range(7)],
    )
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        witness(source, initial),
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=512,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        maximum_newton_steps=24,
        mode=MaterialGuidance(0, length=ReturnLength.RESTORATION_GOAL),
    )
    assert result is not None and result.detail["status"] == "unresolved"
    detail = result.detail
    assert detail["terminal_protection_constraints"] == 4
    assert detail["flat_constraints"] == min(requested, 9)
    updates = requested - 1 if allow_release else min(requested - 1, 9)
    releases = max(0, requested - 9) if allow_release else 0
    assert detail["newton_steps"] == updates <= 24
    assert detail["contact_pairs"] == detail["restoration_screen_pairs"] == updates
    assert detail["stop_reason"] == (
        "physical_inequality_capacity" if not allow_release else "linear_projection_infeasible"
    )
    assert observed_rows and max(observed_rows) <= 19
    added = sum(e["status"] == "constraint_added" for e in events)
    assert added == min(requested, 9) - 1 + releases
    assert detail["material_guidance_releases"] == releases
    assert invalidated.call_count >= added
    if requested == 11:
        released = next(
            event for event in events if event["status"] == "material_guidance_released"
        )
        assert events[-1]["status"] != "separated"
        additions = [event for event in events if event["status"] == "constraint_added"]
        assert additions[-1]["pair"] == released["pair"]
        assert additions[-1]["parts"] == released["parts"]
    assert detail["contacts"] == 0
    terminal.certify.assert_not_called()
