"""
Append three lateral candidates and retain timing counters in memory for readout.

No report document or JSON report is written. Preserve the existing bodies and
export only the combined Fusion archive and its viewport image at finalization.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, load_sources
from experiments.experiment_ribbon_diagnosis.storage import archive

from .endpoint_lateral import lateral_cases
from .endpoint_native import NAME, _build, _hashes
from .endpoint_timing import timing_values
from .native_budget import NativeBudget, resident_kib

_state: dict[str, Any] | None = None


def _sources() -> dict[str, str]:
    """
    Freeze the exact procedure and fixture sources before any case evaluation.
    """
    hashes = _hashes()
    for path in (Path(__file__), Path(__file__).with_name("endpoint_lateral.py")):
        hashes[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _design() -> tuple[adsk.core.Document, adsk.fusion.Design]:
    """
    Activate the exact owned candidate document while requiring an idle command.
    """
    app = adsk.core.Application.get()
    matches = [d for d in app.documents if d.name == NAME]
    if app.userInterface.activeCommand != "SelectCommand" or len(matches) != 1:
        raise RuntimeError("Expected one idle owned candidate document.")
    document = matches[0]
    if not document.activate():
        raise RuntimeError("Owned candidate document activation failed.")
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Owned candidate design unavailable.")
    return document, design


def _bodies(design: adsk.fusion.Design) -> list[dict[str, object]]:
    """
    Record body identity and volume without relying on mutable component labels.
    """
    return [
        {"token": b.entityToken, "name": b.name, "volume_cm3": b.volume, "solid": b.isSolid}
        for c in design.allComponents
        for b in c.bRepBodies
    ]


def start() -> dict[str, object]:
    """
    Freeze inputs, sources, unknown predictions and agreed limits in memory.

    The unchanged generator may reroute between fixed endpoint poses. It gets one
    pass per case, no search/retries, and no post-result target or policy changes.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Lateral batch already registered; no retry.")
    document, design = _design()
    baseline = _bodies(design)
    if len(baseline) != 4 or not all(b["solid"] for b in baseline) or resident_kib() >= 2097152:
        raise RuntimeError("Expected four retained solids below the memory ceiling.")
    cases = lateral_cases()
    plan = {
        "algorithm": "endpoint-quintic-binormal-v1",
        "hypothesis": "The unchanged single-pass rule can connect lateral-heading endpoint poses.",
        "inputs": [asdict(c) for c in cases],
        "sources": _sources(),
        "native_predictions": ["unknown"] * 3,
        "limits": {
            "cases": 3,
            "solves": 3,
            "native_attempts": 3,
            "case_seconds": 120,
            "batch_seconds": 600,
            "rss_kib": 2097152,
            "search": 0,
            "retries": 0,
        },
        "rules": "Unchanged5x sphere,macaroni0.8,no-wide-axis bend,sampled lane radius3diameters,planar original lobe sections; no length equalization.",
        "scope": "Developmental unsplit trunks, not holdouts or complete-ribbon validation. Native internal banking, spacing and strain remain unmeasured.",
        "retention": "User requested end-of-process timing readout, no new report. Plan/outcomes retained only in host memory; combined F3D/PNG exported.",
    }
    _state = {
        "plan": plan,
        "document": document,
        "builder": load_sources()["builder"],
        "started": perf_counter(),
        "rows": [
            {
                "case_id": c.name,
                "evaluated": False,
                "native_attempted": False,
                "built": False,
                "fully_audited": False,
                "status": "not_attempted",
            }
            for c in cases
        ],
        "slot_offset": 4,
        "layout_origin_cm": [16, -64, 0],
        "baseline_bodies": baseline,
        "stop_reason": None,
        "finished": False,
    }
    return plan


def run_next() -> dict[str, Any]:
    """
    Attempt one case, keeping failed and unattempted outcomes in host memory.

    Known API/preflight failures are intentionally captured to preserve diagnostic
    geometry across MCP transactions. Any such outcome latches the scheduling stop.
    """
    state = _state
    if state is None or state["finished"] or state["stop_reason"]:
        raise RuntimeError("No schedulable lateral batch.")
    index = next((i for i, r in enumerate(state["rows"]) if r["status"] == "not_attempted"), None)
    if index is None:
        raise RuntimeError("Approved lateral slots exhausted.")
    row = state["rows"][index]
    started = perf_counter()
    budget = NativeBudget()
    try:
        if _sources() != state["plan"]["sources"] or perf_counter() - state["started"] >= 570:
            raise RuntimeError("Source or batch scheduling gate reached.")
        if not state["document"].activate():
            raise RuntimeError("Owned document activation failed.")
        row.update(_build(lateral_cases()[index], state, index, budget))
        budget.check("post_case")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        row.update(status="stopped", error=str(error))
        state["stop_reason"] = f"{row['case_id']}: {error}"
    finally:
        row["total_seconds"] = perf_counter() - started
        row["timing"] = timing_values(row)
        row["memory_samples"] = budget.samples
    return row


def finish() -> dict[str, object]:
    """
    Verify retained names/volumes and return counters; export F3D/PNG only.
    """
    state = _state
    if state is None or state["finished"]:
        raise RuntimeError("No unfinished lateral batch.")
    _document, design = _design()
    current = {b["name"]: b["volume_cm3"] for b in _bodies(design)}
    retained = all(current.get(b["name"]) == b["volume_cm3"] for b in state["baseline_bodies"])
    directory = PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/lateral" / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    archive(design, directory / "candidates.f3d")
    app = adsk.core.Application.get()
    camera = app.activeViewport.camera
    camera.viewOrientation = adsk.core.ViewOrientations.IsoTopRightViewOrientation
    camera.isFitView = True
    app.activeViewport.camera = camera
    app.activeViewport.refresh()
    app.activeViewport.saveAsImageFile(str(directory / "candidates.png"), 1800, 1100)
    state["finished"] = True
    return {
        "directory": str(directory),
        "rows": state["rows"],
        "stop_reason": state["stop_reason"],
        "wall_seconds": perf_counter() - state["started"],
        "final_rss_kib": resident_kib(),
        "retained_names_volumes_unchanged": retained,
        "bodies": _bodies(design),
    }
