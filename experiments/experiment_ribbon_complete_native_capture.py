"""
Inspect retained native cap planes and physical material inverses without authoring CAD.

Requires the exact frozen qualification owner in a live idle Fusion session and
Fusion's supplied adsk. Run once under resume3229/plan.json; every read is bounded
by the original process cap and a shorter read-only review deadline. No solver,
metadata write, texture, target fitting, native rebuild or face repair occurs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, cast

from artifacts.verification.resume3202 import runtime
from artifacts.verification.resume3227 import manifest, memory
from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.budget import NativeBudget
from experiments.experiment_optional_appearance.material import material_coordinates
from experiments.experiment_ribbon_c2_native_qualification import write
from experiments.experiment_ribbon_c2_native_qualification_renewal import read_free
from experiments.experiment_ribbon_c2_runtime_capture import required_state
from experiments.experiment_ribbon_contraction.runner import restore
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_locked_solver.coordinates import coordinates_for_face

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "artifacts/verification/resume3229"


def readiness(plan: dict[str, Any]) -> Any:
    """
    Require current source, exact retained ownership and idle diagnostic/gym workers.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    from devtools.ribbon_analysis import end_profile_command
    from experiments.experiment_ribbon_locked_solver import native
    from experiments.experiment_ribbon_spatial_inspection import host

    manifest.verify(manifest.read(manifest.FOLDER / "native-plan.json"))
    for relative, expected in plan["pins"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Read-only material capture source/input drift: {relative}")
    app = adsk.core.Application.get()
    assert os.getpid() == plan["pid"]
    assert app.activeDocument.creationId == plan["document_id"]
    assert app.userInterface.activeCommand == "SelectCommand"
    assert not end_profile_command.pending_state()
    assert len(host.VIEWS) == 1
    view = host.VIEWS[0]
    assert view.process is None
    identity = {
        "component_token": view.component.entityToken,
        "fingerprint": view.ledger.fingerprint,
        "palette": view.palette.id,
    }
    assert identity == {key: plan["view"][key] for key in identity}
    gym = sys.modules.get("experiments.experiment_ribbon_locked_solver.gym")
    for owner in () if gym is None else required_state(gym, "_owners"):
        assert not owner.range_tester.active
        assert not required_state(owner.range_tester.engine, "_polling")
        assert required_state(owner.diagnostics.runner, "_process") is None
    retained = required_state(native, plan["owner_attribute"])
    runtime.check_ownership(retained, plan["ownership"])
    return retained


def point_mm(point: Any) -> Vector3:
    """
    Convert native component-local centimeters once, excluding occurrence display translation.
    """
    return Vector3(point.x * 10, point.y * 10, point.z * 10)


def capture(started: float) -> None:
    """
    Read one actual trimmed point per lateral face and both explicit planar terminal caps.

    One-to-one face provenance is required from the original qualification receipt;
    merged faces need their retained multi-region ownership map and are refused.
    Point samples demonstrate coordinate generation at those samples only, never
    continuous inverse validity, material isometry, branch flow or contact clearance.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    plan = manifest.read(FOLDER / "plan.json")
    guard = memory.Headroom(plan["minimum_system_free_percent"], read_free)
    budget = NativeBudget(
        memory=guard.memory,
        maximum_seconds=plan["review_seconds"],
        maximum_rss_kib=4 * 1024 * 1024,
    )
    budget.started = started
    budget.check("read-only capture readiness")
    owner = readiness(plan)
    compiled = {}
    for name in ("readiness", "point_mm", "capture"):
        body = globals()[name]
        assert runtime.signature(body.__code__) == runtime.signature(
            runtime.compiled_body(Path(__file__), name)
        )
        compiled[name] = "exact_current_compiled_body"
    for function, name in (
        (coordinates_for_face, "coordinates_for_face"),
        (material_coordinates, "material_coordinates"),
        (FoldRoute.physical, "FoldRoute.physical"),
        (FoldRoute.surface, "FoldRoute.surface"),
    ):
        filename = sys.modules[function.__module__].__file__
        assert isinstance(filename, str)
        assert runtime.signature(function.__code__) == runtime.signature(
            runtime.compiled_body(Path(filename), name)
        )
        compiled[name] = "exact_current_compiled_body"
    budget.check("read-only capture launch")
    assert budget.memory() < 3984588
    assert memory.checked_read(read_free) >= plan["minimum_system_free_percent"]
    write(FOLDER / "started.json", {"compiled": compiled, "epoch_seconds": time.time()})
    receipt = manifest.read(ROOT / plan["native_receipt"])
    assert receipt["face_mapping_policy"] == "original one-to-one native patches"
    patches = manifest.read(ROOT / plan["patches"])
    route = restore(manifest.read(ROOT / plan["route"]))
    body = owner.displayed.component.bRepBodies.item(0)
    assert len(patches) + 2 == body.faces.count == plan["ownership"]["faces"]
    samples = []
    caps = []
    # Persist each successful observation, so the first unresolved face is retained
    # with an explicit unattempted tail instead of losing all preceding evidence.
    with (FOLDER / "lateral.jsonl").open("x") as stream:
        for index, patch in enumerate(patches):
            budget.check("native material inverse")
            face = body.faces.item(index)
            point = point_mm(face.pointOnFace)
            record = {"piece_index": patch["piece"], "region": patch["region"]}
            material_u, material_v, thickness = coordinates_for_face(route, record, point)
            q = (2 * material_v - 1) * route.half_width_mm
            rebuilt = route.physical(material_u, q, thickness)
            error = magnitude(difference(rebuilt, point))
            if (
                not all(
                    math.isfinite(value) for value in (material_u, material_v, thickness, error)
                )
                or not 0 <= material_u <= 1
                or not 0 <= material_v <= 1
                or error > 0.01
            ):
                raise RuntimeError(f"Invalid material reconstruction on native face {index}")
            row = {
                "face": index,
                "face_token": face.entityToken,
                "piece": patch["piece"],
                "region": patch["region"],
                "material": [material_u, material_v, thickness],
                "point_mm": [point.x, point.y, point.z],
                "roundtrip_error_mm": error,
            }
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            samples.append(error)
    for index, side in enumerate(("start", "end")):
        budget.check("native authoritative cap plane")
        face = body.faces.item(len(patches) + index)
        plane = adsk.core.Plane.cast(face.geometry)
        if plane is None:
            raise RuntimeError("Registered native cap is not planar")
        fixed = getattr(route.targets, side)
        native_point = adsk.core.Point3D.create(fixed.x / 10, fixed.y / 10, fixed.z / 10)
        ok, uv = face.evaluator.getParameterAtPoint(native_point)
        assert ok and face.evaluator.isParameterOnFace(uv)
        ok, center = face.evaluator.getPointAtParameter(uv)
        assert ok
        ok, outward = face.evaluator.getNormalAtPoint(center)
        assert ok
        inward = unit(Vector3(-outward.x, -outward.y, -outward.z))
        expected_inward = getattr(route.targets, side + "_tangent")
        if side == "end":
            expected_inward = difference(Vector3(0, 0, 0), expected_inward)
        # Retain the qualified0.001degree cap-direction gate: ordered material
        # frames and the downstream inverse depend on the same cap direction.
        direction_error = magnitude(difference(inward, expected_inward))
        if direction_error > 2 * math.sin(math.radians(0.001) / 2):
            raise RuntimeError("Actual cap normal differs from the fixed material frame")
        origin = point_mm(plane.origin)
        width = getattr(route.targets, side + "_width")
        lane_distances = []
        for lane in range(route.targets.lines):
            q = (lane - (route.targets.lines - 1) / 2) * route.targets.diameter_mm
            target = fixed.translated(width, q)
            lane_distances.append(abs(dot(difference(target, origin), inward)))
        center_error = magnitude(difference(point_mm(center), fixed))
        if max(lane_distances) > 0.01 or center_error > 0.01:
            raise RuntimeError("Fixed conductor arrivals differ from the actual cap plane")
        caps.append(
            {
                "side": side,
                "face_index": len(patches) + index,
                "face_token": face.entityToken,
                "plane_origin_mm": [origin.x, origin.y, origin.z],
                "actual_inward_normal": [inward.x, inward.y, inward.z],
                "center_error_mm": center_error,
                "inward_direction_vector_error": direction_error,
                "fixed_lane_plane_distances_mm": lane_distances,
            }
        )
    budget.check("read-only capture completion")
    readiness(plan)
    write(
        FOLDER / "result.json",
        {
            "status": "sampled_native_material_and_cap_capture_complete",
            "lateral_faces_sampled": len(samples),
            "maximum_roundtrip_error_mm": max(samples),
            "caps": caps,
            "wall_seconds": time.perf_counter() - started,
            "rss_kib": budget.memory(),
            "system_free_samples": guard.samples,
            "minimum_system_free_percent": guard.minimum_observed_percent,
            "maximum_checkpoint_rss_kib": max(cast(int, row["rss_kib"]) for row in budget.samples),
            "native_builds": 0,
            "fresh_layouts": 0,
            "full_physical_audits": 0,
            "ownership_unchanged": True,
        },
    )
