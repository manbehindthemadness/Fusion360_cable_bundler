"""
Build distinct Discrete/Split fixtures with actual cable-end sketch lines.

Requires Fusion and no active command. Only the newly created scratch design
is edited. A failed case removes its occurrence; no sweep substitution or
case-specific change to the production snapshot is permitted.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from functools import partial
from pathlib import Path
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from cable_bundler.domain import CableGroupDefinition, CableGroupType, OpenGuideAlignment
from cable_bundler.routing.geometry import Vector3, cross, unit
from cable_bundler.routing.parallel import RoutePreview

from .audits import (
    AuditFailure,
    audit_interference,
    audit_lobe_landmarks,
    audit_sections,
    collect_audits,
)
from .bank import bank_ribbon_frames
from .builder import _build_folded_loft, _build_path
from .cases import Expectation, RibbonStressCase, audit_end_boundary, stress_cases
from .contract import UnsafeRibbon, certify_curvature, discrete_profile_reach
from .exits import RibbonExitEnd, _cap_face, _section_sketch, build_ribbon_exit_loft
from .frames import RibbonFrame, ribbon_frames
from .guides import _guide_fit
from .policy import ExperimentPolicy, exception_chain
from .reporting import compare_outcomes, matrix_fingerprint, maximum_frame_step, summarize
from .shape import solve_ribbon_shape
from .transitions import connection_turn, transition_coverage


def _connection_profile(
    component: adsk.fusion.Component, route: RoutePreview, diameter_mm: float
) -> adsk.fusion.SketchCircle:
    """
    Author explicit round connection geometry normal to the exit's arrival tangent.
    """
    point = route.curves[0].start
    tangent = unit(route.curves[0].derivative(0))
    origin = adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)
    sketch = _section_sketch(
        component, origin, adsk.core.Vector3D.create(tangent.x, tangent.y, tangent.z)
    )
    sketch.name = "Connection geometry " + route.cable_number
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        sketch.modelToSketchSpace(origin), 0.9 * diameter_mm / 20
    )
    if circle is None:
        raise RuntimeError("Fusion could not author the connection profile.")
    return circle


def _audit_connection(
    branch: adsk.fusion.BRepBody, circle: adsk.fusion.SketchCircle
) -> dict[str, object]:
    """
    Require the authored connection rim to lie on the generated exit boundary.

    Eight rim landmarks are a finite correspondence check, not a surface proof.
    """
    geometry = circle.worldGeometry
    center, normal = geometry.center, geometry.normal
    caps: list[adsk.fusion.BRepFace] = []
    for face in branch.faces:
        plane = adsk.core.Plane.cast(face.geometry)
        if plane is None or abs(abs(plane.normal.dotProduct(normal)) - 1) > 1e-7:
            continue
        delta = plane.origin.vectorTo(center)
        if abs(delta.dotProduct(normal)) < 1e-5 and face.isPointOnFace(center, 0.001):
            caps.append(face)
    if len(caps) != 1:
        raise AuditFailure("An exit has no unique planar cap at its connection profile.")
    cap = caps[0]
    axis = (
        unit(cross(Vector3(normal.x, normal.y, normal.z), Vector3(1, 0, 0)))
        if abs(normal.x) < 0.9
        else unit(cross(Vector3(normal.x, normal.y, normal.z), Vector3(0, 1, 0)))
    )
    second = unit(cross(Vector3(normal.x, normal.y, normal.z), axis))
    for index in range(8):
        angle = index * math.pi / 4
        point = adsk.core.Point3D.create(
            center.x + geometry.radius * (axis.x * math.cos(angle) + second.x * math.sin(angle)),
            center.y + geometry.radius * (axis.y * math.cos(angle) + second.y * math.sin(angle)),
            center.z + geometry.radius * (axis.z * math.cos(angle) + second.z * math.sin(angle)),
        )
        if not cap.isPointOnFace(point, 0.001):
            raise AuditFailure("An exit missed its authored connection rim.")
    return {"connection_cap": "matched", "connection_rim_landmarks": 8}


def _guide(
    component: adsk.fusion.Component, frame: RibbonFrame, width_mm: float, name: str
) -> adsk.fusion.SketchLine:
    """
    Author a physical cable-end line in its own perpendicular sketch plane.
    """
    plane_input = component.constructionPlanes.createInput()
    point = frame.origin
    normal = frame.tangent
    plane_input.setByPlane(
        adsk.core.Plane.create(
            adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10),
            adsk.core.Vector3D.create(normal.x, normal.y, normal.z),
        )
    )
    plane = component.constructionPlanes.add(plane_input)
    plane.isLightBulbOn = False
    sketch = component.sketches.add(plane)
    sketch.name = name
    a, b = (point.translated(frame.width, sign * width_mm / 2) for sign in (-1, 1))
    line = sketch.sketchCurves.sketchLines.addByTwoPoints(
        sketch.modelToSketchSpace(adsk.core.Point3D.create(a.x / 10, a.y / 10, a.z / 10)),
        sketch.modelToSketchSpace(adsk.core.Point3D.create(b.x / 10, b.y / 10, b.z / 10)),
    )
    if line is None:
        raise RuntimeError("Fusion could not author a cable-end line.")
    return line


def _case(
    design: adsk.fusion.Design,
    case: RibbonStressCase,
    *,
    policy: ExperimentPolicy = ExperimentPolicy.VALIDATE,
) -> dict[str, object]:
    """
    Exercise both ends; diagnostic observation attempts rejected input and retains output.
    """
    name = case.name
    lines, diameter_mm = case.lines, case.diameter_mm
    stage = "end_boundary"
    started = perf_counter()
    occurrence = design.rootComponent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = name
    row: dict[str, object] = {
        "name": name,
        "family": case.family,
        "lines": lines,
        "diameter_mm": diameter_mm,
        "expectation": case.expectation.value,
        "status": "unexpected_failure",
    }
    coverage = transition_coverage(lines)
    row["transitions"] = coverage
    findings: list[dict[str, str]] = []
    try:
        row["end_boundary"] = audit_end_boundary(case)
        width = lines * diameter_mm
        route = case.route
        stage = "curvature"
        try:
            row["curvature"] = asdict(
                certify_curvature(route, discrete_profile_reach(lines, diameter_mm))
            )
            row["input_curvature_accepted"] = True
        except UnsafeRibbon as error:
            row["input_curvature_accepted"] = False
            row["input_curvature_error"] = str(error)
            if policy is ExperimentPolicy.VALIDATE:
                raise
        if policy is ExperimentPolicy.VALIDATE and case.expectation in (
            Expectation.NONLOCAL_REJECTION,
            Expectation.CURVATURE_REJECTION,
        ):
            stage = "guard_gap"
            raise AuditFailure(
                "The current curvature guard admitted a negative control; no body was constructed."
            )
        stage = "bank"
        frames = bank_ribbon_frames(
            ribbon_frames(route, case.start_width, case.end_width), lines, diameter_mm
        )
        row["maximum_frame_step_degrees"] = maximum_frame_step(frames)
        stage = "guide"
        guides = tuple(
            _guide(component, frame, width * case.guide_width_factor, f"Cable-end {label}")
            for frame, label in ((frames[0], "A"), (frames[-1], "B"))
        )
        case.end_boundary.require_contains(
            tuple(
                Vector3(point.x * 10, point.y * 10, point.z * 10)
                for guide in guides
                for point in (guide.worldGeometry.startPoint, guide.worldGeometry.endPoint)
            )
        )
        fits_planes = tuple(
            _guide_fit(
                design, guide.entityToken, OpenGuideAlignment.CENTER, frame, lines, diameter_mm
            )
            for guide, frame in zip(guides, (frames[0], frames[-1]))
        )
        if policy is ExperimentPolicy.VALIDATE and case.expectation is Expectation.GUIDE_REJECTION:
            stage = "guard_gap"
            raise AuditFailure(
                "An undersized cable-end guide was admitted; no body was constructed."
            )
        stage = "shape"
        shape = solve_ribbon_shape(
            frames, lines, diameter_mm, start_fit=fits_planes[0][0], end_fit=fits_planes[1][0]
        )
        group = CableGroupDefinition(
            uuid4(),
            (uuid4(), uuid4()),
            diameter_mm=diameter_mm,
            group_type=CableGroupType.RIBBON,
            ribbon_lines=lines,
        )
        transform = adsk.core.Matrix3D.create()
        _, path, _ = _build_path(component, route, transform)
        stage = "main_loft"
        loft, sections, _ = _build_folded_loft(
            component, path, shape, group, transform, (fits_planes[0][1], fits_planes[1][1])
        )
        body = loft.bodies.item(0)
        body.name = "Fitted Discrete trunk"
        stage = "main_audit"
        row["shape"] = {
            "folded": shape.folded,
            "length_spread": shape.spread,
            "maximum_pitch_ratio": shape.maximum_pitch_ratio,
        }
        main_results, main_failures = collect_audits(
            {
                "main": partial(audit_sections, body, route, 2 * lines + 2, shape),
                "landmarks": partial(audit_lobe_landmarks, body, sections, lines),
            }
        )
        row.update(main_results)
        findings.extend({"stage": "main_audit", **failure} for failure in main_failures)
        branches: list[dict[str, object]] = []
        branch_bodies: list[adsk.fusion.BRepBody] = []
        stage = "split_exits"
        for end_index, frame in ((0, frames[0]), (-1, frames[-1])):
            fit, plane = fits_planes[0 if end_index == 0 else 1]
            end = RibbonExitEnd(plane, frame, tuple(lane[end_index] for lane in shape.lanes), fit)
            try:
                _cap_face(body, end, transform)
            except RuntimeError as error:
                findings.append({"stage": "split_exits", "error": str(error)})
                for transition in coverage[0:lines] if end_index == 0 else coverage[lines:]:
                    transition.update(status="not_reached", reason=f"cap: {error}")
                continue
            inward = (
                frame.tangent
                if end_index == 0
                else Vector3(-frame.tangent.x, -frame.tangent.y, -frame.tangent.z)
            )
            for lane_index, center in enumerate(fit.centers):
                transition = coverage[lane_index + (0 if end_index == 0 else lines)]
                transition["status"] = "constructing"
                bend = (
                    frame.thickness
                    if end_index == 0
                    else Vector3(-frame.thickness.x, -frame.thickness.y, -frame.thickness.z)
                )
                branch_route = connection_turn(
                    center, inward, bend, 8 * width, f"{name} end {end_index} pin {lane_index + 1}"
                )
                try:
                    certificate = certify_curvature(branch_route, diameter_mm)
                    circle = _connection_profile(component, branch_route, diameter_mm)
                    branch = build_ribbon_exit_loft(
                        component,
                        body,
                        branch_route,
                        end,
                        lane_index,
                        diameter_mm,
                        0.9 * diameter_mm,
                        transform,
                    )
                except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                    transition.update(status="construction_failure", reason=str(error))
                    findings.append({"stage": "split_exits", "error": str(error)})
                    continue
                branch.name = f"End {'A' if end_index == 0 else 'B'} pin {lane_index + 1}"
                branch_bodies.append(branch)
                results, failures = collect_audits(
                    {
                        "sections": partial(audit_sections, branch, branch_route, None),
                        "connection": partial(_audit_connection, branch, circle),
                    }
                )
                result = {"curvature": asdict(certificate), **results}
                branches.append(result)
                transition.update(
                    status="audit_failure" if failures else "audited", findings=failures, **result
                )
                findings.extend({"stage": "split_exits", **failure} for failure in failures)
        stage = "interference"
        try:
            row["interference"] = audit_interference(body, tuple(branch_bodies), diameter_mm)
        except AuditFailure as error:
            findings.append({"stage": stage, "error": str(error)})
        if component.bRepBodies.count != 1 + 2 * lines:
            findings.append(
                {
                    "stage": "split_exits",
                    "error": "The output omitted or duplicated a numbered exit.",
                }
            )
        if findings:
            row["findings"] = findings
            stage = findings[0]["stage"]
            raise AuditFailure(findings[0]["error"])
        row.update(
            status="built_and_audited", branches=branches, solid_count=component.bRepBodies.count
        )
        row["elapsed_seconds"] = perf_counter() - started
        row["retained_solid_count"] = component.bRepBodies.count
        if policy is ExperimentPolicy.OBSERVE and case.expectation is not Expectation.BUILD:
            row["status"] = "built_despite_input_control"
        for sketch in component.sketches:
            sketch.isLightBulbOn = False
        return row
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        for transition in coverage:
            if transition["status"] in ("not_reached", "constructing"):
                transition.update(
                    status="not_reached"
                    if transition["status"] == "not_reached"
                    else "construction_failure",
                    reason=f"{stage}: {error}",
                )
        row["error"] = str(error)
        row["exception_chain"] = exception_chain(error)
        row["stage"] = stage
        row["elapsed_seconds"] = perf_counter() - started
        if stage == "guard_gap":
            row["status"] = "guard_gap"
        elif isinstance(error, UnsafeRibbon) and stage == "curvature":
            row["status"] = (
                "expected_rejection"
                if case.expectation is Expectation.CURVATURE_REJECTION
                else "unexpected_rejection"
            )
        elif (
            stage == "guide"
            and case.expectation is Expectation.GUIDE_REJECTION
            and isinstance(error, ValueError)
            and "too short" in str(error)
        ):
            row["status"] = "expected_rejection"
        elif isinstance(error, AuditFailure):
            row["status"] = "audit_failure"
        if policy is ExperimentPolicy.OBSERVE:
            row["retained_solid_count"] = component.bRepBodies.count
            component.name = f"{row['status']} — {name}"
            for sketch in component.sketches:
                sketch.isLightBulbOn = component.bRepBodies.count == 0
        elif occurrence.isValid and not occurrence.deleteMe():
            raise RuntimeError("Could not remove a failed experiment occurrence.") from error
        return row


def run(_context: object) -> None:
    """
    Leave one final scratch containing only cases that passed all audits.
    """
    app = adsk.core.Application.get()
    if str(app.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before the ribbon stress experiment.")
    for previous in tuple(app.documents):
        if previous.name == "Secure ribbon experiment — Discrete Split":
            if not previous.close(False):
                raise RuntimeError("Could not close the previous experiment scratch.")
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = "Secure ribbon experiment — Discrete Split"
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Fusion did not activate a scratch design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    directory = (
        Path(cable_bundler.__file__).resolve().parents[1]
        / "artifacts"
        / "verification"
        / "secure_discrete_ribbon_bounded"
    )
    directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    matrix = stress_cases()
    fingerprint = matrix_fingerprint(matrix)
    previous_rows: list[dict[str, object]] | None = None
    report_path = directory / "report.json"
    if report_path.exists():
        previous_text = report_path.read_text(encoding="utf-8")
        try:
            previous = json.loads(previous_text)
        except json.JSONDecodeError:
            previous = None
        if (
            isinstance(previous, dict)
            and previous.get("completed") is True
            and previous.get("audit_version") == 4
            and previous.get("matrix_fingerprint") == fingerprint
        ):
            candidates = previous.get("cases")
            if isinstance(candidates, list) and all(
                isinstance(row, dict)
                and isinstance(row.get("name"), str)
                and isinstance(row.get("status"), str)
                for row in candidates
            ):
                previous_rows = candidates
                (directory / "previous_report.json").write_text(previous_text, encoding="utf-8")
    report = {
        "production_modified": False,
        "universal_proof": False,
        "matrix_version": 4,
        "audit_version": 4,
        "matrix_fingerprint": fingerprint,
        "planned_cases": len(matrix),
        "completed": False,
        "cases": rows,
    }
    for case in matrix:
        rows.append(_case(design, case))
        (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        adsk.doEvents()
    report["summary"] = summarize(rows)
    report["repeat_changed_cases"] = (
        compare_outcomes(previous_rows, rows) if previous_rows is not None else None
    )
    selected: dict[tuple[str, str], RibbonStressCase] = {}
    for case, row in zip(matrix, rows):
        selected.setdefault((str(row["status"]), str(row.get("stage", ""))), case)
        if case.lines == 19 and row["status"] not in ("built_and_audited", "expected_rejection"):
            selected.setdefault(("nineteen_lane_failure", ""), case)
    repeat_cases = tuple({case.name: case for case in selected.values()}.values())
    report["repeat_planned_cases"] = [case.name for case in repeat_cases]
    repeat_rows: list[dict[str, object]] = []
    report["repeat_cases"] = repeat_rows
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    repeat_document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        repeat_design = adsk.fusion.Design.cast(app.activeProduct)
        if repeat_design is None:
            raise RuntimeError("Could not activate the isolated repetition scratch.")
        repeat_design.designType = adsk.fusion.DesignTypes.DirectDesignType
        for case in repeat_cases:
            repeat_rows.append(_case(repeat_design, case))
            (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            adsk.doEvents()
    finally:
        if not repeat_document.close(False):
            raise RuntimeError("Could not close the experiment repetition scratch.")
        document.activate()
    repeated_names = {case.name for case in repeat_cases}
    report["within_run_changed_cases"] = compare_outcomes(
        [row for row in rows if row["name"] in repeated_names], repeat_rows
    )
    report["completed"] = True
    report["other_documents"] = [
        {"name": other.name, "modified": other.isModified, "saved": other.isSaved}
        for other in app.documents
        if other != document
    ]
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    app.activeViewport.fit()
    adsk.core.Application.log(
        "SECURE_RIBBON_REPORT=" + json.dumps(report),
        adsk.core.LogLevels.InfoLogLevel,
        adsk.core.LogTypes.FileLogType,
    )
