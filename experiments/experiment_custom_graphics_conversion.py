"""
Probe Custom Graphics mesh readback and faceted BRep conversion inside Fusion.

Requires Fusion's live adsk runtime and the preview meshConvertFeatures API.
Run once from Scripts and Add-Ins or the development MCP script dispatcher.
Creates one unsaved scratch design, leaves it open, and restores the previous
active document. Never modifies existing documents or production code.

Frozen procedure: one open bent strip, six vertices, four triangles, identity
transforms; one mesh insertion and one faceted conversion, no retries or fitting.
Predict one non-solid BRep with four planar faces. Audit area (1e-8 cm^2) and
bounds (1e-8 cm); do not claim smoothness, stripe-family or ribbon coverage.
Budget: one native conversion, no search/refinement, 30 s scheduling cap. An
in-flight kernel call cannot safely be canceled; record any overrun and stop.
Reports include fixture/source hashes and live under ignored artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import adsk.core
import adsk.fusion

COORDINATES_CM = (0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.5, 0.0, 0.0,
                  0.5, 0.1, 0.0, 1.0, 0.0, 0.2, 1.0, 0.1, 0.2)
TRIANGLES = (0, 2, 1, 1, 2, 3, 2, 4, 3, 3, 4, 5)


def run(context: object) -> None:
    """
    Execute the fixed probe and retain success or failure evidence in a JSON report.
    """
    started = perf_counter()
    app = adsk.core.Application.get()
    previous = app.activeDocument
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    report_path = (Path(__file__).resolve().parent.parent / "artifacts" /
                   "verification" / "custom_graphics_conversion" / f"{stamp}.json")
    report: dict[str, object] = {
        "case_id": "open-bent-strip-01", "planned_cases": 1,
        "native_attempted": 0, "built": 0, "audited": 0,
        "prediction": "one non-solid BRep, four planar faces",
        "method": "FacetedMeshConvertMethodType", "fusion_version": app.version,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(json.dumps(
            [COORDINATES_CM, TRIANGLES]).encode()).hexdigest(),
        "status": "unresolved", "stage": "scratch", "tolerance": 1e-8,
        "rule_scope": "API conversion only; no routing or mechanical audit",
    }
    try:
        scratch = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        scratch.name = f"Custom Graphics Conversion {stamp}"
        report["scratch_name"] = scratch.name
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            raise RuntimeError("Scratch is not a Fusion design.")
        root = design.rootComponent
        group = root.customGraphicsGroups.add()
        group.name = "Original Custom Graphics"
        coordinates = adsk.fusion.CustomGraphicsCoordinates.create(list(COORDINATES_CM))
        graphics = group.addMesh(coordinates, list(TRIANGLES), [], [])
        if graphics is None:
            raise RuntimeError("Custom Graphics mesh creation failed.")
        read_coordinates = list(graphics.coordinates.coordinates)
        read_indices = list(graphics.vertexIndexList)
        report["readback_exact"] = (read_coordinates == list(COORDINATES_CM)
                                     and read_indices == list(TRIANGLES))
        if not report["readback_exact"]:
            raise RuntimeError("Graphics readback differs from frozen input.")
        report["stage"] = "mesh insertion"
        mesh = root.meshBodies.addByTriangleMeshData(read_coordinates, read_indices, [], [])
        if mesh is None:
            raise RuntimeError("Persistent mesh insertion failed.")
        mesh.name = "Readback Mesh"
        if perf_counter() - started >= 30.0:
            raise RuntimeError("Scheduling cap reached before native conversion.")
        report["stage"] = "native conversion"
        converts = root.features.meshConvertFeatures
        conversion_input = converts.createInput([mesh])
        if conversion_input is None:
            raise RuntimeError("Conversion input creation failed.")
        conversion_input.meshConvertMethodType = (
            adsk.fusion.MeshConvertMethodTypes.FacetedMeshConvertMethodType)
        report["native_attempted"] = 1
        build_started = perf_counter()
        feature = converts.add(conversion_input)
        report["native_seconds"] = perf_counter() - build_started
        if feature is None or root.bRepBodies.count != 1:
            raise RuntimeError("Conversion did not produce exactly one BRep body.")
        report["built"] = 1
        body = root.bRepBodies.item(0)
        body.name = "Converted Faceted Surface"
        report["stage"] = "audit"
        expected_area = 0.05 + 0.1 * math.sqrt(0.5 ** 2 + 0.2 ** 2)
        bounds = body.boundingBox
        actual_bounds = [bounds.minPoint.x, bounds.minPoint.y, bounds.minPoint.z,
                         bounds.maxPoint.x, bounds.maxPoint.y, bounds.maxPoint.z]
        face_types = [body.faces.item(i).geometry.objectType for i in range(body.faces.count)]
        report.update({"body_type": body.objectType, "is_solid": body.isSolid,
                       "face_count": body.faces.count, "face_types": face_types,
                       "area_cm2": body.area, "expected_area_cm2": expected_area,
                       "bounds_cm": actual_bounds})
        checks = {"non_solid": not body.isSolid, "four_faces": body.faces.count == 4,
                  "planar_faces": all(t == adsk.core.Plane.classType() for t in face_types),
                  "area": abs(body.area - expected_area) <= 1e-8,
                  "bounds": all(abs(a - b) <= 1e-8 for a, b in zip(
                      actual_bounds, [0.0, 0.0, 0.0, 1.0, 0.1, 0.2]))}
        report["checks"] = checks
        report["audited"] = 1
        report["status"] = "passed" if all(checks.values()) else "failed"
        group.isVisible = False
        if mesh.isValid:
            mesh.isLightBulbOn = False
    except (RuntimeError, AttributeError, TypeError) as error:
        # Diagnostic boundary retains unsupported APIs and kernel failures without retry.
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["total_seconds"] = perf_counter() - started
        report["scheduling_cap_exceeded"] = report["total_seconds"] > 30.0
        if previous is not None and previous.isValid:
            report["previous_document_restored"] = previous.activate()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        app.log("CUSTOM_GRAPHICS_CONVERSION=" + json.dumps(report))
        print("CUSTOM_GRAPHICS_CONVERSION=" + json.dumps(report))
        print(f"Report: {report_path}")
