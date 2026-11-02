"""
Build selected gym routes in the owned Fusion design with the locked material-fidelity policy.
"""

from __future__ import annotations

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
from devtools.ribbon_analysis.end_profiles import retain_end_profiles
from experiments.experiment_optional_appearance.host import capture
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.material_native import define_material_body
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches
from experiments.experiment_ribbon_joint_route.fidelity import audit_with

from .fidelity_base import audit
from .lock import verify
from .settings import VERSION, Settings


class NativeOwner:
    """
    Retain only this gym's native output visibility; preserve unrelated documents and bodies.
    """

    def __init__(self, document_id: str, display_x_cm: float = 610) -> None:
        """
        Bind a fixed design identity and a display-only translation after native verification.
        """
        self.document_id, self.display_x_cm = document_id, display_x_cm
        self.displayed: Any = None

    def hide(self) -> None:
        """
        Hide this owner's latest accepted body when returning to the mutable gym draft.
        """
        if self.displayed is not None and self.displayed.isValid:
            self.displayed.isLightBulbOn = False

    def build(self, directory: Path) -> dict[str, Any]:
        """
        Attempt one joined solid, preserve failures and expose only named-fidelity success.

        This is a development gym verification path, not a mandatory product-time
        audit. Optional coordinate attributes require no appearances or bitmaps.
        """
        destination = directory / "native-result.json"
        if destination.exists():
            raise RuntimeError("This frozen gym job already has a native disposition; no retry")
        plan = json.loads((directory / "plan.json").read_text())
        settings = Settings.parse(plan["settings"])
        budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
        result: dict[str, Any] = {
            "status": "preparing",
            "version": VERSION,
            "native_attempted": 0,
            "built": 0,
            "fidelity_audited": 0,
            "full_physical_audit": 0,
        }
        body = None

        def checkpoint() -> None:
            """
            Enforce the frozen native time/RSS limits before scheduling more work.
            """
            budget.check("selected gym native work")

        try:
            checkpoint()
            if budget.memory() >= 3984588 or verify() != plan["sources"]:
                raise RuntimeError("Native launch headroom/source-lock guard")
            app = adsk.core.Application.get()
            if (
                app.activeDocument.creationId != self.document_id
                or plan["document_id"] != self.document_id
                or app.userInterface.activeCommand != "SelectCommand"
            ):
                raise RuntimeError("Selected solver requires its owned idle design")
            design = adsk.fusion.Design.cast(app.activeProduct)
            root = design.rootComponent
            route = restore(json.loads((directory / "route.json").read_text()))
            if snapshot(route)["case"] != plan["targets"]:
                raise RuntimeError("Native route targets differ from frozen gym inputs")
            started = time.perf_counter()
            profile = material_profile(route.targets.lines, route.targets.diameter_mm)
            patches = material_patches(route.pieces, profile)
            result["translation_seconds"] = time.perf_counter() - started
            if max(p.error_bound_mm for p in patches) > 1e-6:
                raise RuntimeError("Selected material surface representation bound exceeded")
            started = time.perf_counter()
            authored = define_material_body(route.pieces, patches, checkpoint)
            result["definition_seconds"] = time.perf_counter() - started
            checkpoint()
            result["native_attempted"] = 1
            destination.write_text(json.dumps(result, indent=2))
            started = time.perf_counter()
            transient = authored.definition.createBody()
            result["kernel_seconds"] = time.perf_counter() - started
            if transient is None or not transient.isSolid or transient.volume <= 0:
                raise RuntimeError("Selected gym builder requires one positive-volume solid")
            occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            occurrence.component.name = "Selected solver v1 - " + directory.name
            body = occurrence.component.bRepBodies.add(transient)
            body.name = "Material ribbon - selected solver v1"
            body.isLightBulbOn = False
            revision = body.revisionId
            result.update(
                built=1,
                component=occurrence.component.name,
                face_count=body.faces.count,
                revision=revision,
                generation_seconds=result["translation_seconds"]
                + result["definition_seconds"]
                + result["kernel_seconds"],
            )
            row = snapshot(route)
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
            audit_with(body, row, budget, occurrence, audit)
            result.update(fidelity_audited=1, audit_seconds=time.perf_counter() - started)
            if body.revisionId != revision:
                raise RuntimeError("Native fidelity audit changed the body")
            started = time.perf_counter()
            if settings.material_uv:
                appearances_before = design.appearances.count
                metadata = json.loads((directory / "material-uv.json").read_text())
                encoded = json.dumps(metadata, separators=(",", ":"))
                occurrence.component.attributes.add("RibbonMaterialCoordinates", "map", encoded)
                for index, record in enumerate(authored.face_records):
                    face = body.faces.item(index)
                    source = json.dumps(record, separators=(",", ":"))
                    face.attributes.add("RibbonMaterialCoordinates", "source_face", source)
                    stored = face.attributes.itemByName("RibbonMaterialCoordinates", "source_face")
                    if stored is None or stored.value != source:
                        raise RuntimeError("Material face coordinate metadata read-back failed")
                stored = occurrence.component.attributes.itemByName(
                    "RibbonMaterialCoordinates", "map"
                )
                if stored is None or stored.value != encoded:
                    raise RuntimeError("Material coordinate metadata read-back failed")
                if design.appearances.count != appearances_before or body.revisionId != revision:
                    raise RuntimeError("Material metadata changed appearances or geometry")
                result.update(material_uv_faces=len(authored.face_records), appearances_created=0)
            result["material_uv_seconds"] = time.perf_counter() - started
            retain_end_profiles(occurrence.component, route.targets, checkpoint)
            matrix = adsk.core.Matrix3D.create()
            matrix.translation = adsk.core.Vector3D.create(self.display_x_cm, 0, 0)
            occurrence.transform2 = matrix
            self.hide()
            occurrence.isLightBulbOn = True
            body.isLightBulbOn = True
            self.displayed = occurrence
            capture(app, occurrence, directory / "native.png")
            result["status"] = "built_and_named_fidelity_checks_pass"
        except Exception:
            # Intentional fail-soft native boundary preserves partial bodies and complete evidence.
            if body is not None:
                body.isLightBulbOn = False
            result.update(status="stopped", error=traceback.format_exc())
        finally:
            result.update(
                elapsed_seconds=budget.clock() - budget.started, rss_samples=budget.samples
            )
            destination.write_text(json.dumps(result, indent=2))
        return result
