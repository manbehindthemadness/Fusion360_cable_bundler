"""
Inspect the retained414seam failure without solving, rebuilding or changing fidelity policy.

Requires the local Fusion MCP session, its owned idle gym document and unchanged
retained native revision. Writes frozen evidence under ignored verification output;
changes only diagnostic visibility, display translation, references and graphics.
"""

import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any


def digest(path: Path) -> str:
    """
    Pin immutable source and native evidence bytes without changing them.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_mm(point: Any) -> dict[str, float]:
    """
    Freeze native point coordinates in the same millimeters as the material plan.
    """
    return {axis: float(getattr(point, axis)) * 10 for axis in "xyz"}


def native_point(point: Any) -> Any:
    """
    Translate a fixed planned corner into Fusion's centimeter coordinate frame.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    return adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)


def aligned(actual: list[Any], expected: list[Any]) -> tuple[list[Any], list[float]]:
    """
    Preserve endpoint-pair correspondence using minimum maximum-distance matching.
    """
    selected = min(
        (actual, list(reversed(actual))),
        key=lambda pair: max(a.distanceTo(b) for a, b in zip(pair, expected)),
    )
    return selected, [a.distanceTo(b) * 10 for a, b in zip(selected, expected)]


def run(context: object) -> None:
    """
    Compare planned corners, native curve endpoints and shared BRep vertices on22retained seams.
    """
    del context
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    from cable_bundler.routing.geometry import Vector3
    from devtools.ribbon_analysis.budget import NativeBudget
    from devtools.ribbon_analysis.end_profiles import retain_end_profiles
    from devtools.ribbon_analysis.graphics import draw_lines, draw_text
    from devtools.ribbon_analysis.inspection.native_guides import retain
    from experiments.experiment_optional_appearance.host import capture
    from experiments.experiment_ribbon_contraction.runner import restore
    from experiments.experiment_ribbon_fold_route.material_profile import material_profile
    from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches
    from experiments.experiment_ribbon_locked_solver.inspection import freeze
    from experiments.experiment_ribbon_locked_solver.lock import ROOT, verify

    app = adsk.core.Application.get()
    job = ROOT / "artifacts/verification/ribbon_snap413/native/zero-snap413-new-excursion"
    native_path, route_path = job / "native-result.json", job / "route.json"
    native = json.loads(native_path.read_text())
    document_id = "86e5d125-ed43-4b89-b175-dcca0966fae6"
    if (
        app.activeDocument.creationId != document_id
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("416requires the owned idle gym document")
    design = adsk.fusion.Design.cast(app.activeProduct)
    matches = [
        o for o in design.rootComponent.occurrences if o.component.name == native["component"]
    ]
    if len(matches) != 1 or matches[0].component.bRepBodies.count != 1:
        raise RuntimeError("416requires the exact retained failed occurrence")
    occurrence = matches[0]
    body = occurrence.component.bRepBodies.item(0)
    if body.revisionId != native["revision"] or body.faces.count != 142:
        raise RuntimeError("416native revision/topology differs from the preserved failure")
    out = ROOT / "artifacts/verification/ribbon_seam418"
    out.mkdir(exist_ok=False)
    pins = verify()
    input_hashes = {str(p.relative_to(ROOT)): digest(p) for p in (route_path, native_path)}
    plan = {
        "question": "Do414seam flags represent displaced boundary curves or native vertex-position discrepancies, and where are they?",
        "sources": pins,
        "inputs": input_hashes,
        "revision": native["revision"],
        "script_sha256": digest(ROOT / "experiments/experiment_ribbon_zero_snap/inspect_native.py"),
        "renewal_from": "416setup stopped before measurements: MCP does not define __file__. Earlier future-import wrapper rejection also preserved. No solver/native construction or geometry retry.",
        "renewal417": "Partial read-only records retained after an invalid display-sampling parameter. Use exact cached endpoint evaluations and clamped interior parameters; same22edges and60s scope, no body changes/builds.",
        "scope": "One retained failed gym configuration:20recorded failed shared edges plus two passing controls. Re-evaluate exact planned seam corners, BRep vertices and bounded curve evaluator endpoints. Display unchanged body with red failed seam locations and green controls; retain hidden original guides/cap profiles. No solver, new native body, policy/tolerance or appearance change. Display translation only to x980cm.",
        "limits": {
            "seconds": 60,
            "rss_kib": 4194304,
            "launch_rss_kib": 3984588,
            "seam_records": 22,
            "draw_samples_per_edge": 33,
            "solves": 0,
            "native_attempts": 0,
        },
        "stop": "First source/input/revision/API/resource mismatch. Preserve partial records, no automatic retry.",
    }
    (out / "plan.json").write_text(json.dumps(plan, indent=2))
    budget = NativeBudget(maximum_seconds=60, maximum_rss_kib=4194304)
    if budget.memory() >= 3984588:
        raise RuntimeError("416launch headroom")
    started = perf_counter()
    report: dict[str, Any] = {"status": "running", "records": [], "solves": 0, "native_attempts": 0}

    try:
        route = restore(json.loads(route_path.read_text()))
        profile = material_profile(route.targets.lines, route.targets.diameter_mm)
        patches = material_patches(route.pieces, profile)
        failed = {tuple(r["faces"]): r for r in native["audit"]["seam_failures"]}
        candidates = []
        controls = 0
        for index, patch in enumerate(patches):
            neighbor = index - index % len(profile) + (index + 1) % len(profile)
            pairs = [(neighbor, patch.rows[0][-1], patch.rows[-1][-1])]
            if index >= len(profile):
                pairs.append((index - len(profile), patch.rows[0][0], patch.rows[0][-1]))
            for neighbor, start, end in pairs:
                key = (index, neighbor)
                if key in failed or (controls < 2 and key not in failed and start != end):
                    candidates.append((key, start, end, key in failed))
                    controls += int(key not in failed)
        if len(candidates) != 22:
            raise RuntimeError(
                "416requires all20failed records and exactly two noncollapsed controls"
            )
        curves: dict[int, tuple[Any, list[Any], bool]] = {}
        for (index, neighbor), start, end, is_failure in candidates:
            budget.check("416shared edge measurement")
            face = body.faces.item(index)
            neighbor_edges = {e.tempId for e in body.faces.item(neighbor).edges}
            edges = [e for e in face.edges if e.tempId in neighbor_edges]
            if len(edges) != 1:
                raise RuntimeError("416retained record no longer has exactly one shared edge")
            edge = edges[0]
            expected = [native_point(start), native_point(end)]
            vertices, vertex_errors = aligned(
                [edge.startVertex.geometry, edge.endVertex.geometry], expected
            )
            ids = [edge.startVertex.tempId, edge.endVertex.tempId]
            if vertices[0].distanceTo(edge.startVertex.geometry) > vertices[0].distanceTo(
                edge.endVertex.geometry
            ):
                ids.reverse()
            ok, low, high = edge.evaluator.getParameterExtents()
            if not ok:
                raise RuntimeError("416bounded native edge evaluator unavailable")
            ok_low, a = edge.evaluator.getPointAtParameter(low)
            ok_high, b = edge.evaluator.getPointAtParameter(high)
            if not ok_low or not ok_high:
                raise RuntimeError("416native curve endpoint evaluation failed")
            endpoints, curve_errors = aligned([a, b], expected)
            record = {
                "faces": [index, neighbor],
                "failed414": is_failure,
                "edge_id": edge.tempId,
                "piece": patches[index].piece_index,
                "region": patches[index].region,
                "profile": patches[index].profile.label,
                "vertex_ids": ids,
                "planned_mm": [point_mm(p) for p in expected],
                "vertices_mm": [point_mm(p) for p in vertices],
                "curve_endpoints_mm": [point_mm(p) for p in endpoints],
                "vertex_errors_mm": vertex_errors,
                "curve_errors_mm": curve_errors,
                "curve_to_vertex_mm": [a.distanceTo(b) * 10 for a, b in zip(endpoints, vertices)],
                "recorded414_error_mm": failed.get((index, neighbor), {}).get("endpoint_error_mm"),
            }
            report["records"].append(record)
            with (out / "measurements.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")
            points = [a]
            for i in range(1, 32):
                parameter = min(high, max(low, low + (high - low) * i / 32))
                ok, point = edge.evaluator.getPointAtParameter(parameter)
                if not ok:
                    raise RuntimeError("416edge display sampling failed")
                points.append(point)
            points.append(b)
            curves[edge.tempId] = (edge, points, is_failure)
        retain(
            occurrence.component,
            freeze(route, "seam-failure416"),
            lambda: budget.check("416original material guides"),
        )
        retain_end_profiles(
            occurrence.component, route.targets, lambda: budget.check("416fixed cap profiles")
        )
        group = occurrence.component.customGraphicsGroups.add()
        group.name = "FAILED414 seam inspection416 - red failures, green controls"
        for edge_id, (_, points, is_failure) in curves.items():
            draw_lines(
                group,
                tuple(Vector3(p.x * 10, p.y * 10, p.z * 10) for p in points),
                (230, 35, 25) if is_failure else (20, 160, 70),
                f"{'FAILED' if is_failure else 'CONTROL'} native seam {edge_id}",
            )
        box = body.boundingBox
        label = Vector3(box.minPoint.x * 10, box.minPoint.y * 10, box.maxPoint.z * 10 + 2)
        draw_text(group, "FAILED seam fidelity: 20 / 270", label, (180, 25, 20), 1.1)
        draw_text(
            group,
            "Red: flagged seams   Green: controls",
            label.translated(Vector3(0, 0, 1), 1.5),
            (50, 50, 50),
            1.0,
        )
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(980, 0, 0)
        occurrence.transform2 = transform
        occurrence.isLightBulbOn = True
        body.isLightBulbOn = True
        if (
            body.revisionId != native["revision"]
            or verify() != pins
            or any(digest(ROOT / p) != h for p, h in input_hashes.items())
        ):
            raise RuntimeError("416body/source/input changed during inspection")
        budget.check("416capture")
        capture(app, occurrence, out / "overview.png")
        failures = [r for r in report["records"] if r["failed414"]]
        report.update(
            status="completed",
            revision_unchanged=True,
            measured_failed_seams=len(failures),
            measured_controls=2,
            unique_failed_edges=len({r["edge_id"] for r in failures}),
            unique_flagged_vertex_ids=len(
                {
                    i
                    for r in failures
                    for i, e in zip(r["vertex_ids"], r["vertex_errors_mm"])
                    if e > 1e-6
                }
            ),
            maximum_vertex_error_mm=max(max(r["vertex_errors_mm"]) for r in failures),
            maximum_curve_error_mm=max(max(r["curve_errors_mm"]) for r in failures),
            maximum_curve_to_vertex_mm=max(max(r["curve_to_vertex_mm"]) for r in failures),
            point_tolerance_mm=app.pointTolerance * 10,
        )
    except (
        ArithmeticError,
        KeyError,
        OSError,
        RuntimeError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as error:
        report.update(status="stopped", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report.update(
            seconds=perf_counter() - started,
            maximum_rss_kib=max(
                (
                    value
                    for sample in budget.samples
                    if isinstance(value := sample.get("rss_kib"), int)
                ),
                default=None,
            ),
        )
        (out / "result.json").write_text(json.dumps(report, indent=2))
