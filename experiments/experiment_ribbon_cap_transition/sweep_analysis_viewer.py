"""
Display four cached director experiments as an opt-in Fusion analysis instrument.

No solve, native sweep, target change, automatic repair or acceptance-policy change.
The live ledger retains evidence and timings; no report file is generated.
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

from cable_bundler.routing.geometry import Vector3

from .director_route_sweeps import _trace
from .native_budget import NativeBudget
from .sweep_analysis import Witness, tube_mesh
from .sweep_analysis_graphics import BLUE, RED, WHITE, _color, draw_guides, draw_markers, draw_text

NUMBERS = (3, 7, 11, 29)
_state: dict[str, Any] | None = None


def prepare(ledger: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    """
    Freeze four cached inputs/sources and verify idle owned scratch before display.

    This is a one-use calibration:15s/case,60s summed case work,2GiB sampled RSS.
    No new solves/native attempts. Stop first harness/resource/source error; every
    case retains its disposition. Existing geometry is hidden reversibly only.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Viewer calibration already prepared; preserve its ledger.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if (
        design is None
        or app.userInterface.activeCommand != "SelectCommand"
        or app.activeDocument.name != "Untitled"
    ):
        raise RuntimeError("Expected idle owned Untitled experiment scratch.")
    roots = design.rootComponent.occurrences
    expected = (
        "Ribbon variations01-06 - fixed target director solver",
        "Breadth fixed-target diagnostics07-38",
    )
    if roots.count != 2 or tuple(roots.item(i).component.name for i in range(2)) != expected:
        raise RuntimeError("Owned scratch roots differ; no display writes permitted.")
    for name, digest in ledger["sources"].items():
        source = Path(__file__).parents[2] / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Cached solver source drift:{name}")
    source_rows = {r["number"]: r for r in ledger["rows"]}
    frozen = []
    for number in NUMBERS:
        row = source_rows[number]
        case = ledger["inputs"][number - 1]
        if asdict(case) != ledger["frozen_inputs"][number - 1]:
            raise RuntimeError("Cached endpoint input drift.")
        frozen.append((number, case, paths[row["trial"]][row["trial_index"]]))
    source_names = (
        "sweep_analysis.py",
        "sweep_analysis_viewer.py",
        "sweep_analysis_graphics.py",
        "director_route_sweeps.py",
        "edge_interpolation.py",
    )
    _state = {
        "plan": {
            "numbers": NUMBERS,
            "case_seconds": 15,
            "sum_seconds": 60,
            "rss_kib": 2 * 1024 * 1024,
            "sources": {
                name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in source_names
            },
            "inputs": [asdict(case) for _, case, _ in frozen],
            "policy": "existing center.8/lane3D/5width sphere;both-boundary fullreach proposed only",
            "native_prediction": "unknown",
            "solver_calls": 0,
            "native_attempts": 0,
        },
        "rows": [{"number": n, "attempted": False, "displayed": False} for n in NUMBERS],
        "frozen": frozen,
        "stop_reason": None,
        "document": app.activeDocument,
        "previous_visibility": [(roots.item(i), roots.item(i).isLightBulbOn) for i in range(2)],
        "groups": {},
        "occurrences": {},
    }
    budget = NativeBudget(maximum_seconds=15)
    budget.check("viewer_setup")
    occurrence = roots.addNewComponent(adsk.core.Matrix3D.create())
    occurrence.component.name = "Sweep analysis - 03 07 11 29 - graphics only"
    state = cast(dict[str, Any], _state)
    state["root"] = occurrence
    state["setup_seconds"] = perf_counter() - budget.started
    return {"prepared": True, "numbers": NUMBERS, "setup_seconds": state["setup_seconds"]}


def draw_next() -> dict[str, Any]:
    """
    Draw the next frozen case once, recording failed stages and disposable mesh cost.

    No contact test is included in v1. Sampled curvature, target and containment
    evidence cannot establish complete ribbon compliance or native construction.
    """
    if _state is None or _state["stop_reason"]:
        raise RuntimeError("Viewer unavailable or stop latched.")
    state = _state
    pending = next((r for r in state["rows"] if not r["attempted"]), None)
    if pending is None:
        raise RuntimeError("All four viewer cases already attempted.")
    row = cast(dict[str, Any], pending)
    budget = NativeBudget(maximum_seconds=15)
    row.update(
        attempted=True,
        path_seconds=0.0,
        mesh_seconds=0.0,
        analysis_seconds=0.0,
        display_seconds=0.0,
        guide_analysis_display_seconds=0.0,
        trace_count=0,
        vertices=0,
        triangles=0,
        witnesses=[],
    )
    try:
        if (
            adsk.core.Application.get().activeDocument != state["document"]
            or adsk.core.Application.get().userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Active owned scratch/idle state changed.")
        if sum(r.get("seconds", 0) for r in state["rows"]) >= 60:
            raise RuntimeError("Viewer summed-work cap reached.")
        for name, digest in state["plan"]["sources"].items():
            if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Viewer source drift.")
        number, case, path = next(item for item in state["frozen"] if item[0] == row["number"])
        budget.check("case_setup")
        index = NUMBERS.index(number)
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create((index % 2) * 22, (index // 2) * 20, 0)
        occurrence = state["root"].component.occurrences.addNewComponent(transform)
        component = occurrence.component
        component.name = f"{number:02} - {case.name} - diagnostic only"
        state["occurrences"][number] = occurrence
        groups = {}
        for name in ("tubes", "paths", "targets", "rulings", "findings", "legend"):
            group = component.customGraphicsGroups.add()
            group.name = name
            groups[name] = group
        state["groups"][number] = groups
        witnesses: list[Witness] = []
        lengths, errors, angles = [], [], []
        for i in range(case.lines):
            budget.check("trace")
            offset = (i - (case.lines - 1) / 2) * case.diameter_mm
            started = perf_counter()
            trace = _trace(path, i + 1, offset)
            row["path_seconds"] += perf_counter() - started
            mesh = tube_mesh(trace, case, offset, lambda: None)
            row["mesh_seconds"] += mesh.mesh_seconds
            row["analysis_seconds"] += mesh.analysis_seconds
            witnesses.extend(mesh.witnesses)
            lengths.append(mesh.length_mm)
            errors.append(mesh.midpoint_chord_error_mm)
            angles.append(mesh.maximum_tangent_step_degrees)
            started = perf_counter()
            coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
                [v / 10 for v in mesh.vertices]
            )
            entity = groups["tubes"].addMesh(coordinates, mesh.triangles, [], [])
            entity.name = f"Trace{i + 1:02} circular sweep approximation"
            _color(entity, BLUE if i % 2 == 0 else (85, 180, 205))
            if mesh.hot_triangles:
                hot = groups["findings"].addMesh(coordinates, mesh.hot_triangles, [], [])
                _color(hot, RED)
            row["display_seconds"] += perf_counter() - started
            row["trace_count"] += 1
            row["vertices"] += len(mesh.vertices) // 3
            row["triangles"] += len(mesh.triangles) // 3
            del mesh
        started = perf_counter()
        witnesses.extend(draw_guides(groups, path, case, budget))
        row["highlighted"] = draw_markers(groups["findings"], witnesses, case.diameter_mm)
        row["witnesses"] = [asdict(w) for w in witnesses]
        row["length_spread_percent_polyline"] = 100 * (max(lengths) - min(lengths)) / min(lengths)
        row["maximum_midpoint_chord_error_mm"] = max(errors)
        row["angular_sagitta_mm"] = case.diameter_mm / 2 * (1 - math.cos(math.pi / 12))
        row["maximum_tangent_step_degrees"] = max(angles)
        row["preview_resolution"] = (
            "unresolved"
            if max(errors) > 0.02 * case.diameter_mm or max(angles) > 5
            else "sampled checks within preview thresholds;not a surface certificate"
        )
        red = sum(w.severity == "red" for w in witnesses)
        amber = sum(w.severity == "amber" for w in witnesses)
        row.update(sampled_red_witnesses=red, proposed_amber_witnesses=amber)
        draw_text(
            groups["legend"],
            f"{number:02} {case.name} | diagnostic mesh",
            Vector3(-80, -65, 0),
            WHITE,
            3.5,
        )
        draw_text(
            groups["legend"],
            f"Red: existing rule/target findings ({red}) | Amber: proposed boundary rule ({amber})",
            Vector3(-80, -72, 0),
            WHITE,
            2,
        )
        draw_text(
            groups["legend"],
            "Green: fixed targets | White: center | Orange/Purple: A/B",
            Vector3(-80, -77, 0),
            WHITE,
            2,
        )
        draw_text(
            groups["legend"],
            "Rulings: u:A/B = longer-moving edge proxy; = neutral | No contact/physics certificate",
            Vector3(-80, -82, 0),
            WHITE,
            1.7,
        )
        row["guide_analysis_display_seconds"] = perf_counter() - started
        budget.check("case_complete")
        row["displayed"] = True
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
        row["error"] = str(error)
    finally:
        row["seconds"] = perf_counter() - budget.started
        row["maximum_sampled_rss_kib"] = max(
            (cast(int, s["rss_kib"]) for s in budget.samples), default=None
        )
        for pending in state["rows"]:
            if not pending["attempted"] and state["stop_reason"]:
                pending["not_attempted_reason"] = state["stop_reason"]
    return {k: v for k, v in row.items() if k != "witnesses"}


def show(number: int | None = None, *, tubes: bool = True, rulings: bool = False) -> None:
    """
    Focus one/all prepared examples and toggle tube/ruling layers without recomputing.
    """
    if _state is None or (number is not None and number not in _state["groups"]):
        raise ValueError("Unknown prepared viewer example.")
    for occurrence, _ in _state["previous_visibility"]:
        occurrence.isLightBulbOn = False
    _state["root"].isLightBulbOn = True
    for n, occurrence in _state["occurrences"].items():
        occurrence.isLightBulbOn = number is None or n == number
        _state["groups"][n]["tubes"].isVisible = tubes
        _state["groups"][n]["rulings"].isVisible = rulings
    app = adsk.core.Application.get()
    app.activeViewport.fit()
    app.activeViewport.refresh()


def restore_geometry() -> None:
    """
    Restore the earlier scene visibility, retaining the viewer and evidence ledger.
    """
    if _state is None:
        raise RuntimeError("No prepared viewer.")
    _state["root"].isLightBulbOn = False
    for occurrence, visible in _state["previous_visibility"]:
        occurrence.isLightBulbOn = visible
    adsk.core.Application.get().activeViewport.refresh()
