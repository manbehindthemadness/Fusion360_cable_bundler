"""
Screen every positive director fixture's full-width rulings without geometry edits.

The reserved validation fields are now consumed;this postflight does not turn
them into fresh holdouts or revise their frozen transport/policy outcomes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from . import director_native
from .edge_clearance import Ruling, screen
from .native_budget import NativeBudget

_state: dict[str, Any] | None = None


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Audit11positive fields at129/257rulings;explicitly skip2rejection controls.

    Keep the original1.0diameter thickness screen,2.0diameter search horizon and
    3.0diameter local-flat-neighbor exclusion. Longitudinal sampling/exclusions
    prevent continuous clearance certification. No route solves,native attempts,
    corrections,geometry,reports or retries;10s/2GiB sampledRSS bound.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Director clearance already started.")
    baseline = director_native._state
    if baseline is None or baseline["stop_reason"] or len(director_native._paths) != 13:
        raise RuntimeError("Complete retained director matrix required.")
    sources = director_native._sources()
    if sources != baseline["plan"]["sources"]:
        raise RuntimeError("Director source drift before clearance.")
    for path in (
        Path(__file__),
        Path(__file__).with_name("edge_clearance.py"),
        PROJECT_ROOT / "cable_bundler/routing/avoidance.py",
    ):
        sources[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    budget = NativeBudget(maximum_seconds=10)
    budget.check("start")
    state: dict[str, Any] = {
        "plan": {
            "sources": sources,
            "baseline_sources": baseline["plan"]["sources"],
            "hypothesis": "Local director/map regularity does not imply global clearance.",
            "procedure": "All11positive fields,including sphere-rejected80,129/257full rulings;2rejection controls explicitly skipped.",
            "limits": "10s/2GiB RSS;0solves/nativeattempts/geometry/reports/retries",
            "inputs": baseline["plan"]["fields"],
            "stations": [129, 257],
            "thickness_policy": "1diameter screen,2diameter horizon,3diameter flat-neighbor exclusion",
        },
        "rows": [
            {
                "number": row["number"],
                "case": row["case"],
                "phase": row["phase"],
                "audits": [],
                "outcome": "unattempted",
            }
            for row in baseline["rows"]
        ],
        "stop_reason": None,
    }
    _state = state
    last_sample = budget.started

    def checkpoint() -> None:
        """
        Check time frequently and sample process RSS at least every quarter-second.
        """
        nonlocal last_sample
        now = perf_counter()
        if now - budget.started >= 10:
            raise RuntimeError("Director clearance time cap reached.")
        if now - last_sample >= 0.25:
            budget.check("director_clearance")
            last_sample = now

    try:
        for path, row in zip(director_native._paths, state["rows"]):
            checkpoint()
            for name, digest in sources.items():
                if hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Source drift during director clearance.")
            if row["phase"] == "rejection":
                row["outcome"] = "skipped:rejection control"
                continue
            half = path.field.half_width_mm
            for stations in (129, 257):
                started = perf_counter()
                samples = []
                for i in range(stations):
                    if i % 32 == 0:
                        checkpoint()
                    u = i / (stations - 1)
                    _, eta, _ = path.field.sample(u)
                    s = u * path.field.length_mm
                    samples.append(
                        Ruling(
                            u,
                            path.lane(u, half)[0],
                            path.lane(u, -half)[0],
                            Vector3(s + half * eta, half, 0),
                            Vector3(s - half * eta, -half, 0),
                        )
                    )
                result = screen(tuple(samples), path.field.diameter_mm, checkpoint)
                result["total_seconds"] = perf_counter() - started
                row["audits"].append(result)
            row["outcome"] = (
                "sampled contact detected"
                if any(a["contact_detected"] for a in row["audits"])
                else "no contact detected in sampled eligible pairs"
            )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state["seconds"] = perf_counter() - budget.started
    state["maximum_sampled_rss_kib"] = max(cast(int, s["rss_kib"]) for s in budget.samples)
    return state
