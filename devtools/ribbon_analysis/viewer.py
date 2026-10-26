"""
Display explicit candidates in an owned Fusion component with bounded work.

No numbered fixture lookup,global scratch name,solver run or native construction.
This optional boundary imports Fusion;the numerical API does not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

from .api import Candidate, Evidence, analyze
from .budget import NativeBudget
from .provenance import mark_loaded, source_fingerprints, verify_loaded
from .region_graphics import draw_evidence


@dataclass(frozen=True)
class ViewLimits:
    """
    Set explicit scheduling/RSS bounds;these never authorize additional candidates.
    """

    max_candidates: int
    seconds_per_candidate: float
    total_seconds: float
    rss_kib: int = 2 * 1024 * 1024
    intervals: int = 512

    def __post_init__(self) -> None:
        """
        Reject malformed budgets before creating graphics or station arrays.
        """
        if (
            isinstance(self.max_candidates, bool)
            or not isinstance(self.max_candidates, int)
            or self.max_candidates < 1
        ):
            raise ValueError("Declare a positive candidate count.")
        if any(
            not math.isfinite(v) or v <= 0 for v in (self.seconds_per_candidate, self.total_seconds)
        ):
            raise ValueError("Declare positive finite time limits.")
        if isinstance(self.rss_kib, bool) or not isinstance(self.rss_kib, int) or self.rss_kib <= 0:
            raise ValueError("Declare a positive RSS ceiling.")
        if (
            isinstance(self.intervals, bool)
            or not isinstance(self.intervals, int)
            or not 16 <= self.intervals <= 1024
        ):
            raise ValueError("Use16..1024analysis intervals.")


class Viewer:
    """
    Own only children created under an explicitly supplied development component.

    The caller authorizes/creates that component. Existing geometry,visibility and
    unrelated documents are untouched. Failed work remains in records and latches
    a stop;create a renewed viewer only after reviewing its specific stop reason.
    """

    def __init__(self, component: Any, document: Any, limits: ViewLimits) -> None:
        """
        Bind an owned live component without creating geometry or finding fixtures.
        """
        self.component = component
        self.document = document
        self.limits = limits
        self.records: dict[str, dict[str, Any]] = {}
        self.stop_reason: str | None = None
        self.sources = source_fingerprints()
        self._active()
        if component.parentDesign != adsk.core.Application.get().activeProduct:
            raise ValueError("Owned component must belong to the active design.")

    def _active(self) -> None:
        """
        Refuse writes after document/command/source changes,without automatic reload.
        """
        app = adsk.core.Application.get()
        if (
            app.activeDocument != self.document
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Expected the supplied owned document and an idle command.")
        verify_loaded()

    def add(self, candidate: Candidate, transform: Any = None) -> dict[str, object]:
        """
        Analyze and display one explicit candidate once,retaining failed stage times.

        Expected invalid regions are diagnostic results,not construction failures.
        A failed display or exhausted budget stops scheduling further candidates.
        """
        self._active()
        if self.stop_reason:
            raise RuntimeError(self.stop_reason)
        if candidate.identifier in self.records:
            raise ValueError("Candidate identity was already attempted in this viewer.")
        if len(self.records) >= self.limits.max_candidates:
            self.stop_reason = "Registered viewer candidate limit reached."
            raise RuntimeError(self.stop_reason)
        spent = sum(row["seconds"] for row in self.records.values())
        remaining = self.limits.total_seconds - spent
        if remaining <= 0:
            self.stop_reason = "Viewer summed-work budget exhausted."
            raise RuntimeError(self.stop_reason)
        budget = NativeBudget(
            maximum_seconds=min(self.limits.seconds_per_candidate, remaining),
            maximum_rss_kib=self.limits.rss_kib,
        )
        row: dict[str, Any] = {
            "identifier": candidate.identifier,
            "source": candidate.source,
            "displayed": False,
            "evidence": None,
            "analysis_stage_seconds": None,
            "display_seconds": None,
        }
        self.records[candidate.identifier] = row
        try:
            budget.check("analysis")
            started = perf_counter()
            try:
                evidence = analyze(
                    candidate, lambda: budget.check("sampling"), intervals=self.limits.intervals
                )
                row["evidence"] = evidence
            finally:
                row["analysis_stage_seconds"] = perf_counter() - started
            budget.check("graphics")
            started = perf_counter()
            try:
                placement = transform if transform is not None else adsk.core.Matrix3D.create()
                occurrence = self.component.occurrences.addNewComponent(placement)
                row["occurrence"] = occurrence
                occurrence.component.name = f"{candidate.identifier} - ribbon analysis snapshot"
                rendered = draw_evidence(occurrence.component, evidence)
                row["groups"] = rendered.pop("groups")
                row.update(rendered)
            finally:
                row["display_seconds"] = perf_counter() - started
            budget.check("complete")
            row["displayed"] = True
        except (RuntimeError, ValueError, TypeError, AttributeError) as error:
            self.stop_reason = str(error)
            row["error"] = str(error)
        finally:
            row["seconds"] = perf_counter() - budget.started
            row["rss_samples"] = tuple(budget.samples)
        return {
            key: row[key]
            for key in (
                "identifier",
                "displayed",
                "analysis_stage_seconds",
                "display_seconds",
                "seconds",
            )
        } | {"error": row.get("error")}

    def evidence(self, identifier: str) -> Evidence:
        """
        Return the frozen shared snapshot,including evidence retained after a display failure.
        """
        row = self.records.get(identifier)
        if row is None or not isinstance(row["evidence"], Evidence):
            raise ValueError("Unknown or unmeasured candidate.")
        return row["evidence"]

    def show(
        self, identifier: str | None = None, *, sheet: bool = True, graphs: bool = True
    ) -> None:
        """
        Focus own completed displays without changing earlier geometry or recomputing.
        """
        self._active()
        if identifier is not None and (
            identifier not in self.records or not self.records[identifier]["displayed"]
        ):
            raise ValueError("Unknown completed display.")
        for number, row in self.records.items():
            if not row["displayed"]:
                continue
            row["occurrence"].isLightBulbOn = identifier is None or identifier == number
            row["groups"]["sheet"].isVisible = sheet
            row["groups"]["graph"].isVisible = graphs
        adsk.core.Application.get().activeViewport.refresh()


mark_loaded(__file__)
