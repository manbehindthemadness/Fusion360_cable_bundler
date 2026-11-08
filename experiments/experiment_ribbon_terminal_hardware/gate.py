"""
Share one bounded strict terminal eligibility check across a complete solver invocation.
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.contracts import TargetPose
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import ProjectionPolicy, Report, inspect
from .model import Dimensions, Hardware


class _Exhausted(RuntimeError):
    """
    Stop only terminal measurement, keeping outer solver resource failures distinct.
    """


class Gate:
    """
    Accept only cleared material routes under one shared 0.1CPU/0.25wall/1024cell allowance.

    Cache immutable route objects by identity, retaining references to prevent ID
    reuse. Cached clearance remains usable after budget exhaustion; a new route
    cannot inherit it. Timers accumulate actual measurement calls, excluding time
    in intervening solver phases. Callers retain their existing overall limits.
    """

    def __init__(
        self,
        source: TargetPose,
        checkpoint: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Freeze scaled proxy dimensions and bind the caller's hard cancellation/source guards.
        """
        self.hardware = Hardware.create(source, Dimensions.scaled(source))
        self.checkpoint, self.record = checkpoint, record
        self.cpu_seconds, self.wall_seconds = 0.0, 0.0
        self.cells, self.cache_hits = 0, 0
        self._cache: dict[int, tuple[FoldRoute, Report]] = {}
        self._refined_unresolved: dict[int, tuple[FoldRoute, Report]] = {}
        self._outcomes = {status: 0 for status in ("clear", "blocked", "unresolved")}

    def permits(
        self,
        route: FoldRoute,
        stage: str,
    ) -> bool:
        """
        Check each changed full-material route once; report blocked and exhausted work without acceptance.
        """
        return self.measure(route, stage).status == "clear"

    def measure(self, route: FoldRoute, stage: str) -> Report:
        """
        Return evidence bound to this immutable route under the same shared check allowance.
        """
        return self._measure(route, stage, 512, ProjectionPolicy.BOX_AXES)

    def certify(self, route: FoldRoute, stage: str) -> Report:
        """
        Refine a completed candidate under the original shared allowance without changing guidance.

        Both policies prove the same material clearance. Incomplete guidance
        evidence cannot substitute for this refined check, or vice versa.
        """
        return self._measure(route, stage, 512, ProjectionPolicy.PIECE_AXES)

    def probe(self, route: FoldRoute, stage: str) -> Report:
        """
        Look for a demonstrated early intrusion in at most32cells of the same shared budget.

        An incomplete probe is not cached as the final route measurement. This
        reserves the existing allowance for first-pass/final certification rather
        than spending512cells on an initializer that may change afterward.
        """
        return self._measure(route, stage, 32, ProjectionPolicy.BOX_AXES)

    def _measure(
        self,
        route: FoldRoute,
        stage: str,
        maximum_cells: int,
        projection_policy: ProjectionPolicy,
    ) -> Report:
        """
        Share route-bound evidence, accumulated work and logging between probe and full checks.
        """
        self.checkpoint()
        if route.targets != self.hardware.targets:
            raise ValueError("Terminal gate cannot change its fixed target inputs")
        cached = self._cache.get(id(route))
        if projection_policy is ProjectionPolicy.PIECE_AXES and (
            cached is None or cached[1].status == "unresolved"
        ):
            cached = self._refined_unresolved.get(id(route))
        if cached is not None:
            assert cached[0] is route
            self.cache_hits += 1
            return cached[1]
        cpu, wall = process_time(), perf_counter()
        calls = 0
        report: Report
        measured_cells: int | None = None

        def bounded() -> None:
            """
            Preserve caller errors and bound accumulated terminal work before each material cell.
            """
            nonlocal calls
            self.checkpoint()
            if (
                self.cpu_seconds + process_time() - cpu >= 0.1
                or self.wall_seconds + perf_counter() - wall >= 0.25
                or self.cells + calls >= 1024
            ):
                raise _Exhausted("Shared terminal measurement allowance exhausted")
            calls += 1

        try:
            bounded()
            report = inspect(
                route,
                self.hardware,
                maximum_cells=min(maximum_cells, 1024 - self.cells),
                checkpoint=bounded,
                projection_policy=projection_policy,
            )
            measured_cells = report.cells_checked
        except _Exhausted:
            report = Report(
                "unresolved", calls, reason="Shared terminal measurement allowance exhausted"
            )
            measured_cells = calls
        finally:
            self.cpu_seconds += process_time() - cpu
            self.wall_seconds += perf_counter() - wall
            self.cells += calls if measured_cells is None else measured_cells
        if maximum_cells == 512 or report.status != "unresolved":
            cache = (
                self._refined_unresolved
                if report.status == "unresolved"
                and projection_policy is ProjectionPolicy.PIECE_AXES
                else self._cache
            )
            cache[id(route)] = route, report
        self._outcomes[report.status] += 1
        self.record(
            {
                "stage": "terminal_hardware",
                "phase": stage,
                "projection_policy": projection_policy.value,
                "status": report.status,
                "report": asdict(report),
                "route": snapshot(route),
            }
        )
        return report

    def detail(self) -> dict[str, Any]:
        """
        Return measured work and declared assumptions separately from other solver timings.
        """
        return {
            "enabled": True,
            "dimensions": asdict(self.hardware.boxes[0].dimensions),
            "cpu_seconds": self.cpu_seconds,
            "wall_seconds": self.wall_seconds,
            "cells": self.cells,
            "checks": sum(self._outcomes.values()),
            "cache_hits": self.cache_hits,
            "outcomes": dict(self._outcomes),
            "limits": {"cpu_seconds": 0.1, "wall_seconds": 0.25, "cells": 1024},
        }
