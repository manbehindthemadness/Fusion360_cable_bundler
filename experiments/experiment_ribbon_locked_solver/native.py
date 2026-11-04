"""
Build selected gym routes in the owned Fusion design with the locked material-fidelity policy.
"""

from __future__ import annotations

import json
import time
import traceback
from functools import partial
from pathlib import Path
from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.end_profiles import retain_end_profiles
from experiments.experiment_optional_appearance.host import capture
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.material_cylinder import FlatSurfaces
from experiments.experiment_ribbon_fold_route.material_native import (
    circular_flat_surface,
    define_material_body,
    native_point,
    native_surface,
)
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import (
    MaterialPatch,
    material_patches,
)
from experiments.experiment_ribbon_joint_route.fidelity import audit_with

from .accuracy import DISPLAY_ACCURACY, warning_summary
from .correspondence import MaterialFaces
from .fidelity_base import audit
from .lock import verify
from .progress import append
from .rejected_native import build as build_rejected
from .settings import Settings
from .versions import method


class NativeOwner:
    """
    Retain only this gym's native output visibility; preserve unrelated documents and bodies.
    """

    def __init__(
        self,
        document_id: str,
        display_x_cm: float = 610,
        *,
        flat_surfaces: FlatSurfaces = FlatSurfaces.CYLINDERS,
    ) -> None:
        """
        Bind a fixed design identity and a display-only translation after native verification.
        """
        self.document_id, self.display_x_cm = document_id, display_x_cm
        self.flat_surfaces = FlatSurfaces(flat_surfaces)
        self.displayed: Any = None
        self.rejected_job: Path | None = None
        self.on_progress: Callable[[dict[str, str]], None] | None = None

    def _progress(self, directory: Path, stage: str, message: str) -> None:
        """
        Persist a native stage and notify the optional diagnostic progress view.
        """
        entry = append(directory, stage, message)
        if self.on_progress is not None:
            self.on_progress(entry)

    def hide(self) -> None:
        """
        Hide this owner's latest accepted body when returning to the mutable gym draft.
        """
        if self.displayed is not None and self.displayed.isValid:
            self.displayed.isLightBulbOn = False

    def has_geometry(self) -> bool:
        """
        Report whether this owner's latest generated occurrence still contains native bodies.
        """
        return (
            self.displayed is not None
            and self.displayed.isValid
            and self.displayed.component.bRepBodies.count > 0
        )

    def clear(self) -> None:
        """
        Delete only the latest owned output occurrence, retaining diagnostic archives and other bodies.

        The output's auxiliary end-profile sketches are removed with its occurrence.
        Require the owned idle design; a missing or externally deleted output is a
        harmless no-op. Failed deletion retains the handle for a subsequent explicit action.
        """
        app = adsk.core.Application.get()
        if (
            app.activeDocument.creationId != self.document_id
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Clear geometry requires its owned idle design")
        if self.displayed is not None and self.displayed.isValid:
            if not self.displayed.deleteMe():
                raise RuntimeError("Fusion could not remove the generated output occurrence")
        self.displayed = None
        self.rejected_job = None

    def inspect_rejected(self, directory: Path) -> dict[str, Any]:
        """
        Own an inspection-only rejected body under the ordinary hide/clear/capture controls.
        """
        occurrence, result = build_rejected(
            directory, self.document_id, self.display_x_cm, self.flat_surfaces
        )
        if occurrence is not None:
            self.hide()
            self.displayed = occurrence
            self.rejected_job = directory.resolve()
            occurrence.isLightBulbOn = True
        return result

    def build(self, directory: Path) -> dict[str, Any]:
        """
        Attempt one joined solid, preserve failures and expose only named-fidelity success.

        This is a development gym verification path, not a mandatory product-time
        audit. Optional coordinate attributes require no appearances or bitmaps.
        """
        destination = directory / "native-result.json"
        self._progress(directory, "native", "Validating native build inputs.")
        if destination.exists():
            raise RuntimeError("This frozen gym job already has a native disposition; no retry")
        plan = json.loads((directory / "plan.json").read_text())
        selected = method(plan["version"])
        settings = Settings.parse(plan["settings"])
        budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
        result: dict[str, Any] = {
            "status": "preparing",
            "version": selected.identifier,
            "native_attempted": 0,
            "built": 0,
            "fidelity_audited": 0,
            "full_physical_audit": 0,
            "accuracy_goal_mm": DISPLAY_ACCURACY.goal_mm,
            "accuracy_warning_below_mm": DISPLAY_ACCURACY.warning_below_mm,
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
            self._progress(directory, "native", "Translating material geometry into NURBS patches.")
            profile = material_profile(route.targets.lines, route.targets.diameter_mm)
            patches = material_patches(route.pieces, profile)
            result["translation_seconds"] = time.perf_counter() - started
            representation_error = max(p.error_bound_mm for p in patches)
            if not DISPLAY_ACCURACY.accepts(representation_error):
                raise RuntimeError("Selected material surface representation bound exceeded")
            started = time.perf_counter()
            self._progress(directory, "native", "Defining native faces, edges and seams.")

            def surface_factory(patch: MaterialPatch) -> Any:
                """
                Choose equivalent flat supports under this owner's explicit construction policy.
                """
                return (
                    circular_flat_surface(route.pieces[patch.piece_index], patch)
                    if self.flat_surfaces is FlatSurfaces.CYLINDERS
                    else native_surface(patch)
                )

            authored = define_material_body(
                route.pieces, patches, checkpoint, surface_factory=surface_factory
            )
            result["flat_surface_policy"] = self.flat_surfaces.value
            result["definition_seconds"] = time.perf_counter() - started
            checkpoint()
            result["native_attempted"] = 1
            self._progress(directory, "native", "Creating the native BRep solid in Fusion.")
            destination.write_text(json.dumps(result, indent=2))
            started = time.perf_counter()
            transient = authored.definition.createBody()
            result["kernel_seconds"] = time.perf_counter() - started
            if transient is None or not transient.isSolid or transient.volume <= 0:
                raise RuntimeError("Selected gym builder requires one positive-volume solid")
            occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            occurrence.component.name = selected.label + " - " + directory.name
            body = occurrence.component.bRepBodies.add(transient)
            body.name = "Material ribbon - " + selected.label
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
            DISPLAY_ACCURACY.observe(row["audit"], "surface_representation", representation_error)
            self._progress(
                directory,
                "audit",
                f"Solid created ({body.faces.count} faces); checking surface, guide, seam and cap fidelity.",
            )
            started = time.perf_counter()
            face_records = authored.face_records
            if body.faces.count == len(patches) + 2:
                audit_with(body, row, budget, occurrence, partial(audit, accuracy=DISPLAY_ACCURACY))
                result["face_mapping_policy"] = "original one-to-one native patches"
            else:

                def trimmed_distance(point: Any, entity: Any) -> float:
                    """
                    Measure actual native trim support for the selected accuracy policy.
                    """
                    return app.measureManager.measureMinimumDistance(point, entity).value * 10

                families = MaterialFaces(
                    body,
                    route,
                    patches,
                    occurrence,
                    budget,
                    native_point,
                    trimmed_distance,
                    row["audit"],
                    accuracy=DISPLAY_ACCURACY,
                    collapsed_boundary_tolerance_mm=app.pointTolerance * 10,
                )
                audit(
                    body,
                    row,
                    budget,
                    occurrence,
                    material_faces=families,
                    accuracy=DISPLAY_ACCURACY,
                )
                face_records = families.records()
                result["face_mapping_policy"] = "verified material regions across native faces"
            warning = warning_summary(row["audit"].get("accuracy_warnings", []))
            if warning is not None:
                result["precision_warning"] = warning
                self._progress(directory, "warning", warning["message"])
            result.update(fidelity_audited=1, audit_seconds=time.perf_counter() - started)
            if body.revisionId != revision:
                raise RuntimeError("Native fidelity audit changed the body")
            started = time.perf_counter()
            if settings.material_uv:
                self._progress(directory, "uv", "Storing optional material-coordinate metadata.")
                appearances_before = design.appearances.count
                metadata = json.loads((directory / "material-uv.json").read_text())
                encoded = json.dumps(metadata, separators=(",", ":"))
                occurrence.component.attributes.add("RibbonMaterialCoordinates", "map", encoded)
                for index, record in enumerate(face_records):
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
                result.update(material_uv_faces=len(face_records), appearances_created=0)
            result["material_uv_seconds"] = time.perf_counter() - started
            retain_end_profiles(occurrence.component, route.targets, checkpoint)
            matrix = adsk.core.Matrix3D.create()
            matrix.translation = adsk.core.Vector3D.create(self.display_x_cm, 0, 0)
            occurrence.transform2 = matrix
            self.hide()
            occurrence.isLightBulbOn = True
            body.isLightBulbOn = True
            self.displayed = occurrence
            self.rejected_job = None
            self._progress(
                directory,
                "warning" if result.get("precision_warning") else "native",
                "Showing generated body with recorded dimensional accuracy warnings."
                if result.get("precision_warning")
                else "Fidelity checks passed; showing the generated body.",
            )
            capture(app, occurrence, directory / "native.png")
            result["status"] = (
                "built_with_precision_warning"
                if result.get("precision_warning")
                else "built_and_named_fidelity_checks_pass"
            )
        except Exception:
            # Intentional fail-soft native boundary preserves partial bodies and complete evidence.
            if body is not None:
                body.isLightBulbOn = False
            result.update(status="stopped", error=traceback.format_exc())
            self._progress(directory, "failed", result["error"].strip().splitlines()[-1])
        finally:
            result.update(
                elapsed_seconds=budget.clock() - budget.started, rss_samples=budget.samples
            )
            destination.write_text(json.dumps(result, indent=2))
        return result
