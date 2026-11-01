"""
Construct frozen material-route results in the owned Fusion design, without rerouting.

Fusion supplies adsk. The pinned historical221audit measures native surfaces,
ordered guides, seams and cap frames with its unchanged sampling/tolerances.
"""

from __future__ import annotations

import hashlib
import json
import runpy
import time
import traceback
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.end_profiles import retain_end_profiles
from devtools.ribbon_analysis.provenance import verify_loaded
from experiments.experiment_optional_appearance.host import capture
from experiments.experiment_ribbon_fold_route.material_native import define_material_body
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches

from .runner import restore


def build(run_path: str, case_id: str) -> None:
    """
    Attempt one native body, retain partial failures and never retry a kernel call.
    """
    run = Path(run_path)
    plan = json.loads((run / "plan.json").read_text())
    root_path = Path(plan["root"])
    destination = run / f"{case_id}-native.json"
    if destination.exists():
        raise RuntimeError("Native case already recorded; no retry")
    budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
    budget.maximum_seconds = min(120, 600 - (time.time() - plan["started"]))
    result: dict[str, Any] = {
        "id": case_id,
        "status": "preparing",
        "native_attempted": 0,
        "built": 0,
        "fidelity_audited": 0,
        "full_physical_audit": 0,
    }
    app = adsk.core.Application.get()
    camera = app.activeViewport.camera
    stored = None

    def checkpoint() -> None:
        """
        Enforce time/RSS limits before additional native work.
        """
        budget.check("frozen material-route native work")

    try:
        checkpoint()
        if budget.memory() >= 3984588:
            raise RuntimeError("Insufficient launch RSS headroom")
        verify_loaded()
        for relative, expected in plan["sources"].items():
            if hashlib.sha256((root_path / relative).read_bytes()).hexdigest() != expected:
                raise RuntimeError("Source drift: " + relative)
        if (
            app.activeDocument.creationId != "86e5d125-ed43-4b89-b175-dcca0966fae6"
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Expected owned idle development design")
        root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
        entry = next(item for item in plan["cases"] if item["id"] == case_id)
        baseline = json.loads((root_path / entry["baseline_native"]).read_text())
        originals = [
            o.component for o in root.occurrences if o.component.name == baseline["component"]
        ]
        if (
            len(originals) != 1
            or originals[0].bRepBodies.item(0).revisionId != baseline["revision"]
        ):
            raise RuntimeError("Original body identity/revision changed")
        original = originals[0].bRepBodies.item(0)
        row = json.loads((root_path / entry["contracted"]).read_text())
        numerical = json.loads(
            (
                root_path
                / plan.get(
                    "numerical_results", "artifacts/verification/ribbon_contract258/result.json"
                )
            ).read_text()
        )
        evidence = next(item for item in numerical["cases"] if item["id"] == case_id)
        if evidence["final_contact"]["status"] != "separated":
            raise RuntimeError("Frozen contact gate unavailable")
        route = restore(row)
        started = time.perf_counter()
        profile = material_profile(route.targets.lines, route.targets.diameter_mm)
        patches = material_patches(route.pieces, profile)
        result["translation_seconds"] = time.perf_counter() - started
        if max(p.error_bound_mm for p in patches) > 1e-6:
            raise RuntimeError("Existing surface representation bound exceeded")
        started = time.perf_counter()
        authored = define_material_body(route.pieces, patches, checkpoint)
        result["definition_seconds"] = time.perf_counter() - started
        checkpoint()
        result["native_attempted"] = 1
        destination.write_text(json.dumps(result, indent=2))
        started = time.perf_counter()
        body = authored.definition.createBody()
        result["kernel_seconds"] = time.perf_counter() - started
        result["kernel_outcome"] = list(authored.definition.outcomeInfo)
        if body is None or not body.isSolid or body.volume <= 0:
            raise RuntimeError("Expected one positive-volume solid")
        result["built"] = 1
        occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        component = occurrence.component
        component.name = (
            plan.get("component_prefix", "259 - Deterministic contraction - ") + case_id
        )
        component.attributes.add("RibbonContraction259", "plan", str(run / "plan.json"))
        stored = component.bRepBodies.add(body)
        stored.name = plan.get("body_name", "Contracted material route - unchanged folds")
        stored.isLightBulbOn = False
        revision = stored.revisionId
        result.update(
            component=component.name,
            face_count=stored.faces.count,
            original_face_count=original.faces.count,
            volume_mm3=stored.volume * 1000,
            revision=revision,
        )
        retain_end_profiles(component, route.targets, checkpoint)
        row.update(
            lines=route.targets.lines,
            diameter_mm=route.targets.diameter_mm,
            profile_width_mm=2 * route.half_width_mm,
        )
        row["audit"] = {
            "native_points_checked": 0,
            "failed_points": [],
            "maximum_error_mm": 0.0,
            "patches_audited": 0,
            "samples": [],
            "seams_checked": 0,
            "seam_failures": [],
            "guide_records": [],
            "caps": [],
            "guide_maximum_position_error_mm": {},
            "guide_maximum_tangent_error_degrees": {},
        }
        result["audit"] = row["audit"]
        started = time.perf_counter()
        audit = runpy.run_path(
            str(
                root_path
                / plan.get(
                    "fidelity_audit",
                    "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py",
                )
            )
        )["audit"]
        audit(stored, row, budget, occurrence)
        result["audit_seconds"] = time.perf_counter() - started
        if stored.revisionId != revision or original.revisionId != baseline["revision"]:
            raise RuntimeError("Audit changed a body revision")
        result["fidelity_audited"] = 1
        started = time.perf_counter()
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(
            plan.get("display_x_cm", 150), 30 * plan["cases"].index(entry), 0
        )
        occurrence.transform2 = matrix
        stored.isLightBulbOn = True
        capture(app, occurrence, run / f"{case_id}-contracted.png")
        result["display_seconds"] = time.perf_counter() - started
        result["generation_seconds"] = (
            result["translation_seconds"] + result["definition_seconds"] + result["kernel_seconds"]
        )
        result["status"] = "built_and_named_fidelity_checks_pass"
    except Exception:
        # Intentional fail-soft host boundary preserves partial geometry and evidence.
        result.update(status="stopped", error=traceback.format_exc())
    finally:
        if stored is not None:
            stored.isLightBulbOn = False
        app.activeViewport.camera = camera
        result.update(
            elapsed_seconds=time.perf_counter() - budget.started, rss_samples=budget.samples
        )
        destination.write_text(json.dumps(result, indent=2))
        print(
            json.dumps(
                {
                    key: value
                    for key, value in result.items()
                    if key not in {"audit", "rss_samples", "kernel_outcome"}
                }
            )
        )
