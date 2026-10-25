"""
Compare seven displacement-guided candidates against retained three-motion outcomes.

One new solve per fixed case, no search/retries/solids; 10 seconds numerical,
30 seconds drawing, 60 seconds overall, 2 GiB sampled RSS. Reuse the original
guide authoring and numerical audits unchanged, retaining known failures.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import coupled_native
from .chord_coupled import construct
from .coupled_motion import CoupledMotion
from .coupled_route import CoupledRejection, audit, cases
from .lateral_native import _bodies, _design
from .native_budget import NativeBudget, resident_kib

NAME = "Chord-guided coupled motion - three guide diagnostic"
_state: dict[str, Any] | None = None


def _sources() -> dict[str, str]:
    """
    Include unchanged baseline, guide, audit, new construction and active rule files.
    """
    result = coupled_native._fingerprints()
    for name in ("chord_coupled.py", "chord_native.py"):
        path = Path(__file__).with_name(name)
        result[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run() -> dict[str, Any]:
    """
    Evaluate one unchanged policy across the frozen seven-case development matrix.

    Require the original in-memory baseline and exact frozen inputs/sources before
    starting. Baseline timings are historical and excluded from this new run.
    Constructed rule failures may be drawn as diagnostics, never accepted ribbons.
    Retain only F3D/PNG artifacts and read result counters from memory into chat.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Chord-guided batch already started; no retry.")
    baseline = coupled_native._state
    inputs = cases()
    if baseline is None or baseline.get("stop_reason") is not None:
        raise RuntimeError("Completed original seven-case baseline is unavailable.")
    if baseline["plan"]["inputs"] != [asdict(case) for case in inputs]:
        raise RuntimeError("Fixed inputs differ from the completed baseline.")
    if coupled_native._fingerprints() != baseline["plan"]["sources"]:
        raise RuntimeError("Original source or rule fingerprints differ from baseline.")
    _document, design = _design()
    if any(component.name == NAME for component in design.allComponents):
        raise RuntimeError("Chord-guided component already exists; no duplicate.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    originals, sources = _bodies(design), _sources()
    _state = {
        "plan": {
            "algorithm": "chord-frame-two-ABA-legs-seven-travel-projection-v1",
            "hypothesis": "A chord-selected intermediate frame and seven travel freedoms improve forward pose closure over the three-motion orientation-only basis.",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "baseline": deepcopy(baseline["rows"]),
            "baseline_policy": "Completed original run; cached outcomes, no old solves in current timers.",
            "degrees_of_freedom": "Chord intermediate heading; transported width bisector; fixed oblique primitive basis; seven lengths in one minimum-deviation projection. Centerline may reroute.",
            "constraints": "Unchanged modeled width-axis rule, 0.8 macaroni, 3-diameter lane radius, 5-width sphere; 1% length spread is warning only. No branches or solids in scope.",
            "limits": {
                "cases": 7,
                "new_solves": 7,
                "search": 0,
                "retries": 0,
                "native_solid_attempts": 0,
                "math_seconds": 10,
                "display_seconds": 30,
                "overall_seconds": 60,
                "rss_kib": 2097152,
            },
            "stop": "Any control regression, source/fixture change, resource or API/harness failure; no local repair.",
            "native_prediction": "Unknown; only approximate diagnostic curves attempted.",
            "coverage": "Same seven examined development cases; no invalid controls or untouched holdouts.",
        },
        "rows": [
            {
                "case": case.name,
                "evaluated": False,
                "overall": "unattempted",
                "display_attempted": False,
                "displayed_curves": False,
            }
            for case in inputs
        ],
        "stop_reason": None,
    }
    cpu_started = process_time()
    routes: list[tuple[CoupledMotion, ...] | None] = []
    try:
        started_math = perf_counter()
        for case, row in zip(inputs, _state["rows"]):
            budget.check("solve_" + case.name)
            if perf_counter() - started_math >= 10:
                raise RuntimeError("Numerical scheduling limit reached.")
            if _sources() != sources:
                raise RuntimeError("Frozen source or rules changed before solve.")
            started = perf_counter()
            try:
                motions = construct(case)
            except CoupledRejection as error:
                motions = None
                row.update({"overall": "failed", "construction_rejection": str(error)})
            row["solve_seconds"] = perf_counter() - started
            started = perf_counter()
            if motions is not None:
                row.update(audit(case, motions))
            row["audit_seconds"] = perf_counter() - started
            row["evaluated"] = True
            routes.append(motions)
            if case.name in ("control", "reference_broad_return") and row["overall"] == "failed":
                raise RuntimeError("Representative control regression: " + case.name)
        _state["numerical_seconds"] = perf_counter() - started_math
        budget.check("create_array")
        started_display = perf_counter()
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(144, 0, 0)
        parent = design.rootComponent.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        for index, (case, motions, row) in enumerate(zip(inputs, routes, _state["rows"])):
            budget.check("display_" + case.name)
            if perf_counter() - started_display >= 30:
                raise RuntimeError("Drawing scheduling limit reached.")
            if _sources() != sources:
                raise RuntimeError("Frozen source or rules changed before drawing.")
            row["display_attempted"] = True
            started = perf_counter()
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(
                (index % 3) * 16, -(index // 3) * 16, 0
            )
            component = parent.occurrences.addNewComponent(transform).component
            component.name = f"{index + 1} {case.name} - {row['overall']}"
            coupled_native._guides(component, case)
            if motions is not None:
                coupled_native._curves(component, case, motions)
                row["displayed_curves"] = True
            row["display_seconds"] = perf_counter() - started
        _state["display_seconds"] = perf_counter() - started_display
        budget.check("archive_camera")
        app = adsk.core.Application.get()
        camera = app.activeViewport.camera
        camera.isPerspective = False
        camera.target = adsk.core.Point3D.create(159, -13, 1.5)
        camera.eye = adsk.core.Point3D.create(173, -35, 29)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        if not camera.setExtents(59, 47):
            raise RuntimeError("Chord diagnostic camera extent failed.")
        app.activeViewport.camera = camera
        app.activeViewport.refresh()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/chord_coupled"
            / uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        started = perf_counter()
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "trajectories.png"), 1800, 1100):
            raise RuntimeError("Chord diagnostic image export failed.")
        _state["archive_image_seconds"] = perf_counter() - started
        _state["directory"] = str(directory)
        current = _bodies(design)
        _state["original_solids_unchanged"] = len(current) == len(originals) and all(
            old in current for old in originals
        )
        if not _state["original_solids_unchanged"]:
            raise RuntimeError("Original solid identity or geometry changed.")
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        _state["stop_reason"] = str(error)
    finally:
        _state["overall_seconds"] = perf_counter() - budget.started
        _state["cpu_seconds"] = process_time() - cpu_started
        _state["maximum_sampled_rss_kib"] = max(int(sample["rss_kib"]) for sample in budget.samples)
        _state["final_rss_kib"] = resident_kib()
    return _state
