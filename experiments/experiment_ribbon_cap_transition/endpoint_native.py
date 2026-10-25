"""
Build the approved endpoint-first trunk prototypes in one owned Fusion document.

One case is scheduled per call. Preserve all failures and never retry or repair.
These unsplit trunks provide no complete split-ribbon compliance coverage.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, load_sources
from experiments.experiment_ribbon_diagnosis.storage import archive

from .endpoint_first import EndpointCase, construct, endpoint_cases, ribbon_group
from .native_budget import NativeBudget, resident_kib

NAME = "Endpoint-first ribbon candidates"
_state: dict[str, Any] | None = None


def _hashes() -> dict[str, str]:
    """
    Fingerprint the prototype, shared native dependencies and governing rules.
    """
    paths = [
        Path(__file__),
        Path(__file__).with_name("endpoint_first.py"),
        Path(__file__).with_name("native_budget.py"),
    ]
    paths.extend(
        PROJECT_ROOT / name
        for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt")
    )
    paths.extend(
        (PROJECT_ROOT / "experiments/experiment_production_split_ribbon/snapshot").glob("*.source")
    )
    return {
        str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


def _write(state: dict[str, Any]) -> None:
    """
    Checkpoint every planned disposition without discarding unsuccessful cases.
    """
    payload = {
        key: value for key, value in state.items() if key not in ("document", "started", "builder")
    }
    payload["wall_seconds"] = perf_counter() - state["started"]
    (Path(state["directory"]) / "report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def start(renewed_from: Path | None = None) -> str:
    """
    Freeze all poses, resource bounds and unknown native predictions before solving.

    An explicitly renewed setup-only failure may reuse its empty owned document.
    Preserve the historical report and empty component; reject any geometry there.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Endpoint batch already exists; no restart.")
    app = adsk.core.Application.get()
    owned = [d for d in app.documents if d.name == NAME]
    if app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Host is busy.")
    if renewed_from is None and owned:
        raise RuntimeError("Owned document exists without explicit renewal.")
    if renewed_from is not None:
        prior = json.loads((renewed_from / "report.json").read_text(encoding="utf-8"))
        if (
            len(owned) != 1
            or not prior.get("finished")
            or any(row.get("native_attempted") or row.get("built") for row in prior["rows"])
        ):
            raise RuntimeError("Renewal requires exactly one setup-only owned result.")
        if not owned[0].activate():
            raise RuntimeError("Owned document activation failed.")
        previous_design = adsk.fusion.Design.cast(app.activeProduct)
        if previous_design is None or any(
            c.bRepBodies.count or c.sketches.count for c in previous_design.allComponents
        ):
            raise RuntimeError("Owned renewal document contains geometry; no changes made.")
    if resident_kib() >= 2 * 1024 * 1024:
        raise RuntimeError("Host already exceeds approved RSS ceiling.")
    builder = load_sources()["builder"]
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/endpoint_first" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    cases = endpoint_cases()
    plan = {
        "algorithm": "endpoint-quintic-binormal-v1",
        "hypothesis": "One pose-derived quintic and its analytic bend binormal can produce unsplit ribbon trunk candidates without search or length equalization.",
        "inputs": [asdict(c) for c in cases],
        "rules": "5x width sphere centered between endpoints; macaroni0.8; hard no-wide-axis bend; undeformed planar original lobe sections; sampled radius>=3diameters; no approximate corkscrew ratio imposed.",
        "degrees_of_freedom": "Interior curve is generated, not supplied. One fixed chord-scaled endpoint speed/curvature policy. No search, retries, post-result adjustments or roll cap. Endpoint orientation does not specify winding class.",
        "limits": {
            "cases": 4,
            "solves": 4,
            "native_attempts": 4,
            "case_seconds": 120,
            "batch_seconds": 600,
            "rss_kib": 2097152,
            "search": 0,
            "retries": 0,
        },
        "review": "Control calibration first; remaining scheduling requires measured control time plus reserved finalization to fit remaining budget.",
        "prediction": "unknown native outcome on every case",
        "scope": "Four examined development trunk prototypes; no split endings or complete-ribbon audits. Continuous native spacing, banking, cap flow and strain unmeasured; not elastic equilibrium.",
        "authorization": "User approved proposed four-case limits with 'Just go with it'. Preserve unrelated documents; one new candidate document and local F3D archive.",
        "sources": _hashes(),
        "documents_before": [d.name for d in app.documents],
        "renewed_from": str(renewed_from) if renewed_from is not None else None,
        "renewal_direction": "User reported missing geometry and requested delivery; correct setup metadata and renew unchanged scope."
        if renewed_from is not None
        else None,
    }
    (directory / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    document = (
        owned[0]
        if renewed_from is not None
        else app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    )
    if renewed_from is None:
        document.name = NAME
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Owned direct design unavailable.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    _state = {
        "directory": str(directory),
        "document": document,
        "builder": builder,
        "started": perf_counter(),
        "sources": plan["sources"],
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
        "stop_reason": None,
        "finished": False,
    }
    _write(_state)
    return str(directory)


def _build(
    case: EndpointCase, state: dict[str, Any], index: int, budget: NativeBudget
) -> dict[str, object]:
    """
    Attempt one original-profile loft; keep failed inputs and never use a fallback.
    """
    row = state["rows"][index]
    started = perf_counter()
    row["evaluated"] = True
    frames, numerical = construct(case)
    row["numerical"] = numerical
    row["numerical_seconds"] = perf_counter() - started
    budget.check("component")
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    if design is None:
        raise RuntimeError("Owned design unavailable.")
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(0, index * 16, 0)
    occurrence = design.rootComponent.occurrences.addNewComponent(transform)
    component = occurrence.component
    component.name = f"{index + 1} - {case.name}"
    group = ribbon_group(case)
    loft_input = component.features.loftFeatures.createInput(
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    sketches = []
    profile_started = perf_counter()
    for number, frame in enumerate(frames):
        budget.check("section")
        sketch, _plane = state["builder"]._add_section(
            component,
            None,
            frame,
            group,
            adsk.core.Matrix3D.create(),
            guide_plane=RibbonGuidePlane(frame.origin, frame.tangent),
        )
        sketch.name = f"{case.name} - section {number + 1:02}"
        sketches.append(sketch)
        loft_input.loftSections.add(sketch.profiles.item(0))
    row["section_seconds"] = perf_counter() - profile_started
    loft_input.isSolid = True
    budget.check("loft")
    row["native_attempted"] = True
    native_started = perf_counter()
    try:
        loft = component.features.loftFeatures.add(loft_input)
    finally:
        row["loft_seconds"] = perf_counter() - native_started
    if loft is None or loft.bodies.count != 1:
        raise RuntimeError("Native loft did not return exactly one body.")
    body = loft.bodies.item(0)
    if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
        raise RuntimeError("Native output is not a positive-volume solid.")
    row["built"] = True
    body.name = case.name + " - unaudited trunk"
    for sketch in sketches:
        sketch.isLightBulbOn = False
    audit_started = perf_counter()
    cap_matches = []
    for endpoint, tangent in ((case.start, case.start_tangent), (case.end, case.end_tangent)):
        matches = 0
        for face in body.faces:
            plane = adsk.core.Plane.cast(face.geometry)
            if plane is not None:
                normal = plane.normal
                aligned = abs(normal.x * tangent.x + normal.y * tangent.y + normal.z * tangent.z)
                offset = abs(
                    (plane.origin.x - endpoint.x / 10) * tangent.x
                    + (plane.origin.y - endpoint.y / 10) * tangent.y
                    + (plane.origin.z - endpoint.z / 10) * tangent.z
                )
                if aligned > 1 - 1e-7 and offset < 1e-6:
                    matches += 1
        cap_matches.append(matches)
    row["native_audit"] = {
        "volume_cm3": body.volume,
        "endpoint_plane_matches": cap_matches,
        "complete_compliance": "unmeasured",
    }
    row["audit_seconds"] = perf_counter() - audit_started
    if cap_matches != [1, 1]:
        raise RuntimeError("Native endpoint plane audit failed.")
    return {"status": "built_partial_audit"}


def run_next() -> dict[str, Any]:
    """
    Consume one case slot and latch any hard rejection or host/resource failure.

    Known experimental/API errors are intentionally retained as dispositions so
    the MCP transaction does not erase failed diagnostic geometry.
    """
    state = _state
    if state is None or state["finished"] or state["stop_reason"]:
        raise RuntimeError("No active schedulable endpoint batch.")
    index = next(
        (i for i, row in enumerate(state["rows"]) if row["status"] == "not_attempted"), None
    )
    if index is None:
        raise RuntimeError("All approved slots consumed.")
    row = state["rows"][index]
    started = perf_counter()
    budget = NativeBudget()
    try:
        if _hashes() != state["sources"] or perf_counter() - state["started"] >= 600:
            raise RuntimeError("Source or batch scheduling gate reached.")
        if (
            index == 1
            and (600 - (perf_counter() - state["started"]))
            < 3 * state["rows"][0]["total_seconds"] + 30
        ):
            raise RuntimeError("Calibration does not support remaining cases within budget.")
        if not state["document"].activate():
            raise RuntimeError("Owned document activation failed.")
        row.update(_build(endpoint_cases()[index], state, index, budget))
        budget.check("post_case")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        row.update(status="stopped", error=str(error))
        state["stop_reason"] = f"{row['case_id']}: {error}"
    finally:
        row["total_seconds"] = perf_counter() - started
        row["memory_samples"] = budget.samples
        _write(state)
    return row


def finish() -> str:
    """
    Archive and photograph the one owned document, retaining skipped dispositions.
    """
    state = _state
    if state is None or state["finished"]:
        raise RuntimeError("No unfinished endpoint batch.")
    document = state["document"]
    if not document.activate():
        raise RuntimeError("Owned document activation failed.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Owned design unavailable.")
    directory = Path(state["directory"])
    archive(design, directory / "candidates.f3d")
    camera = app.activeViewport.camera
    camera.isFitView = True
    app.activeViewport.camera = camera
    app.activeViewport.refresh()
    app.activeViewport.saveAsImageFile(str(directory / "candidates.png"), 1800, 1100)
    state["finished"] = True
    state["final_rss_kib"] = resident_kib()
    state["documents_after"] = [d.name for d in app.documents]
    _write(state)
    return str(directory)
