"""
Re-audit one existing body without rebuilding, preserving the original failed report.
"""

from __future__ import annotations

import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from devtools.ribbon_analysis.budget import NativeBudget
from experiments.experiment_optional_appearance.host import capture

from .fidelity import audit


def audit_existing(run_path: str, case_id: str) -> None:
    """
    Measure the unchanged286body under the new explicit trim certificate, with no retry.

    Only after all named checks pass, move its display occurrence to the new review
    location. The original286report remains failed; new measurements name the policy
    and historical construction timing separately. No native builder is called.
    """
    run = Path(run_path)
    plan = json.loads((run / "plan.json").read_text())
    root_path = Path(plan["root"])
    destination = run / f"{case_id}-native.json"
    if destination.exists():
        raise RuntimeError("Existing-body audit already recorded; no retry")
    entry = next(c for c in plan["cases"] if c["id"] == case_id)
    previous = json.loads((root_path / entry["existing_native"]).read_text())
    budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
    budget.maximum_seconds = min(120, 600 - (time.time() - plan["started"]))
    result: dict[str, Any] = {
        "id": case_id,
        "status": "reauditing_existing_body",
        "native_attempted": 0,
        "built": 0,
        "existing_native_built": 1,
        "reused_native": entry["existing_native"],
        "fidelity_audited": 0,
        "full_physical_audit": 0,
        "component": previous["component"],
        "revision": previous["revision"],
        "face_count": previous["face_count"],
        "original_face_count": previous["original_face_count"],
        "generation_seconds": sum(
            previous[k] for k in ("translation_seconds", "definition_seconds", "kernel_seconds")
        ),
        "generation_timing_scope": "Historical286construction;0newconstruction",
    }
    try:
        budget.check("existing-body audit launch")
        if budget.memory() >= 3984588:
            raise RuntimeError("Existing-body audit launch headroom")
        for relative, digest in plan["sources"].items():
            if hashlib.sha256((root_path / relative).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Existing-body audit source drift: " + relative)
        app = adsk.core.Application.get()
        if (
            app.activeDocument.creationId != "86e5d125-ed43-4b89-b175-dcca0966fae6"
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Existing-body audit requires owned idle design")
        root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
        matches = [o for o in root.occurrences if o.component.name == previous["component"]]
        if len(matches) != 1:
            raise RuntimeError("Expected unique existing286body")
        occurrence = matches[0]
        body = occurrence.component.bRepBodies.item(0)
        if body.revisionId != previous["revision"]:
            raise RuntimeError("Existing286body changed")
        row = json.loads((root_path / entry["contracted"]).read_text())
        row.update(
            lines=row["case"]["lines"],
            diameter_mm=row["case"]["diameter_mm"],
            profile_width_mm=(row["case"]["lines"] + 0.2) * row["case"]["diameter_mm"],
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
        audit(body, row, budget, occurrence)
        result["audit_seconds"] = time.perf_counter() - started
        if body.revisionId != previous["revision"]:
            raise RuntimeError("Read-only audit changed existing body")
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(
            plan["display_x_cm"], 30 * plan["cases"].index(entry), 0
        )
        occurrence.transform2 = matrix
        body.isLightBulbOn = True
        capture(app, occurrence, run / f"{case_id}-existing.png")
        result.update(status="built_and_named_fidelity_checks_pass", fidelity_audited=1)
    except Exception:
        # Intentional fail-soft measurement boundary retains every partial diagnostic.
        result.update(status="stopped", error=traceback.format_exc())
    finally:
        result.update(elapsed_seconds=budget.clock() - budget.started, rss_samples=budget.samples)
        destination.write_text(json.dumps(result, indent=2))
