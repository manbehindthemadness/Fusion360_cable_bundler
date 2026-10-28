"""
Check cold-side selection and collision-filtered endpoint steps.
"""

from __future__ import annotations

from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import clear_initialization
from experiments.experiment_ribbon_route_discovery.families import Seed


def _case() -> EndpointCase:
    """
    Provide one fixed neutral boundary for actual transport checks.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase("clear control", Vector3(0, 0, 0), Vector3(100, 0, 0), x, x, y, y)


def test_selection_prefers_opposite_side_but_requires_spatial_difference() -> None:
    """
    Side sign alone cannot turn a duplicate route into a second initialization.
    """
    rows = tuple(
        clear_initialization.ClearSeed(
            Seed(i, (0.0,) * 9 + (1.0,), score, (offset, 0.0, 0.0)), side
        )
        for i, score, offset, side in ((0, 1, 0, 1), (1, 2, 0.1, -1), (2, 3, 1, 1), (3, 4, 2, -1))
    )
    assert [row.seed.index for row in clear_initialization.choose(rows)] == [0, 3]
    assert clear_initialization.choose(tuple(reversed(rows))) == clear_initialization.choose(rows)
    assert [row.seed.index for row in clear_initialization.choose(rows[:3])] == [0, 2]
    assert clear_initialization.choose(()) == ()


def test_transition_samples_are_interior_and_preserve_the_box() -> None:
    """
    Sample the whole coordinate update without changing either endpoint vector.
    """
    before, after = (0.0,) * 10, (4.0,) * 10
    assert clear_initialization.transition_parameters(before, after) == (
        (1.0,) * 10,
        (2.0,) * 10,
        (3.0,) * 10,
    )
    with pytest.raises(ValueError):
        clear_initialization.transition_parameters((), after)


def test_clear_closed_route_skips_unnecessary_polishing() -> None:
    """
    A closed clear route must not spend iterations chasing numerical roundoff.
    """
    values = (0.0,) * 9 + (1.0,)
    seed = clear_initialization.ClearSeed(Seed(0, values, 0.0, (0.0,) * 3), 0)
    path, metrics = clear_initialization.refine(_case(), seed, lambda: None)
    assert metrics["evaluations"] == 2 and metrics["audits"] == 2
    assert metrics["trials"] == [] and metrics["coordinates"] == values
    assert path.states[-1][:3] == pytest.approx((100, 0, 0))


def test_colliding_proposals_cannot_replace_clear_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Force contact after the initial audit and retain the original path despite fitting.
    """
    calls = 0

    def audit(*_args: Any, **_kwargs: Any) -> tuple[dict[str, bool], tuple[()]]:
        """
        Model a clear initial route followed by blocked proposals and fine replay.
        """
        nonlocal calls
        calls += 1
        return {"contact_detected": calls > 1}, ()

    monkeypatch.setattr(clear_initialization.contact, "audit", audit)
    values = (1.0,) + (0.0,) * 8 + (1.0,)
    seed = clear_initialization.ClearSeed(Seed(0, values, 1.0, (0.0,) * 3), 1)
    _, metrics = clear_initialization.refine(_case(), seed, lambda: None)
    assert metrics["coordinates"] == values
    assert any(trial.get("clear_step") is False for trial in metrics["trials"])
    assert not any(trial.get("accepted") for trial in metrics["trials"])
    assert metrics["evaluations"] <= 520
