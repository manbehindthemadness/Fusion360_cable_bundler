"""
Attempt one frozen three-anchor nonplanar trunk in the existing owned document.
"""

from __future__ import annotations

import hashlib
import json
import math
import traceback
from dataclasses import asdict
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

from .flex_contours import flex_contour, guide_tangent
from .midpoint_native import PARENT
from .native import PROJECT_ROOT, _write
from .native_budget import NativeBudget
from .screen import _fingerprints, verify_sources
from .section_flex import flex_section

DOCUMENT_NAME = "Tube failure - skew return -360 - exact replay - Rate of twist failure v1"


def run(_context: object) -> None:
    """
    Read existing guides; make 30 flexed contours and attempt one full 32-section loft.

    Preserve exact terminal contours, original sections, guides and baseline. Catch
    expected native errors to retain diagnostic evidence, with no retry, endings,
    rerouting, search or production changes. Numerical findings remain diagnostics,
    not whole-structure compliance. Budget checks prevent further launches but do
    not cancel an in-flight Fusion kernel. Presentation/export is a separate call.
    """
    budget = NativeBudget()
    app = adsk.core.Application.get()
    if (
        app.activeDocument.name != DOCUMENT_NAME
        or str(app.userInterface.activeCommand) != "SelectCommand"
    ):
        raise RuntimeError("Expected owned active document and idle Fusion.")
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or design.rootComponent.occurrences.count != 1:
        raise RuntimeError("Owned component structure changed.")
    occurrence = design.rootComponent.occurrences.item(0)
    component = occurrence.component
    if (
        component.bRepBodies.count != 1
        or component.bRepBodies.item(0).name != "Prefix 1-17 - last successful solid"
    ):
        raise RuntimeError("Baseline changed; no build.")
    baseline = component.bRepBodies.item(0)
    baseline_volume = baseline.volume
    existing = [
        sketch.name
        for sketch in component.sketches
        if sketch.name.startswith("Three-anchor flex section")
    ]
    if existing not in ([], ["Three-anchor flex section 02"]):
        raise RuntimeError("Unexpected prototype state; no retry.")
    sections = []
    for number in range(1, 33):
        matches = [
            sketch
            for sketch in component.sketches
            if sketch.name == f"Failed loft input section {number:02}"
        ]
        if (
            len(matches) != 1
            or matches[0].sketchCurves.sketchArcs.count != 42
            or matches[0].profiles.count != 1
        ):
            raise RuntimeError("Frozen source sections changed.")
        sections.append(matches[0])
    guides = []
    for side in ("minus", "plus"):
        matches = [
            sketch
            for sketch in component.sketches
            if sketch.name == f"Outer edge {side} - midpoint fit spline"
        ]
        if len(matches) != 1 or matches[0].sketchCurves.sketchFittedSplines.count != 1:
            raise RuntimeError("Physical guide missing/ambiguous.")
        spline = matches[0].sketchCurves.sketchFittedSplines.item(0)
        if spline.fitPoints.count != 32:
            raise RuntimeError("Guide station count changed.")
        guides.append(spline)
    parent_path = PROJECT_ROOT / PARENT
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if verify_sources() != parent["plan"]["production_sha256"]:
        raise RuntimeError("Production provenance drift.")
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/flex_native" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    source_hashes = {
        name: hashlib.sha256(
            (PROJECT_ROOT / "experiments/experiment_ribbon_cap_transition" / name).read_bytes()
        ).hexdigest()
        for name in ("section_flex.py", "curve_context.py", "flex_contours.py", "flex_native.py")
    }
    plan = {
        "case_id": parent["plan"]["case_id"],
        "parent_report": str(parent_path),
        "parent_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        "fixed_case": parent["plan"]["case"],
        "source_sha256": source_hashes,
        "rule_sha256": _fingerprints(),
        "hypothesis": "Three-anchor local perpendicular section flex may avoid the known planar trunk failure.",
        "native_prediction": "unknown",
        "adapter_revision": "Explicit occurrence proxies and connected collection order; geometry unchanged. Retained section02 reused only after all210 fit points match fixed math within1e-7mm. User-renewed one-attempt pilot; preceding harness exits reached zero loft attempts.",
        "procedure": "Fixed three-anchor Hermite midline + smoothstep unit thickness; 5-point fitted spline per original arc; closed nonplanar Paths; exact original terminal contours; one NewBody loft. No rails attached.",
        "degrees_of_freedom": "None searched; fixed centerline, roll, anchors and targets.",
        "limits": {
            "cases": 1,
            "native_attempts": 1,
            "seconds": 120,
            "rss_kib": 2097152,
            "search": 0,
            "retries": 0,
        },
        "exclusions": "Endings, complete mechanical audits and three collateral configurations not attempted. Native interpolation between samples unmeasured.",
        "future_architecture": "Anchors/edge curves are mathematical solver references, not required Fusion construction objects.",
    }
    report: dict[str, object] = {
        "plan": plan,
        "sections": [],
        "planned": 1,
        "evaluated": 0,
        "native_attempted": 0,
        "trunk_built": 0,
        "complete_ribbons_built": 0,
        "fully_audited": 0,
        "status": "not_attempted",
        "baseline_volume_cm3": baseline_volume,
    }
    _write(directory / "plan.json", plan)
    _write(directory / "report.json", report)
    try:
        started = perf_counter()
        paths = []
        observations = []
        for index, record in enumerate(parent["sections"]):
            budget.check(f"flex_section_{index + 1}")
            report["stage"] = f"section_{index + 1}_guide_and_math"
            data = record["frame"]
            frame = RibbonFrame(
                **{
                    name: Vector3(**data[name])
                    for name in ("origin", "tangent", "width", "thickness")
                }
            )
            tangents = tuple(guide_tangent(guide, index) for guide in guides)
            flex = flex_section(frame, tangents[0], tangents[1], terminal=index in (0, 31))
            for guide, anchor in zip(guides, (flex.minus, flex.plus)):
                point = guide.fitPoints.item(index).worldGeometry
                if (
                    magnitude(
                        difference(
                            Vector3(point.x * 10, point.y * 10, point.z * 10), anchor.position
                        )
                    )
                    > 1e-7
                ):
                    raise RuntimeError("Physical guide anchor moved from frozen frame.")
            report["stage"] = f"section_{index + 1}_contour_path"
            _write(directory / "report.json", report)
            sketch, path, observation = flex_contour(
                component, sections[index], frame, flex, index + 1, occurrence
            )
            sketch.isLightBulbOn = index not in (0, 31)
            sketch.areProfilesShown = False
            observation["anchor_frames"] = asdict(flex)
            observation["guide_tangents"] = [asdict(tangent) for tangent in tangents]
            observations.append(observation)
            paths.append(path)
            report["sections"] = observations
            _write(directory / "report.json", report)
        budget.timings["guide_read_math_and_contour_build"] = perf_counter() - started
        report["evaluated"] = 1
        report["stage"] = "loft_input"
        budget.check("full_trunk")
        if _fingerprints() != plan["rule_sha256"]:
            raise RuntimeError("Rule/source drift; no native launch.")
        loft_input = component.features.loftFeatures.createInput(
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        if loft_input is None:
            raise RuntimeError("Loft input unavailable.")
        for path in paths:
            if loft_input.loftSections.add(path) is None:
                raise RuntimeError("Nonplanar section not accepted by loft input.")
        loft_input.isSolid = True
        report["native_attempted"] = 1
        report["stage"] = "native_trunk"
        _write(directory / "report.json", report)
        started = perf_counter()
        try:
            loft = component.features.loftFeatures.add(loft_input)
        finally:
            budget.timings["native_trunk"] = perf_counter() - started
        if loft is None or loft.bodies.count != 1:
            raise RuntimeError("Loft did not produce one body.")
        body = loft.bodies.item(0)
        if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
            raise RuntimeError("Invalid resulting solid.")
        body.name = "Full trunk - three-anchor section flex"
        body.isLightBulbOn = True
        report["trunk_built"] = 1
        report["status"] = "trunk_built_compliance_unmeasured"
        for sketch in component.sketches:
            if sketch.name.startswith("Three-anchor flex section"):
                sketch.isLightBulbOn = False
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        report["status"] = "diagnostic_failure"
        report["error"] = str(error)
        report["error_type"] = type(error).__name__
        report["traceback"] = traceback.format_exc()
    baseline.isLightBulbOn = True
    report["baseline_unchanged"] = baseline.volume == baseline_volume
    report["timings_seconds"] = budget.timings
    report["memory_samples"] = budget.samples
    report["elapsed_seconds"] = perf_counter() - budget.started
    report["final_rss_kib"] = budget.memory()
    _write(directory / "report.json", report)
    _write(
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/flex-latest.json",
        {"directory": str(directory)},
    )
    app.log(f"Three-anchor section flex: {directory}")
