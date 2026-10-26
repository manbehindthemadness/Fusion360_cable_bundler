"""
Read-only dense and native-curve audit of the provisional quarter-minus candidate.

Requirements:completed edge_precision_native in the current owned Fusion scratch.
No new solve,geometry,report file or acceptance-policy change. This is a focused
curve check,not complete thick-ribbon native compliance.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, cast

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import difference, magnitude

from . import edge_precision_native
from .edge_first import frame
from .edge_native_checks import audit_curves, curve_findings
from .native_budget import NativeBudget

_state: dict[str, Any] | None = None


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Audit1025reference stations and513native parameters plus both knot-side limits.

    Only candidate68 previously passed the257station gate. Check its three native
    cubic paths' endpoints,radii,center macaroni and sampled occupied sphere.
    Time cap10s/2GiB sampledRSS;no retry on an API/resource/source failure.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Focused edge audit already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    baseline = edge_precision_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete precision baseline required.")
    if edge_precision_native._sources() != baseline["plan"]["sources"]:
        raise RuntimeError("Source drift before audit.")
    candidate = edge_precision_native._candidates[3]
    curve = candidate.curve
    if not candidate.companion_allowed or curve is None:
        raise RuntimeError("Candidate68 must have passed the provisional gate.")
    root = design.rootComponent
    if (
        root.occurrences.count != 10
        or root.occurrences.item(9).component.name != edge_precision_native.NAME
    ):
        raise RuntimeError("Expected retained precision array.")
    component = root.occurrences.item(9).component.occurrences.item(3).component
    budget = NativeBudget(maximum_seconds=10)
    budget.check("start")
    state: dict[str, Any] = {
        "number": 68,
        "math_stations": 1025,
        "native_uniform_parameters": 513,
        "native_knot_side_offsets": 1e-7,
        "new_solves": 0,
        "new_geometry": 0,
        "stop_reason": None,
        "plan": {
            "inputs": asdict(candidate.case),
            "baseline_sources": dict(baseline["plan"]["sources"]),
            "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    _state = state
    case = candidate.case
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    reach = math.hypot(half_width, case.diameter_mm / 2)
    center = case.start.translated(difference(case.end, case.start), 0.5)
    try:
        min_jac, min_radius, max_ratio, max_extent = 1.0, math.inf, 0.0, 0.0
        for index in range(1025):
            if index % 128 == 0:
                budget.check("math_dense")
            observed = frame(curve, index / 1024)
            state["math_samples_completed"] = index + 1
            for offset in (0.0, -half_width, -2 * half_width):
                jac = 1 + offset * observed.slope_rate / observed.speed
                min_jac = min(min_jac, jac)
                if jac <= 0:
                    raise RuntimeError("Dense reference reveals material-coordinate reversal.")
                curvature = observed.curvature / jac
                min_radius = min(min_radius, 1 / curvature)
                if offset == -half_width:
                    max_ratio = max(max_ratio, curvature * reach)
                point, _ = observed.lane(offset)
                max_extent = max(
                    max_extent, magnitude(difference(point, center)) + case.diameter_mm / 2
                )
        state["reference"] = {
            "minimum_jacobian": min_jac,
            "minimum_lane_radius_mm": min_radius,
            "center_ratio": max_ratio,
            "occupied_sphere_reach_mm": max_extent,
        }
        rows: list[dict[str, Any]] = []
        state["native_curves"] = rows

        def checkpoint() -> None:
            """
            Bound the shared native evaluator without changing the scene.
            """
            budget.check("native_samples")

        audit_curves(component, case, 64, checkpoint, rows)
        if len(rows) != 3:
            raise RuntimeError("Expected three native material paths.")
        state["native_curves"] = rows
        state["findings"] = []
        if min_radius < 4.5 or max_ratio > 0.8 or max_extent > 71.25:
            state["findings"].append("dense reference rule failure")
        state["findings"].extend(curve_findings(rows))
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state["seconds"] = perf_counter() - budget.started
    state["maximum_sampled_rss_kib"] = max(cast(int, s["rss_kib"]) for s in budget.samples)
    return state
