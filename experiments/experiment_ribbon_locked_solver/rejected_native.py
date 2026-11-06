"""
Attempt one native inspection body without accepting or repairing a rejected route.
"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.end_profiles import retain_end_profiles
from devtools.ribbon_analysis.inspection.archive import write_document
from experiments.experiment_ribbon_fold_route.material_cylinder import FlatSurfaces
from experiments.experiment_ribbon_fold_route.material_native import (
    circular_flat_surface,
    define_material_body,
    native_surface,
)
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches

from .lock import verify
from .progress import append
from .rejected_selection import describe, select


def build(
    directory: Path, document_id: str, display_x_cm: float, flat_surfaces: FlatSurfaces
) -> tuple[Any, dict[str, Any]]:
    """
    Build the shared selected rejected result once, returning an occurrence or scaffold fallback.

    Contact and numerical failure remain authoritative. No fidelity audit, healing,
    appearance, UV work, route search or native-ready route file is introduced.
    Source/resource/context errors stop this attempt just like kernel rejection.
    The durable result prevents retries even if Fusion returned no usable body.
    """
    destination = directory / "rejected-native-result.json"
    if destination.exists():
        raise RuntimeError("Rejected native inspection already attempted; no retry")
    result: dict[str, Any] = {
        "status": "scaffold_fallback",
        "built": 0,
        "native_attempts": 0,
        "accepted": False,
        "native_fidelity_audits": 0,
    }
    occurrence: Any = None
    budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
    try:
        budget.check("rejected inspection launch")
        pins = verify()
        plan = json.loads((directory / "plan.json").read_text())
        app = adsk.core.Application.get()
        if (
            plan.get("sources") != pins
            or plan.get("document_id") != document_id
            or app.activeDocument is None
            or app.activeDocument.creationId != document_id
            or app.userInterface.activeCommand != "SelectCommand"
            or budget.memory() >= 3984588
            or (directory / "cancel").exists()
        ):
            raise RuntimeError("Rejected inspection context/source/resource/cancellation guard")
        ledger = directory / "rejected-geometry.json"
        if ledger.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Rejected geometry exceeds32MiB")
        payload = json.loads(ledger.read_text())
        if not isinstance(payload, dict):
            raise ValueError("Rejected inspection needs a structured ledger")
        route, branch = select(payload, plan["targets"])
        result.update(
            roots=branch.get("roots"),
            inspection_origin=branch.get("kind", "shortest_closed_branch"),
            contact_disposition=branch["disposition"],
        )
        write_document(
            directory / "rejected-native-plan.json",
            {
                "sources": pins,
                "route": branch["route"],
                "contact": branch.get("contact"),
                "accepted": False,
                "scope": "One native inspection attempt; rejected status retained; no audit/repair/retry",
                "seconds": 120,
                "rss_kib": 4194304,
            },
        )

        def checkpoint() -> None:
            """
            Check cancellation and fixed sources before scheduling further native operations.
            """
            budget.check("rejected native inspection")
            if (directory / "cancel").exists() or verify() != pins:
                raise RuntimeError("Rejected inspection cancellation/source drift")

        append(
            directory,
            "inspection",
            f"Trying native inspection of {describe(branch)} ({route.material_length_mm:.6f} mm); NOT ACCEPTED.",
        )
        started = perf_counter()
        patches = material_patches(
            route.pieces, material_profile(route.targets.lines, route.targets.diameter_mm)
        )
        result["translation_seconds"] = perf_counter() - started
        checkpoint()
        started = perf_counter()
        authored = define_material_body(
            route.pieces,
            patches,
            checkpoint,
            surface_factory=lambda patch: (
                circular_flat_surface(route.pieces[patch.piece_index], patch)
                if flat_surfaces is FlatSurfaces.CYLINDERS
                else native_surface(patch)
            ),
        )
        result["definition_seconds"] = perf_counter() - started
        checkpoint()
        result["native_attempts"] = 1
        destination.write_text(json.dumps(result, indent=2))
        started = perf_counter()
        transient = authored.definition.createBody()
        result["kernel_seconds"] = perf_counter() - started
        if transient is None or not transient.isSolid or transient.volume <= 0:
            raise RuntimeError("Fusion did not return a positive-volume inspection solid")
        checkpoint()
        design = adsk.fusion.Design.cast(app.activeProduct)
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(display_x_cm, 0, 0)
        occurrence = design.rootComponent.occurrences.addNewComponent(matrix)
        occurrence.component.name = "REJECTED native inspection - " + directory.name
        occurrence.isLightBulbOn = False
        body = occurrence.component.bRepBodies.add(transient)
        if body is None:
            raise RuntimeError("Fusion could not persist the inspection solid")
        body.name = "NOT ACCEPTED - rejected route"
        occurrence.component.attributes.add("RejectedRibbonDiagnostic", "source", str(directory))
        retain_end_profiles(occurrence.component, route.targets, checkpoint)
        result.update(
            status="native_inspection_built",
            built=1,
            face_count=body.faces.count,
            volume_mm3=body.volume * 1000,
            generation_seconds=result["translation_seconds"]
            + result["definition_seconds"]
            + result["kernel_seconds"],
        )
        body.isLightBulbOn = True
    except (ArithmeticError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        # Optional failure visualization must preserve the numerical stop and scaffold fallback.
        result["error"] = f"{type(error).__name__}: {error}"
        if occurrence is not None and occurrence.isValid:
            occurrence.isLightBulbOn = False
        occurrence = None
    result.update(elapsed_seconds=perf_counter() - budget.started, rss_samples=budget.samples)
    destination.write_text(json.dumps(result, indent=2))
    append(
        directory,
        "inspection",
        "Rejected native body available; NOT ACCEPTED."
        if result["built"]
        else "Native inspection unavailable; using diagnostic scaffold. "
        + str(result.get("error", "")),
    )
    return occurrence, result
