"""
Rebuild the frozen open failure once with explicit outer contour midpoint vertices.
"""

from __future__ import annotations

import hashlib
import json
import math
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ribbon_diagnosis.storage import archive

from .native import PROJECT_ROOT, _write
from .native_budget import NativeBudget
from .screen import _fingerprints, verify_sources
from .section_midpoints import split_outer_edge_midpoints

DOCUMENT_NAME = "Tube failure - skew return -360 - exact replay"
PARENT = "artifacts/verification/ribbon_cap_transition/native/be41e5d8f52e4cf5ba4fb773545dee3f/report.json"


def run(_context: object, *, document_name: str = DOCUMENT_NAME) -> None:
    """
    Add two contour vertices to all 32 existing profiles and attempt one full trunk.

    Require the owned replay and unchanged 19x1.5mm inputs. No solver/search,
    warping, retries, endings or production changes. Preserve the prior partial
    body, and catch expected kernel errors so Fusion commits diagnostic evidence.
    Archive/presentation failures are recorded without rolling back construction.
    An explicitly supplied name accommodates a user-saved/renamed replay without
    guessing which other open document to modify.
    """
    budget = NativeBudget()
    app = adsk.core.Application.get()
    documents = [document for document in app.documents if document.name == document_name]
    if len(documents) != 1 or str(app.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Owned replay missing/ambiguous or a Fusion command is active.")
    documents[0].activate()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or design.rootComponent.occurrences.count != 1:
        raise RuntimeError("Owned replay design/component changed.")
    component = design.rootComponent.occurrences.item(0).component
    prior_bodies = tuple(component.bRepBodies)
    if len(prior_bodies) != 1 or prior_bodies[0].name != "Prefix 1-17 - last successful solid":
        raise RuntimeError("Expected the single retained 1-17 baseline solid.")
    parent_path = PROJECT_ROOT / PARENT
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if (
        parent["plan"]["case"]["lines"] != 19
        or verify_sources() != parent["plan"]["production_sha256"]
    ):
        raise RuntimeError("Material/production provenance drift; no build.")
    sections = []
    for index in range(1, 33):
        matches = [
            sketch
            for sketch in component.sketches
            if sketch.name == f"Failed loft input section {index:02}"
        ]
        if len(matches) != 1 or matches[0].profiles.count != 1:
            raise RuntimeError(f"Original section {index} missing/ambiguous/invalid.")
        if matches[0].sketchCurves.sketchArcs.count != 40:
            raise RuntimeError(f"Section {index} is not original topology; no retry.")
        sections.append(matches[0])
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/midpoint_native" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    fingerprints = _fingerprints()
    plan = {
        "case_id": parent["plan"]["case_id"],
        "authorized_document": document_name,
        "fixed_case": parent["plan"]["case"],
        "parent_report": str(parent_path),
        "parent_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        "source_and_rule_sha256": fingerprints,
        "production_sha256": verify_sources(),
        "hypothesis": "Explicit side-cap midpoint vertices may improve loft correspondence; outcome unknown.",
        "procedure": "Split original circular side caps; one unchanged full 32-section NewBody solid loft. No rails, warping, target movement or solver changes.",
        "limits": {
            "cases": 1,
            "native_attempts": 1,
            "seconds": 120,
            "rss_kib": 2097152,
            "solves": 0,
            "search": 0,
            "refinements": 0,
        },
        "scope": "One development topology diagnostic, not collateral regression or full-ribbon validation. Endings and post-build compliance audits not attempted.",
        "retention": "Retain current owned document, baseline body and diagnostic evidence; unrelated documents untouched.",
    }
    report: dict[str, object] = {
        "plan": plan,
        "midpoints": [],
        "native_attempted": 0,
        "trunk_built": 0,
        "complete_ribbons_built": 0,
        "fully_audited": 0,
        "numerically_reevaluated": 0,
        "timings_seconds": {},
        "status": "not_attempted",
        "production_modified": False,
    }
    _write(directory / "plan.json", plan)
    _write(directory / "report.json", report)
    try:
        started = perf_counter()
        midpoints = []
        for index, section in enumerate(sections, 1):
            budget.check(f"midpoints_section_{index}")
            midpoints.append(
                {"section": index, "world_mm": split_outer_edge_midpoints(section, 19)}
            )
            report["midpoints"] = midpoints
            _write(directory / "report.json", report)
        budget.timings["section_topology"] = perf_counter() - started
        budget.check("full_trunk")
        if _fingerprints() != fingerprints:
            raise RuntimeError("Source drift; no loft attempt.")
        loft_input = component.features.loftFeatures.createInput(
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        if loft_input is None:
            raise RuntimeError("Loft input unavailable.")
        for section in sections:
            loft_input.loftSections.add(section.profiles.item(0))
        loft_input.isSolid = True
        report["native_attempted"] = 1
        _write(directory / "report.json", report)
        started = perf_counter()
        try:
            loft = component.features.loftFeatures.add(loft_input)
        finally:
            budget.timings["native_trunk"] = perf_counter() - started
        if loft is None or loft.bodies.count != 1:
            raise RuntimeError("Full trunk did not produce one body.")
        body = loft.bodies.item(0)
        if body is None or not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
            raise RuntimeError("Invalid full trunk solid.")
        body.name = "Full trunk - explicit outer midpoint vertices"
        body.isLightBulbOn = True
        prior_bodies[0].isLightBulbOn = False
        report["trunk_built"] = 1
        report["status"] = "trunk_built_compliance_unmeasured"
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        report["status"] = "diagnostic_failure"
        report["error"] = str(error)
        report["error_type"] = type(error).__name__
    report["timings_seconds"] = budget.timings
    report["memory_samples"] = budget.samples
    report["elapsed_seconds"] = perf_counter() - budget.started
    _write(directory / "report.json", report)
    try:
        budget.check("presentation")
        for section in sections:
            section.isLightBulbOn = report["trunk_built"] == 0
            section.areProfilesShown = False
        app.activeViewport.fit()
        app.activeViewport.refresh()
        archive(design, directory / "midpoint-result.f3d")
        report["image_saved"] = app.activeViewport.saveAsImageFile(
            str(directory / "midpoint-result.png"), 1800, 1100
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        report["presentation_error"] = str(error)
    report["final_rss_kib"] = budget.memory()
    report["elapsed_seconds"] = perf_counter() - budget.started
    report["document"] = app.activeDocument.name
    _write(directory / "report.json", report)
    _write(
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/midpoint-latest.json",
        {"directory": str(directory)},
    )
    app.log(f"Outer-edge midpoint diagnostic: {directory}")
