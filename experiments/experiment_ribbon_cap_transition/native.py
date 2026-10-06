"""
Run one explicitly selected five-width native diagnostic calibration.

Requires Fusion and an idle command. Changes only the owned preview/calibration
documents. No retries, target relocation, fallback or production modification.
Audit failures remain findings, not construction blockers or compliance passes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from functools import partial
from pathlib import Path
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.live import _harness
from experiments.experiment_production_split_ribbon.sources import (
    PROJECT_ROOT,
    load_sources,
    verify_sources,
)
from experiments.experiment_ribbon_diagnosis.observations import PlanePolicy, SectionObserver
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_ribbon_diagnosis.rail_audit import audit_rails
from experiments.experiment_ribbon_diagnosis.storage import archive, archive_and_close
from experiments.experiment_secure_discrete_ribbon.bank import bank_ribbon_frames
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame, ribbon_frames
from experiments.experiment_secure_discrete_ribbon.policy import ExperimentPolicy
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit, RibbonShape

from .accuracy import length_goal
from .fixtures import development_cases, direction_cases
from .native_budget import NativeBudget
from .planning import ShortConnectionFixture, freeze_targets, inspect_candidate
from .screen import _fingerprints
from .solver import solve_candidate

SCRATCH_NAME = "Ribbon 5x both-inward — native calibration"
OUTWARD_SCRATCH_NAME = "Ribbon 5x both-outward — native calibration"
MIXED_SCRATCH_NAME = "Ribbon 5x A-out B-in — native calibration"
REFLECTED_SCRATCH_NAME = "Ribbon 5x A-in B-out — native calibration"
SPATIAL_SCRATCH_NAME = "Ribbon 5x spatial S +45 — native diagnostic"
OWNED_PREVIEW = "Ribbon directions - 4x sphere - layout preview v1"
DIAGNOSTIC_LINEAR_MM = 0.05


def _write(path: Path, value: dict[str, object]) -> None:
    """
    Checkpoint generated evidence without changing historical run directories.
    """
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def run(_context: object) -> None:
    """
    Run the original one-case both-inward calibration, without an automatic retry.
    """
    _run_case(direction_cases()[1], SCRATCH_NAME, OWNED_PREVIEW)


def run_outward(_context: object) -> None:
    """
    Advance one configuration using unchanged solver, construction and audit policies.

    Archive/close only the preceding owned both-inward calibration; retain the
    both-outward result. This entry point does not schedule either mixed case.
    """
    _run_case(direction_cases()[0], OUTWARD_SCRATCH_NAME, SCRATCH_NAME)


def run_mixed(_context: object) -> None:
    """
    Test A-outward/B-inward once without changing the shared solver or audits.

    Archive/close only the owned both-outward result. The reflected mixed
    counterpart is not scheduled by this entry point.
    """
    _run_case(direction_cases()[2], MIXED_SCRATCH_NAME, OUTWARD_SCRATCH_NAME)


def run_reflected(_context: object) -> None:
    """
    Test the reflected A-inward/B-outward configuration once under unchanged rules.

    Archive/close only the preceding owned mixed result. This is an invariance
    check of the same geometric family, not independent generalized coverage.
    """
    _run_case(direction_cases()[3], REFLECTED_SCRATCH_NAME, MIXED_SCRATCH_NAME)


def run_spatial45(_context: object) -> None:
    """
    Attempt the existing spatial +45-degree configuration once, without tuning.

    Length-goal warnings and known end-allocation rejection remain evidence.
    Timing is uncalibrated for this family. Archive only the reflected scratch.
    """
    _run_case(
        development_cases()[5],
        SPATIAL_SCRATCH_NAME,
        REFLECTED_SCRATCH_NAME,
        estimated_seconds=None,
    )


def _run_case(
    case: RibbonStressCase,
    scratch_name: str,
    owned_previous: str,
    *,
    estimated_seconds: float | None = 36.4,
) -> None:
    """
    Build at most one complete configuration and leave its native document open.

    Loose 0.05 mm vertex containment is diagnostic only. Strict existing section,
    landmark, interference, connection and paired-side findings remain recorded.
    Continuous flow/strain and complete native conductor lengths are unmeasured.
    """
    app = adsk.core.Application.get()
    if str(app.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before calibration.")
    if any(document.name in (scratch_name, scratch_name + " v1") for document in app.documents):
        raise RuntimeError("A calibration document already exists; no automatic retry.")
    previous_documents = tuple(
        document
        for document in app.documents
        if document.name in (owned_previous, owned_previous + " v1")
    )
    if len(previous_documents) != 1:
        raise RuntimeError(
            "The authorized preceding scratch is missing or ambiguous; documents retained."
        )
    directory = PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/native" / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    budget = NativeBudget()
    fingerprints = _fingerprints()
    harness_paths = (
        "experiment_secure_discrete_ribbon/live.py",
        "experiment_secure_discrete_ribbon/audits.py",
        "experiment_ribbon_diagnosis/observations.py",
        "experiment_ribbon_diagnosis/rail_audit.py",
    )
    plan = {
        "question": f"Can {case.name} construct as a native trunk and all split endings under the same procedure?",
        "procedure": "cap-transition-v2; fixed centerline, exact caps, 15-degree four-conductor-radius targets; private copied lofts; FRAME planes; no fallback",
        "case": asdict(case),
        "case_id": case.name,
        "estimated_seconds": estimated_seconds,
        "timing_basis": "Spatial family uncalibrated; preceding planar diagnostics took 16–36 seconds."
        if estimated_seconds is None
        else "Previous planar diagnostic calibration.",
        "authorized_previous_document": owned_previous,
        "matrix_sha256": matrix_fingerprint((case,)),
        "candidate_and_rule_sha256": fingerprints,
        "harness_sha256": {
            name: hashlib.sha256((PROJECT_ROOT / "experiments" / name).read_bytes()).hexdigest()
            for name in harness_paths
        },
        "production_sha256": verify_sources(),
        "native_prediction": "unknown; numerical no-violation is not a build prediction",
        "length_policy": "One percent is a nonblocking mechanical goal, separately reported from geometry construction and other rule findings.",
        "limits": {
            "configurations": 1,
            "shape_solves": 1,
            "refinements": 0,
            "native_attempts": 1,
            "schedule_wall_seconds": 120,
            "main_process_rss_kib": budget.maximum_rss_kib,
        },
        "tolerances": {
            "loose_diagnostic_vertex_containment_mm": DIAGNOSTIC_LINEAR_MM,
            "master_rules": "Unchanged; failures retained, never accepted by loose diagnostic checks.",
        },
        "retention": "Archive/close only the authorized preceding owned scratch; retain new calibration scratch and archive. User documents untouched.",
        "scope": "One development calibration; no holdout or generality claim. No fixed wall-time guarantee for an in-flight kernel.",
    }
    # Case identity contains UUID/Enums; retain their stable representations.
    plan["case"] = json.loads(json.dumps(plan["case"], default=str))
    _write(directory / "plan.json", plan)
    report: dict[str, object] = {
        "plan": plan,
        "run_classification": "diagnostic construction run; not production latency or predictive certification",
        "planned": 1,
        "evaluated": 0,
        "native_attempted": 0,
        "built": 0,
        "fully_audited": 0,
        "overall": "unresolved",
        "production_modified": False,
    }
    _write(directory / "report.json", report)
    budget.check("document_setup")
    retention_started = perf_counter()
    archive_and_close(previous_documents[0], directory / "previous-scratch.f3d")
    budget.timings["previous_scratch_archive_close"] = perf_counter() - retention_started
    budget.check("new_scratch")
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = scratch_name
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Fusion did not activate the calibration design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    modules = load_sources()
    harness = _harness(modules)
    harness._build_path = modules["builder"]._build_path
    harness.ribbon_frames = partial(
        ribbon_frames,
        endpoint_tangents=(case.route.curves[0].derivative(0), case.route.curves[-1].derivative(1)),
    )
    harness.bank_ribbon_frames = bank_ribbon_frames
    observer = SectionObserver(modules["builder"], PlanePolicy.FRAME)

    def observe_shape(
        frames: tuple[RibbonFrame, ...],
        line_count: int,
        line_diameter_mm: float,
        *,
        start_fit: RibbonEndFit | None = None,
        end_fit: RibbonEndFit | None = None,
    ) -> RibbonShape:
        """
        Solve once using real Fusion guides and freeze the same branches for build.
        """
        del frames
        if (
            line_count != case.lines
            or line_diameter_mm != case.diameter_mm
            or start_fit is None
            or end_fit is None
        ):
            raise ValueError("Native guides do not match the frozen configuration.")
        turns = freeze_targets(
            case, start_fit, end_fit, fixture=ShortConnectionFixture(case, turn_degrees=15)
        )
        shape = budget.measure("search_shape", solve_candidate)(case, start_fit, end_fit)
        end_plan = EndPlan(case, turns)
        report["preflight"] = budget.measure("numerical_validation", inspect_candidate)(
            shape, end_plan
        )
        if report["preflight"]["failures"]:
            report["overall"] = "failed_known_geometry_rules"
        report["evaluated"] = 1
        harness.connection_turn = end_plan
        _write(directory / "report.json", report)
        return shape

    def build_main(*args: object, **kwargs: object) -> object:
        """
        Count one native attempt only immediately before the actual trunk loft.
        """
        budget.check("native_trunk")
        if _fingerprints() != fingerprints:
            raise RuntimeError("Source drift; native attempt not launched.")
        report["native_attempted"] = 1
        _write(directory / "report.json", report)
        return budget.measure("native_trunk", modules["builder"]._build_folded_loft)(
            *args, **kwargs
        )

    harness.solve_ribbon_shape = observe_shape
    harness._build_folded_loft = build_main
    harness.build_ribbon_exit_loft = budget.measure(
        "native_endings", harness.build_ribbon_exit_loft, native=True
    )
    harness.audit_sections = budget.measure("section_audits", harness.audit_sections)
    harness.audit_lobe_landmarks = budget.measure("landmark_audit", harness.audit_lobe_landmarks)
    harness._audit_connection = budget.measure("connection_audits", harness._audit_connection)
    harness.audit_interference = budget.measure("interference_audit", harness.audit_interference)
    observer.install()
    try:
        report["native_result"] = harness._case(design, case, policy=ExperimentPolicy.OBSERVE)
    finally:
        observer.restore()
    component = design.rootComponent.occurrences.item(0).component
    bodies = tuple(component.bRepBodies)
    trunks = tuple(body for body in bodies if body.name == "Fitted Discrete trunk")
    report["built"] = int(len(bodies) == 1 + 2 * case.lines and len(trunks) == 1)
    if trunks:
        report["native_paired_sides"] = budget.measure("paired_side_audit", audit_rails)(
            trunks[0], observer.records, case.lines
        )
    else:
        report["native_paired_sides"] = {"status": "unmeasured", "reason": "No constructed trunk."}
    paired = report["native_paired_sides"]
    if not isinstance(paired, dict):
        raise TypeError("Native paired-side evidence must be a mapping.")
    paired_spread = paired.get("maximum_relative_spread")
    if paired_spread is not None and not isinstance(paired_spread, (int, float)):
        raise TypeError("Native paired-side spread must be numeric or unmeasured.")
    report["native_mechanical_accuracy"] = {
        "paired_side_length": length_goal(paired_spread),
        "complete_conductor_length": length_goal(None),
        "scope": "Paired seam chains only; legacy paired-side status is a goal diagnostic, not a build gate.",
    }
    report["sections"] = [record.summary() for record in observer.records]
    vertices = tuple(vertex.geometry for body in bodies for vertex in body.vertices)
    if vertices:
        center = case.end_boundary.center
        maximum = max(
            (
                (point.x * 10 - center.x) ** 2
                + (point.y * 10 - center.y) ** 2
                + (point.z * 10 - center.z) ** 2
            )
            ** 0.5
            for point in vertices
        )
        report["loose_diagnostic_sphere"] = {
            "maximum_vertex_radius_mm": maximum,
            "tolerance_mm": DIAGNOSTIC_LINEAR_MM,
            "status": "within_sampled_limit"
            if maximum <= case.end_boundary.diameter_mm / 2 + DIAGNOSTIC_LINEAR_MM
            else "outside",
            "scope": "Native vertices only; not a native skin containment proof.",
        }
    report["unmeasured"] = [
        "native trunk/branch join flow and curvature",
        "connection skin tangency",
        "complete native conductor lengths",
        "continuous final-lane strain/curvature",
        "global clearance and shortest route",
    ]
    display_started = perf_counter()
    for sketch in component.sketches:
        sketch.isLightBulbOn = False
    camera = app.activeViewport.camera
    camera.isFitView = True
    app.activeViewport.camera = camera
    app.activeViewport.refresh()
    report["image_saved"] = app.activeViewport.saveAsImageFile(
        str(directory / "native.png"), 1400, 900
    )
    archive(design, directory / "calibration.f3d")
    budget.timings["display_archive"] = perf_counter() - display_started
    report["timings_seconds"] = budget.timings
    overall_seconds = perf_counter() - budget.started
    report["overall_seconds"] = overall_seconds
    timing_groups = {
        "timed_numerical_prediction_preflight": sum(
            budget.timings.get(stage, 0.0) for stage in ("search_shape", "numerical_validation")
        ),
        "native_construction": sum(
            budget.timings.get(stage, 0.0) for stage in ("native_trunk", "native_endings")
        ),
        "diagnostic_audits": sum(
            budget.timings.get(stage, 0.0)
            for stage in (
                "section_audits",
                "landmark_audit",
                "connection_audits",
                "interference_audit",
                "paired_side_audit",
            )
        ),
    }
    timing_groups["other_overhead"] = overall_seconds - sum(timing_groups.values())
    report["timing_groups_seconds"] = timing_groups
    report["timing_scope"] = (
        "Timed numerical covers only shape solve and candidate inspection, not all fixture/guide "
        "preparation. Other overhead includes uninstrumented setup, display and archiving. "
        "Diagnostic audits are not routine solver time; overall is diagnostic turnaround."
    )
    report["memory_samples"] = budget.samples
    report["final_rss_kib"] = budget.memory()
    report["stop_reason"] = (
        budget.stopped or "Approved single native attempt exhausted; no retry or refinement."
    )
    report["document"] = document.name
    _write(directory / "report.json", report)
    _write(
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/native-latest.json",
        {"directory": str(directory)},
    )
    app.log(f"Ribbon native calibration report: {directory / 'report.json'}")
