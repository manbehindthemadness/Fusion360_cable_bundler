"""
Invoke the unchanged frozen experimental trunk candidate under its existing inner limits.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from importlib import import_module
from typing import Any, ContextManager, Protocol, cast

from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver import Result
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve


class CandidateBundle(Protocol):
    """
    Declare the existing frozen context-bundle contract at its development artifact boundary.
    """

    kernel_installed: Callable[[], ContextManager[Any]]
    equations_installed: Callable[[], ContextManager[Any]]
    projection_installed: Callable[[], ContextManager[Any]]
    Policy: Callable[[float], Any]
    mobility_installed: Callable[[Any], ContextManager[Any]]
    returns_installed: Callable[[], ContextManager[Any]]
    caps_installed: Callable[[], ContextManager[Any]]
    schedule_installed: Callable[[], ContextManager[Any]]
    readiness_installed: Callable[[Any], ContextManager[Any]]
    priority_installed: Callable[[], ContextManager[Any]]
    initial_installed: Callable[[Any], ContextManager[Any]]


loaded_bundle: object = import_module("artifacts.verification.resume3185.numerical")
candidate = cast(CandidateBundle, loaded_bundle)


def construct(
    targets: Targets,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    settings: Settings,
    native_point_tolerance_mm: float,
) -> Result:
    """
    Reuse3338/3346's exact context order once, with no extra candidates or recovery work.

    This dependency on a frozen artifact bundle is explicit and development-only.
    The outer gym watchdog adds no inner feasibility allocation or physical pass.
    """
    with ExitStack() as stack:
        stack.enter_context(candidate.kernel_installed())
        evidence = stack.enter_context(candidate.equations_installed())
        stack.enter_context(candidate.projection_installed())
        policy = candidate.Policy(native_point_tolerance_mm)
        for installation in (
            candidate.mobility_installed(evidence),
            candidate.returns_installed(),
            candidate.caps_installed(),
            candidate.schedule_installed(),
            candidate.readiness_installed(policy),
            candidate.priority_installed(),
            candidate.initial_installed(policy),
        ):
            stack.enter_context(installation)
        return solve(
            targets,
            settings,
            checkpoint,
            record,
            native_point_tolerance_mm=native_point_tolerance_mm,
        )
