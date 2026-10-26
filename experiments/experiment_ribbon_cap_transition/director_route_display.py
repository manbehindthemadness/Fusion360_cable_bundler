"""
Draw frozen cold-route outcomes and audit native curves without rerouting.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, cast

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from . import coupled_native, director_route_trials, event_display
from .director_native import _draw_lane
from .edge_native_checks import audit_curves
from .endpoint_first import EndpointCase
from .native_budget import NativeBudget

NAME = "Cold fixed-target director routes88-105"
_state: dict[str, Any] | None = None


# noinspection PyProtectedMember,DuplicatedCode
def run(entries: tuple[tuple[str, int, EndpointCase], ...]) -> dict[str, Any]:
    """
    Display all18registered outcomes once;three paths only after numerical gates.

    Entries identify preserved solver rows and their original fixed input poses.
    Failed outcomes show onlyA and target guides. Audit all authored native curves
    at1535parameters each against fixed targets,not reference-generated endpoints.
    This constructs no solids and provides no complete-ribbon compliance coverage.
    Limits30s drawing/10s nativeaudit/60s overall/2GiB sampledRSS;no retries/reports.
    Native construction prediction unknown. Preserve partial rows on any failure.
    """
    global _state
    if _state is not None or len(entries) != 18:
        raise RuntimeError("Expected one frozen eighteen-outcome display.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle current scratch.")
    root = design.rootComponent
    if root.occurrences.count != 12:
        raise RuntimeError("Expected twelve retained arrays before display.")
    fingerprints = director_route_trials.sources()
    for name in ("director_route_display.py", "director_native.py", "edge_native_checks.py"):
        file = Path(__file__).with_name(name)
        fingerprints[str(file.relative_to(PROJECT_ROOT))] = hashlib.sha256(
            file.read_bytes()
        ).hexdigest()
    paths = []
    rows = []
    for label, index, case in entries:
        trial = director_route_trials._trials[label]
        source_row = trial["rows"][index]
        if trial["stop_reason"] or not source_row["evaluated"]:
            raise RuntimeError("Incomplete source trial:" + label)
        if trial["plan"]["inputs"][index] != asdict(case):
            raise RuntimeError("Fixed target mismatch before native display.")
        paths.append(director_route_trials._paths[label][index])
        rows.append(
            {
                "number": 88 + len(rows),
                "trial": label,
                "index": index,
                "case": case.name,
                "numerical": source_row["overall"],
                "companions_allowed": source_row["overall"].startswith(
                    "sampled numerical gates pass"
                ),
                "drawn": False,
                "native_prediction": "unknown",
                "native_curves": [],
                "native_findings": [],
                "native_audit": "unattempted",
            }
        )
    state: dict[str, Any] = {
        "plan": {"sources": fingerprints, "inputs": [asdict(c) for _, _, c in entries]},
        "rows": rows,
        "stop_reason": None,
    }
    _state = state
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    stage_started = perf_counter()
    stage_cap = 30.0
    sampled_at = stage_started

    def checkpoint() -> None:
        """
        Bound stage time and sample process memory every quarter-second.
        """
        nonlocal sampled_at
        now = perf_counter()
        if now - stage_started >= stage_cap:
            raise RuntimeError("Route display stage cap reached.")
        if now - sampled_at >= 0.25:
            budget.check("display")
            sampled_at = now

    def check_sources() -> None:
        """
        Reject dependency changes before scheduling each candidate operation.
        """
        for relative_path, digest in fingerprints.items():
            if hashlib.sha256((PROJECT_ROOT / relative_path).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Route display source drift.")

    try:
        pitch = 94.17185167125959
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(0, -24 * pitch, 0)
        array = root.occurrences.addNewComponent(transform).component
        array.name = NAME
        components = []
        for i, ((_, _, case), path, row) in enumerate(zip(entries, paths, rows)):
            checkpoint()
            check_sources()
            started = perf_counter()
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(i % 4 * pitch, -(i // 4) * pitch, 0)
            component = array.occurrences.addNewComponent(placement).component
            components.append(component)
            component.name = f"{row['number']} - {case.name} - {row['numerical']}"
            coupled_native._guides(component, case)
            _draw_lane(component, path, "A boundary", path.field.half_width_mm)
            if row["companions_allowed"]:
                _draw_lane(component, path, "Derived center", 0)
                _draw_lane(component, path, "Derived B boundary", -path.field.half_width_mm)
            label_sketch = component.sketches.add(component.xYConstructionPlane)
            label_sketch.name = str(row["number"]) + " - fixed target route status"
            event_display._text(label_sketch, str(row["number"]), -3, -5, 0.9)
            caption = "GATES PASS" if row["companions_allowed"] else "FAILED - A ONLY"
            event_display._text(label_sketch, caption, -3, -7, 0.3)
            label_sketch.isLightBulbOn = True
            row.update(drawn=True, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - stage_started
        checkpoint()
        stage_started = perf_counter()
        stage_cap = 10.0
        for component, (_, _, case), row in zip(components, entries, rows):
            checkpoint()
            check_sources()
            started = perf_counter()
            audit_curves(component, case, 512, checkpoint, row["native_curves"])
            expected = 3 if row["companions_allowed"] else 1
            if len(row["native_curves"]) != expected:
                raise RuntimeError("Unexpected authored native path count.")
            findings = row["native_findings"]
            for curve in row["native_curves"]:
                if curve["minimum_radius_mm"] < 3 * case.diameter_mm:
                    findings.append("native radius policy rejected")
                if curve["occupied_sphere_reach_mm"] > 2.5 * case.lines * case.diameter_mm:
                    findings.append("native sphere policy rejected")
                if curve["center_ratio"] is not None and curve["center_ratio"] > 0.8:
                    findings.append("native center policy rejected")
                if curve["endpoint_error_mm"] > 1e-8:
                    findings.append("native fixed target closure rejected")
            row["native_findings"] = sorted(set(findings))
            row["native_audit"] = (
                "named curve checks failed" if findings else "named curve checks pass"
            )
            row["native_audit_seconds"] = perf_counter() - started
        state["native_audit_seconds"] = perf_counter() - stage_started
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state["overall_seconds"] = perf_counter() - budget.started
    state["maximum_sampled_rss_kib"] = max(cast(int, s["rss_kib"]) for s in budget.samples)
    return state
