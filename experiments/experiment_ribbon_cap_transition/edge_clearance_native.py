"""
Audit retained reference rulings without rebuilding or changing the Fusion scene.

Requires the completed paths70..74 array and retained original analytic controls.
All evidence stays in memory;no report files,solids,route solves or corrections.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from time import perf_counter
from typing import Any, cast

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from . import edge_interpolation_native, edge_native, edge_precision_native
from .edge_clearance import audit
from .native_budget import NativeBudget

_state: dict[str, Any] | None = None


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Audit129and257full-width rulings for each of four prior-compatible cases.

    Keep all eight fixed development configurations in the disposition table.
    Four prior-rejected cases skip clearance explicitly;no invalid material maps
    are treated as physical ribbons. Bound total audit10s/2GiB sampledRSS and
    stop on source/resource/API errors without replay or repair.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Clearance diagnostic already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    baseline = edge_interpolation_native._state
    precision = edge_precision_native._state
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    if baseline is None or baseline["stop_reason"] or baseline["findings"] or precision is None:
        raise RuntimeError("Completed native interpolation comparison required.")
    if design.rootComponent.occurrences.count != 11:
        raise RuntimeError("Expected retained eleven arrays.")
    sources = edge_precision_native._sources()
    old = precision["plan"]["sources"]
    if any(
        sources.get(p) != h for p, h in old.items() if p != edge_interpolation_native.DISPLAY_PATH
    ):
        raise RuntimeError("Unreviewed numerical source drift.")
    for relative in (
        "experiments/experiment_ribbon_cap_transition/edge_clearance.py",
        "experiments/experiment_ribbon_cap_transition/edge_clearance_native.py",
        "cable_bundler/routing/avoidance.py",
    ):
        sources[relative] = hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()
    spatial = iter(edge_precision_native._candidates)
    candidates = [
        candidate if i in (2, 3, 7) else next(spatial)
        for i, candidate in enumerate(edge_native._candidates)
    ]
    if len(candidates) != 8 or sum(c.companion_allowed for c in candidates) != 4:
        raise RuntimeError("Expected five spatial cases and three retained controls.")
    budget = NativeBudget(maximum_seconds=10)
    budget.check("start")
    state: dict[str, Any] = {
        "plan": {
            "hypothesis": "A locally regular strip can still approach remote material within cable thickness.",
            "algorithm": "full-ruling-pairs-v1",
            "sources": sources,
            "inputs": [asdict(c.case) for c in candidates],
            "reference_curves": [
                asdict(c.curve) if c.curve is not None else None for c in candidates
            ],
            "stations": [129, 257],
            "clearance_mm": 1.5,
            "local_exclusion_mm": 4.5,
            "search_horizon_mm": 3.0,
            "new_solves": 0,
            "native_attempts": 0,
            "limits": "8retained configurations;4eligible x2grids;0solids/retries/reports;10s/2GiBRSS",
            "scope": "Analytical full-width rulings sampled longitudinally;local flat-neighbor pairs excluded;no continuous/native/full cable certificate.",
        },
        "rows": [
            {
                "case": c.case.name,
                "number": 19
                if i == 2
                else 20
                if i == 3
                else 24
                if i == 7
                else 70 + sum(j not in (2, 3, 7) for j in range(i)),
                "reference_allowed": c.companion_allowed,
                "audits": [],
                "clearance": "unattempted",
            }
            for i, c in enumerate(candidates)
        ],
        "stop_reason": None,
    }
    _state = state
    sampled_at = budget.started

    def checkpoint() -> None:
        """
        Check time often and sample process memory at least once per quarter-second.
        """
        nonlocal sampled_at
        now = perf_counter()
        if now - budget.started >= 10:
            raise RuntimeError("Clearance diagnostic time cap reached.")
        if now - sampled_at >= 0.25:
            budget.check("ruling_pairs")
            sampled_at = now

    try:
        for candidate, row in zip(candidates, state["rows"]):
            checkpoint()
            for p, h in sources.items():
                if hashlib.sha256((PROJECT_ROOT / p).read_bytes()).hexdigest() != h:
                    raise RuntimeError("Clearance source drift.")
            if not candidate.companion_allowed:
                row["clearance"] = "skipped:prior reference rejection"
                row["prior_findings"] = list(candidate.metrics["findings"])
                continue
            for stations in (129, 257):
                row["audits"].append(audit(candidate, stations, checkpoint))
            row["clearance"] = (
                "contact detected"
                if any(a["contact_detected"] for a in row["audits"])
                else "no contact detected in sampled eligible ruling pairs"
            )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state["seconds"] = perf_counter() - budget.started
    state["maximum_sampled_rss_kib"] = max(cast(int, s["rss_kib"]) for s in budget.samples)
    return state
