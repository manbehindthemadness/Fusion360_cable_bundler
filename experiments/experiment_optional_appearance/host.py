"""
Export and apply optional color maps in one guarded, existing Fusion test design.

Run through the local MCP runner with an immutable phase plan. Fusion supplies
adsk. Every write targets newly owned diagnostic copies; production is untouched.
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

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.inspection.archive import write_document
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches

DOCUMENT_ID = "86e5d125-ed43-4b89-b175-dcca0966fae6"
LIBRARY_ID = "BA5EE55E-9982-449B-9D66-9F036540E140"


def refresh(app: Any) -> None:
    """
    Allow the native renderer to expose its actual display mesh.
    """
    app.activeViewport.refresh()
    adsk.doEvents()
    app.activeViewport.refresh()


def source_settings(appearance: Any) -> dict[str, Any]:
    """
    Capture the supported color-map state without assuming arbitrary shader support.
    """
    texture = appearance.appearanceProperties.itemById("opaque_albedo").connectedTexture
    if texture is None:
        raise RuntimeError("Expected a connected opaque color map")
    return {
        "name": appearance.name,
        "path": appearance.colorTexture,
        "type": int(texture.textureType),
        "roughness": appearance.roughness,
        "properties": {
            name: texture.properties.itemById(name).value
            for name in (
                "texture_RealWorldScaleX",
                "texture_RealWorldScaleY",
                "texture_RealWorldOffsetX",
                "texture_RealWorldOffsetY",
                "texture_WAngle",
                "texture_URepeat",
                "texture_VRepeat",
            )
        },
    }


def settings(appearance: Any, values: dict[str, Any]) -> None:
    """
    Apply required bitmap controls after connecting the source image.
    """
    texture = appearance.appearanceProperties.itemById("opaque_albedo").connectedTexture
    if texture is None:
        raise RuntimeError("Missing connected color map")
    for name, value in values.items():
        prop = texture.properties.itemById(name)
        if prop is None:
            raise RuntimeError("Missing required texture property: " + name)
        prop.value = value


def capture(app: Any, occurrence: Any, path: Path) -> None:
    """
    Frame one root-owned diagnostic body at its declared display translation.
    """
    body = occurrence.component.bRepBodies.item(0)
    box = body.boundingBox
    shift = occurrence.transform2.translation
    center = adsk.core.Point3D.create(
        (box.minPoint.x + box.maxPoint.x) / 2 + shift.x,
        (box.minPoint.y + box.maxPoint.y) / 2 + shift.y,
        (box.minPoint.z + box.maxPoint.z) / 2 + shift.z,
    )
    span = max(
        box.maxPoint.x - box.minPoint.x,
        box.maxPoint.y - box.minPoint.y,
        box.maxPoint.z - box.minPoint.z,
        0.3,
    )
    camera = app.activeViewport.camera
    camera.target = center
    camera.eye = adsk.core.Point3D.create(center.x + span, center.y - span, center.z + span)
    camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
    camera.viewExtents = span * 1.5
    camera.isFitView = False
    app.activeViewport.camera = camera
    refresh(app)
    app.activeViewport.saveAsImageFile(str(path), 1280, 960)


def export_cases(
    app: Any,
    root: Any,
    run: Path,
    plan: dict[str, Any],
    budget: NativeBudget,
    output: dict[str, Any],
) -> None:
    """
    Create four untextured copies before selecting a source appearance later.
    """
    design = adsk.fusion.Design.cast(app.activeProduct)
    library = app.materialLibraries.itemById(LIBRARY_ID)
    base = library.appearances.itemById("Prism-129")
    plain = design.appearances.addByCopy(base, "240 - Initial plain color")
    plain.color = adsk.core.Color.create(40, 120, 210, 255)
    originals = []
    copies = []
    for spec in plan["cases"]:
        budget.check("prepare unchanged appearance-only copy")
        evidence = json.loads((Path(plan["root_path"]) / spec["evidence"]).read_text())
        original = next(
            o.component for o in root.occurrences if o.component.name == evidence["component"]
        ).bRepBodies.item(0)
        if original.revisionId != evidence["revision"]:
            raise RuntimeError("Measured original changed")
        occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occurrence.component.name = "240 - Deferred appearance - " + spec["id"]
        body = occurrence.component.bRepBodies.add(
            adsk.fusion.TemporaryBRepManager.get().copy(original)
        )
        body.appearance = plain
        for face in body.faces:
            face.appearance = None
        body.isLightBulbOn = True
        occurrence.isLightBulbOn = False
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(100, 0, 0)
        occurrence.transform2 = matrix
        if body.faces.count != original.faces.count or abs(body.volume - original.volume) > 1e-10:
            raise RuntimeError("Copy changed geometry")
        originals.append((original, evidence["revision"]))
        copies.append((occurrence, spec))
        output["prepared"].append(
            {
                "id": spec["id"],
                "component": occurrence.component.name,
                "revision": body.revisionId,
                "volume_cm3": body.volume,
                "source_revision": original.revisionId,
                "initial_color_texture": plain.colorTexture,
                "initial_color": [plain.color.red, plain.color.green, plain.color.blue],
            }
        )
    if plain.colorTexture:
        raise RuntimeError("Unrequested image map at initial preparation")
    source = design.appearances.addByCopy(base, "240 - Deferred source - Fabric base color")
    native = library.appearances.itemById("Prism-213")
    source.colorTexture = native.colorTexture
    source.roughness = 0.47
    settings(
        source,
        {
            "texture_RealWorldScaleX": 1.2,
            "texture_RealWorldScaleY": 0.3,
            "texture_RealWorldOffsetX": 0.0,
            "texture_RealWorldOffsetY": 0.0,
            "texture_WAngle": 0.0,
            "texture_URepeat": True,
            "texture_VRepeat": True,
        },
    )
    output["source"] = source_settings(source)
    output["source"]["library_id"] = "Prism-213"
    output["source"]["library_name"] = native.name
    output["source"]["alternate_image"] = library.appearances.itemById("Prism-202").colorTexture
    for old in root.occurrences:
        if old.component.name == "230 - Per-face baked material texture":
            old.isLightBulbOn = False
    for occurrence, spec in copies:
        started = time.perf_counter()
        budget.check("start native chart export")
        body = occurrence.component.bRepBodies.item(0)
        body.appearance = source
        occurrence.isLightBulbOn = True
        refresh(app)
        row = json.loads((Path(plan["root_path"]) / spec["input"]).read_text())
        pieces = tuple(
            PlacedPiece(
                Pose(**{key: Vector3(**value) for key, value in item["pose"].items()}),
                CylindricalFold(**item["geometry"])
                if item["kind"] == "fold"
                else Straight(**item["geometry"]),
                item["label"],
            )
            for item in row["pieces"]
        )
        patches = material_patches(pieces, material_profile(row["lines"], row["diameter_mm"]))
        record = next(r for r in output["prepared"] if r["id"] == spec["id"])
        record["faces"] = []
        if body.faces.count != len(patches) + 2:
            raise RuntimeError("Source topology mismatch")
        for index, patch in enumerate(patches):
            if index % 16 == 0:
                budget.check("bounded group of sixteen mesh reads")
            face = body.faces.item(index)
            meshes = face.meshManager.displayMeshes
            if not meshes.count:
                raise RuntimeError("Actual display mesh unavailable")
            mesh = meshes.item(0)
            points, uv = mesh.nodeCoordinates, mesh.textureCoordinates
            if len(points) != len(uv) or len(points) > 200000:
                raise RuntimeError("Invalid display chart")
            record["faces"].append(
                {
                    "index": index,
                    "piece_index": patch.piece_index,
                    "region": patch.region,
                    "profile_index": patch.profile_index,
                    "points_cm": [[p.x, p.y, p.z] for p in points],
                    "uv": [[p.x, p.y] for p in uv],
                    "triangles": list(mesh.nodeIndices),
                    "edges": [e.tempId for e in face.edges],
                }
            )
        record["chart_export_seconds"] = time.perf_counter() - started
        write_document(run / (spec["id"] + "-charts.json"), record)
        capture(app, occurrence, run / (spec["id"] + "-before.png"))
        occurrence.isLightBulbOn = False
    if any(body.revisionId != revision for body, revision in originals):
        raise RuntimeError("Original changed")
    output["status"] = "four_deferred_sources_exported"


def apply_cases(
    app: Any,
    root: Any,
    run: Path,
    plan: dict[str, Any],
    budget: NativeBudget,
    output: dict[str, Any],
) -> None:
    """
    Assign baked source-image variants and independently read every installed chart.
    """
    design = adsk.fusion.Design.cast(app.activeProduct)
    source = design.appearances.itemByName("240 - Deferred source - Fabric base color")
    baked = json.loads((Path(plan["bake_path"]) / "result.json").read_text())
    for case in baked["cases"]:
        budget.check("apply one complete case")
        occurrence = next(o for o in root.occurrences if o.component.name == case["component"])
        body = occurrence.component.bRepBodies.item(0)
        if body.revisionId != case["revision"] or abs(body.volume - case["volume_cm3"]) > 1e-12:
            raise RuntimeError("Copy geometry changed")
        record: dict[str, Any] = {"id": case["id"], "checked_faces": 0}
        output["cases"].append(record)
        started = time.perf_counter()
        for item in case["faces"]:
            index = item["index"]
            if index % 16 == 0:
                budget.check("bounded group of sixteen appearance assignments")
            path = Path(item["path"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise RuntimeError("Stale baked image")
            appearance = design.appearances.addByCopy(
                source, f"{run.name} - {case['id']} - {index:03}"
            )
            appearance.colorTexture = str(path)
            values = {
                "texture_RealWorldScaleX": item["bounds"][2] / 2.54,
                "texture_RealWorldScaleY": item["bounds"][3] / 2.54,
                "texture_RealWorldOffsetX": item["bounds"][0] / 2.54,
                "texture_RealWorldOffsetY": item["bounds"][1] / 2.54,
                "texture_WAngle": 0.0,
                "texture_URepeat": False,
                "texture_VRepeat": False,
                "unifiedbitmap_Blur": 0.0,
            }
            settings(appearance, values)
            body.faces.item(index).appearance = appearance
            texture = appearance.appearanceProperties.itemById("opaque_albedo").connectedTexture
            if any(
                texture.properties.itemById(key).value != value for key, value in values.items()
            ):
                raise RuntimeError("Installed texture settings mismatch")
            if (
                appearance.roughness != 0.47
                or hashlib.sha256(Path(appearance.colorTexture).read_bytes()).hexdigest()
                != item["sha256"]
            ):
                raise RuntimeError("Source properties or image changed")
        record["assignment_seconds"] = time.perf_counter() - started
        occurrence.isLightBulbOn = True
        refresh(app)
        charts = json.loads((Path(plan["export_path"]) / (case["id"] + "-charts.json")).read_text())
        for item in charts["faces"]:
            if item["index"] % 16 == 0:
                budget.check("read assigned native charts")
            mesh = body.faces.item(item["index"]).meshManager.displayMeshes.item(0)
            if (
                [[p.x, p.y] for p in mesh.textureCoordinates] != item["uv"]
                or [[p.x, p.y, p.z] for p in mesh.nodeCoordinates] != item["points_cm"]
                or list(mesh.nodeIndices) != item["triangles"]
            ):
                raise RuntimeError("Rendered chart changed")
            record["checked_faces"] += 1
        if body.revisionId != case["revision"] or abs(body.volume - case["volume_cm3"]) > 1e-12:
            raise RuntimeError("Appearance operation changed geometry")
        record["geometry_unchanged"] = True
        capture(app, occurrence, run / (case["id"] + "-after.png"))
        occurrence.isLightBulbOn = False
    first = next(o for o in root.occurrences if o.component.name == baked["cases"][0]["component"])
    first.isLightBulbOn = True
    capture(app, first, run / "visible-calibration.png")
    output["status"] = "four_source_image_applications_checked"


def run_phase(run_directory: str) -> None:
    """
    Execute a single source-pinned phase, preserving partial results on any stop.
    """
    run = Path(run_directory)
    plan = json.loads((run / "plan.json").read_text())
    budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
    output: dict[str, Any] = {
        "status": "preparing",
        "prepared": [],
        "cases": [],
        "new_geometry_attempts": 0,
        "new_solves": 0,
    }
    try:
        for name, digest in plan["sources"].items():
            if hashlib.sha256((Path(plan["root_path"]) / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Source drift: " + name)
        budget.check("launch")
        if budget.memory() >= 3984588:
            raise RuntimeError("Launch headroom")
        app = adsk.core.Application.get()
        if (
            app.activeDocument.creationId != DOCUMENT_ID
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Owned idle document guard")
        root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
        if plan["phase"] == "export":
            export_cases(app, root, run, plan, budget, output)
        elif plan["phase"] == "apply":
            apply_cases(app, root, run, plan, budget, output)
        else:
            raise ValueError("Unknown native phase")
    except Exception:
        # External failures preserve partial copies, appearances and measurements.
        output["status"] = "stopped"
        output["error"] = traceback.format_exc()
    finally:
        output["rss_samples"] = budget.samples
        output["elapsed_seconds"] = budget.clock() - budget.started
        write_document(run / "result.json", output)
        print(json.dumps({k: v for k, v in output.items() if k not in {"prepared", "rss_samples"}}))
