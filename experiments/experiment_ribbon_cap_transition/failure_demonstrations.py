"""
Run a bounded, inspectable failure-region demonstration in the owned Fusion scratch.

Six forward diagnostic variants plus retained11 are not new routing coverage.
The previous stopped viewer ledger is neither reset nor extended by this run.
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

from cable_bundler.routing.geometry import Vector3

from . import failure_region_graphics
from .failure_fixtures import author, specifications
from .failure_regions import measure, summary
from .native_budget import NativeBudget
from .sweep_analysis_graphics import draw_text

_state: dict[str, Any] | None = None


def prepare(breadth: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    """
    Freeze six authored variants and retained11 before any failure measurements.

    Bounds10s/display,75s total scheduling,2GiB sampledRSS,no searches or native
    builds/retries. Known invalid findings are expected outcomes,not harness errors.
    Stop on unexpected classification,source/input drift,host error or resource gate.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Failure demonstration already prepared; retain its ledger.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if (
        design is None
        or app.activeDocument.name != "Untitled"
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Expected idle owned Untitled experiment scratch.")
    roots = design.rootComponent.occurrences
    expected = (
        "Ribbon variations01-06 - fixed target director solver",
        "Breadth fixed-target diagnostics07-38",
        "Sweep analysis - 03 07 11 29 - graphics only",
    )
    if roots.count != 3 or tuple(roots.item(i).component.name for i in range(3)) != expected:
        raise RuntimeError("Unexpected scratch roots; no display writes.")
    root = Path(__file__).parents[2]
    for name, digest in breadth["sources"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Cached solver source drift.")
    budget = NativeBudget(maximum_seconds=10)
    entries = []
    for spec in specifications():
        budget.check("fixture_authoring")
        path, case = author(spec)
        entries.append(
            {
                "number": spec.number,
                "parent": spec.parent,
                "path": path,
                "case": case,
                "input": asdict(case),
                "field": asdict(spec.field),
                "expected_red": spec.expected_red,
                "expected_amber": spec.expected_amber,
            }
        )
    retained = next(r for r in breadth["rows"] if r["number"] == 11)
    case = breadth["inputs"][10]
    if asdict(case) != breadth["frozen_inputs"][10]:
        raise RuntimeError("Retained11 target drift.")
    entries.append(
        {
            "number": "R11",
            "parent": "retained rejected endpoint case11",
            "path": paths[retained["trial"]][retained["trial_index"]],
            "case": case,
            "input": asdict(case),
            "expected_red": ("material J",),
            "expected_amber": None,
        }
    )
    names = (
        "failure_regions.py",
        "failure_fixtures.py",
        "failure_region_graphics.py",
        "failure_demonstrations.py",
        "director_fields.py",
        "director_transport.py",
        "director_rotation_transport.py",
        "director_route_sweeps.py",
        "edge_interpolation.py",
        "sweep_analysis_graphics.py",
        "native_budget.py",
    )
    sources = {
        str(Path(__file__).with_name(n).relative_to(root)): hashlib.sha256(
            Path(__file__).with_name(n).read_bytes()
        ).hexdigest()
        for n in names
    }
    sources.update(breadth["sources"])
    state: dict[str, Any] = {
        "plan": {
            "sources": sources,
            "numbers": [e["number"] for e in entries],
            "seconds_per_display": 10,
            "total_seconds": 75,
            "rss_kib": 2 * 1024 * 1024,
            "intervals": 512,
            "native_attempts": 0,
            "solver_calls": 0,
            "coverage": "2forward diagnostic families/6variants plus1retained case;no holdouts",
        },
        "entries": entries,
        "rows": [{"number": e["number"], "attempted": False, "displayed": False} for e in entries],
        "stop_reason": None,
        "document": app.activeDocument,
        "previous_visibility": [(roots.item(i), roots.item(i).isLightBulbOn) for i in range(3)],
        "occurrences": {},
        "groups": {},
    }
    budget.check("root")
    occurrence = roots.addNewComponent(adsk.core.Matrix3D.create())
    occurrence.component.name = "Failure regions - bend fold and retained11 - diagnostic sheets"
    state["root"] = occurrence
    state["setup_seconds"] = perf_counter() - budget.started
    _state = state
    return {"numbers": state["plan"]["numbers"], "setup_seconds": state["setup_seconds"]}


def _active() -> dict[str, Any]:
    """
    Require the original live document and an idle command for all viewer writes.
    """
    if _state is None:
        raise RuntimeError("Failure demonstration not prepared.")
    app = adsk.core.Application.get()
    if (
        app.activeDocument != _state["document"]
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Owned document or idle command changed.")
    return _state


def draw_next() -> dict[str, Any]:
    """
    Measure/render one registered diagnostic once;retain every failure and skip.

    The sheet can represent a folded map without pretending a valid tube exists.
    Expected invalid regions remain a completed diagnostic,not an accepted ribbon.
    """
    state = _active()
    if state["stop_reason"]:
        raise RuntimeError("Demonstration stop latched:" + state["stop_reason"])
    pending = next((r for r in state["rows"] if not r["attempted"]), None)
    if pending is None:
        raise RuntimeError("All registered demonstrations attempted.")
    row = cast(dict[str, Any], pending)
    row.update(attempted=True, analysis_seconds=None, display_seconds=None)
    budget = NativeBudget(maximum_seconds=10)
    try:
        if state["setup_seconds"] + sum(r.get("seconds", 0) for r in state["rows"]) >= 75:
            raise RuntimeError("75s summed-work scheduling cap.")
        root = Path(__file__).parents[2]
        for name, digest in state["plan"]["sources"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Demonstration source drift.")
        entry = next(e for e in state["entries"] if e["number"] == row["number"])
        if asdict(entry["case"]) != entry["input"]:
            raise RuntimeError("Frozen target drift.")
        budget.check("analysis")
        started = perf_counter()
        try:
            series, findings = measure(entry["path"], lambda: None)
            row["series"], row["regions"] = series, findings
            row["summary"] = summary(series, findings)
        finally:
            row["analysis_seconds"] = perf_counter() - started
        red = set(row["summary"]["red_kinds"])
        expected = set(entry["expected_red"])
        if (entry["number"] != "R11" and red != expected) or (
            entry["number"] == "R11" and not expected <= red
        ):
            raise RuntimeError(f"Unexpected reference classification:{red},expected{expected}")
        if entry["expected_amber"] and entry["expected_amber"] not in row["summary"]["amber_kinds"]:
            raise RuntimeError("Expected boundary warning missing.")
        row["expected_classification_observed"] = True
        budget.check("display")
        started = perf_counter()
        try:
            index = state["plan"]["numbers"].index(row["number"])
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(
                (index % 3) * 7 if index < 6 else 2, (index // 3) * 7, 0
            )
            occurrence = state["root"].component.occurrences.addNewComponent(transform)
            occurrence.component.name = (
                f"{row['number']} - {entry['parent']} - reference diagnostic"
            )
            state["occurrences"][row["number"]] = occurrence
            primary = "center macaroni" if row["number"].startswith("B") else "material J"
            rendered = failure_region_graphics.draw(
                occurrence.component,
                row["number"],
                entry["path"],
                entry["case"],
                series,
                findings,
                primary,
            )
            state["groups"][row["number"]] = rendered.pop("groups")
            row.update(rendered)
        finally:
            row["display_seconds"] = perf_counter() - started
        draw_text(
            state["groups"][row["number"]]["legend"],
            f"Analysis {row['analysis_seconds']:.3f}s | Display {row['display_seconds']:.3f}s | No solve/native build",
            Vector3(0, -40, 0),
            (40, 40, 40),
            1.2,
        )
        budget.check("complete")
        row["displayed"] = True
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
        row["error"] = str(error)
    finally:
        elapsed = perf_counter() - budget.started
        observed_rss = [cast(int, sample["rss_kib"]) for sample in budget.samples]
        row.update(seconds=elapsed, maximum_sampled_rss_kib=max(observed_rss, default=None))
        if state["stop_reason"]:
            for waiting in state["rows"]:
                if waiting["attempted"]:
                    continue
                waiting["not_attempted_reason"] = state["stop_reason"]
    return {k: v for k, v in row.items() if k not in ("series", "regions", "summary")} | {
        "red_kinds": row.get("summary", {}).get("red_kinds")
    }


def inspect(number: str, *, kind: str | None = None, trace: int | None = None) -> dict[str, object]:
    """
    Return selected full region records without recomputing or changing the scene.
    """
    if _state is None:
        raise RuntimeError("No demonstration evidence.")
    measured = next((r for r in _state["rows"] if r["number"] == number), None)
    if measured is None or "series" not in measured:
        raise ValueError("Unknown/unmeasured demonstration.")
    row = cast(dict[str, Any], measured)
    selected = tuple(
        s
        for s in row["series"]
        if (kind is None or s.kind == kind) and (trace is None or s.trace == trace)
    )
    findings = tuple(
        r
        for r in row["regions"]
        if (kind is None or r.kind == kind) and (trace is None or r.trace == trace)
    )
    return summary(selected, findings)


def show(number: str | None = None, *, sheet: bool = True, graphs: bool = True) -> None:
    """
    Focus one/all measured demonstrations and toggle layers without another audit.
    """
    state = _active()
    if number is not None and number not in state["groups"]:
        raise ValueError("Unknown displayed demonstration.")
    for occurrence, _ in state["previous_visibility"]:
        occurrence.isLightBulbOn = False
    state["root"].isLightBulbOn = True
    for n, occurrence in state["occurrences"].items():
        occurrence.isLightBulbOn = number is None or number == n
        state["groups"][n]["sheet"].isVisible = sheet
        state["groups"][n]["graph"].isVisible = graphs
    app = adsk.core.Application.get()
    app.activeViewport.fit()
    app.activeViewport.refresh()


def restore() -> None:
    """
    Restore original visibility without deleting demonstrations or stopped history.
    """
    state = _active()
    state["root"].isLightBulbOn = False
    for occurrence, visible in state["previous_visibility"]:
        occurrence.isLightBulbOn = visible
    adsk.core.Application.get().activeViewport.refresh()
