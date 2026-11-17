"""
Keep the manual gym's candidate context order identical to the frozen demonstrations.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, ContextManager

import pytest

from experiments.experiment_ribbon_complete_gym import candidate
from experiments.experiment_ribbon_complete_gym.job import SETTINGS
from experiments.experiment_ribbon_locked_solver.solver import Result
from tests.test_ribbon_complete_execution import checkpoint, targets


def test_adapter_calls_unchanged_candidate_once_inside_original_context_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Neither additional families nor a fallback solve may appear in the gym adapter.
    """
    entered, exited, calls = [], [], []
    evidence = object()
    policies = []

    def factory(context_name: str) -> Callable[..., ContextManager[Any]]:
        """
        Preserve explicit entry/exit order without installing numerical patches.
        """

        @contextmanager
        def installed(*_args: Any) -> Iterator[Any]:
            """
            Yield the shared equation receipt in the same scope as the real adapter.
            """
            entered.append(context_name)
            if context_name in ("readiness_installed", "initial_installed"):
                policies.append(_args[0])
            yield evidence
            exited.append(context_name)

        return installed

    names = (
        "kernel_installed",
        "equations_installed",
        "projection_installed",
        "mobility_installed",
        "returns_installed",
        "caps_installed",
        "schedule_installed",
        "readiness_installed",
        "priority_installed",
        "initial_installed",
    )
    for name in names:
        monkeypatch.setattr(candidate.candidate, name, factory(name))
    expected = Result(None, None, {"status": "analytical_unresolved"}, None)

    def solve(*args: Any, **kwargs: Any) -> Result:
        """
        Record forwarding at the external candidate boundary, returning one unresolved result.
        """
        assert tuple(entered) == names and not exited
        calls.append((args, kwargs))
        return expected

    monkeypatch.setattr("experiments.experiment_ribbon_complete_gym.candidate.solve", solve)
    source = targets().trunk
    events = []
    result = candidate.construct(
        source, checkpoint, events.append, settings=SETTINGS, native_point_tolerance_mm=1e-5
    )
    assert result is expected and len(calls) == 1
    assert calls[0][0] == (source, SETTINGS, checkpoint, events.append)
    assert calls[0][1] == {"native_point_tolerance_mm": 1e-5}
    assert tuple(exited) == tuple(reversed(names))
    assert len(policies) == 2 and policies[0] is policies[1]
    assert isinstance(policies[0], candidate.ConstructionReadiness)
    assert policies[0].point_tolerance_mm == 1e-5
