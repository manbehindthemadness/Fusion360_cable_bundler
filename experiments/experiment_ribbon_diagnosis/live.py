"""
Run observed copied lofts and a single-variable plane comparison in a scratch.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from functools import partial
from pathlib import Path
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing import RibbonEndFit, RibbonFrame, RibbonShape
from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_production_split_ribbon.live import _harness
from experiments.experiment_production_split_ribbon.sources import (
    PROJECT_ROOT,
    load_sources,
    verify_sources,
)
from experiments.experiment_secure_discrete_ribbon.cases import (
    Expectation,
    RibbonStressCase,
    audit_end_boundary,
    stress_cases,
)
from experiments.experiment_secure_discrete_ribbon.policy import ExperimentPolicy
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint, summarize

from .audit_probe import SectionAuditProbe
from .cloth import side_lengths
from .compact import compact_cases, route_evidence
from .end_sections import CappedConnectionTurns
from .inputs import analytic_guide_frame
from .observations import PlanePolicy, SectionObserver, angle_degrees
from .preflight import EndPlan
from .rail_audit import audit_rails
from .spatial import spatial_cases, spatial_evidence
from .storage import archive, archive_and_close

SCRATCH_NAME = "Ribbon failure diagnosis"
REPORT_DIRECTORY = PROJECT_ROOT / "artifacts/verification/ribbon_failure_diagnosis"


class GuidePolicy(Enum):
    """
    Distinguish historical fixture planes from independently authored exact cap normals.
    """

    SAMPLED = "historical_sampled_tangents"
    EXACT = "exact_cubic_end_tangents"


def _case(
    design: adsk.fusion.Design,
    case: RibbonStressCase,
    plane_policy: PlanePolicy,
    guide_policy: GuidePolicy = GuidePolicy.SAMPLED,
    section_count: int = 32,
    preflight_path: Path | None = None,
) -> dict[str, object]:
    """
    Attempt input controls, retain all output, and observe the copied fitted loft.
    """
    modules = load_sources()
    harness = _harness(modules)
    harness._build_path = modules["builder"]._build_path
    harness._build_folded_loft = modules["builder"]._build_folded_loft
    harness.ribbon_frames = partial(modules["frames"].ribbon_frames, maximum_sections=section_count)
    spatial = case.family.startswith(("spatial_oblique", "spatial_s_twist"))
    constrained = spatial or case.family.startswith("compact_")
    if spatial:
        harness.audit_end_boundary = partial(audit_end_boundary, diameter_widths=4.0)
    end_sections = CappedConnectionTurns(case, turn_degrees=15 if spatial else 90)
    end_plan = EndPlan(case, end_sections) if spatial else None
    preflight: dict[str, object] = {}
    if constrained:
        harness.connection_turn = end_plan if end_plan is not None else end_sections
    original_guide = harness._guide

    def author_guide(
        component: adsk.fusion.Component, frame: RibbonFrame, width_mm: float, name: str
    ) -> adsk.fusion.SketchLine:
        """
        Author exact analytic caps only in the explicitly labeled fixture comparison.
        """
        if guide_policy is GuidePolicy.EXACT:
            frame = analytic_guide_frame(case, name == "Cable-end A")
        return original_guide(component, frame, width_mm, name)

    harness._guide = author_guide
    observer = SectionObserver(modules["builder"], plane_policy)
    probe = SectionAuditProbe(harness.audit_sections)
    harness.audit_sections = probe
    original_shape = harness.solve_ribbon_shape
    shapes: list[RibbonShape] = []

    def observe_shape(
        frames: tuple[RibbonFrame, ...],
        line_count: int,
        line_diameter_mm: float,
        *,
        start_fit: RibbonEndFit | None = None,
        end_fit: RibbonEndFit | None = None,
    ) -> RibbonShape:
        """
        Retain the returned shape without changing solver arguments or result.
        """
        shape = original_shape(
            frames, line_count, line_diameter_mm, start_fit=start_fit, end_fit=end_fit
        )
        shapes.append(shape)
        if end_plan is not None:
            preflight.update(end_plan.inspect(shape))
            if preflight_path is not None:
                _checkpoint(preflight_path, preflight)
        return shape

    harness.solve_ribbon_shape = observe_shape
    before = design.rootComponent.occurrences.count
    observer.install()
    try:
        row = harness._case(design, case, policy=ExperimentPolicy.OBSERVE)
    finally:
        observer.restore()
    occurrence = design.rootComponent.occurrences.item(before)
    component = occurrence.component
    component.name = f"{plane_policy.value} | {guide_policy.value} | n{section_count} | {row['status']} | {case.name}"
    row["plane_policy"] = plane_policy.value
    row["guide_policy"] = guide_policy.value
    row["section_count"] = section_count
    row["input_expectation"] = case.expectation.value
    if end_plan is not None:
        row["preflight"] = preflight
        row["observed_construction_status"] = row["status"]
    if constrained:
        row["end_section_length_policy"] = {
            "maximum_fraction_per_end": 0.06,
            "reference": "Central trunk route arc length, excluding both split-end regions.",
            "scope": "Every authored connection-to-cap lane; native skin length not certified.",
            "observations": end_sections.observations,
        }
    row["fitted_body_constructed"] = any(
        body.name == "Fitted Discrete trunk" for body in component.bRepBodies
    )
    row["section_observations"] = [record.summary() for record in observer.records]
    row["audit_witnesses"] = probe.findings
    row["max_section_off_plane_mm"] = max(
        (record.maximum_off_plane_mm for record in observer.records), default=0.0
    )
    row["max_section_normal_error_degrees"] = max(
        (record.normal_error_degrees for record in observer.records), default=0.0
    )
    if shapes:
        shape = shapes[0]
        frames = shape.frames
        row["frame_diagnostics"] = {
            "count": len(frames),
            "start_tangent_error_degrees": angle_degrees(
                frames[0].tangent, case.route.curves[0].derivative(0)
            ),
            "end_tangent_error_degrees": angle_degrees(
                frames[-1].tangent, case.route.curves[-1].derivative(1)
            ),
            "first_span_mm": magnitude(difference(frames[1].origin, frames[0].origin)),
            "end_lead_mm": shape.end_lead_mm,
            "minimum_end_radius_mm": shape.minimum_end_radius_mm,
            "frames": [asdict(frame) for frame in frames],
        }
        if constrained:
            row["lane_length_constraint"] = {
                "limit": 0.01,
                "spread": shape.spread,
                "passed": shape.meets_length_target,
            }
            if not shape.meets_length_target:
                row.update(status="audit_failure", error="Sampled lane length spread exceeds 1%.")
    if constrained:
        row["route_length_evidence"] = spatial_evidence(case) if spatial else route_evidence(case)
        row["new_rules_certified"] = False
        if row["fitted_body_constructed"]:
            body = next(
                body for body in component.bRepBodies if body.name == "Fitted Discrete trunk"
            )
            try:
                row["native_side_lengths"] = (
                    audit_rails(body, observer.records, case.lines)
                    if spatial
                    else side_lengths(body, case)
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                row["native_side_lengths"] = {"status": "unmeasured", "error": str(error)}
            if row["native_side_lengths"]["status"] != "passed":
                row.update(
                    status="audit_failure",
                    error="Native side-length constraint failed or could not be measured.",
                )
        if row["status"] == "built_and_audited":
            row["status"] = "audited_with_unresolved_optimality_gap"
        if row.get("input_curvature_accepted") is False:
            row["status"] = "audit_failure"
            row["input_rule_failure"] = (
                "Input curvature rejected; constructed geometry cannot be a rule-compliant pass."
            )
    if not row["fitted_body_constructed"] and observer.records:
        try:
            row["retained_section_evidence"] = observer.retain_profiles(component)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            row["section_evidence_error"] = str(error)
    if end_plan is not None:
        row["status"] = (
            "preflight_rejected_diagnostic"
            if preflight.get("verdict") == "reject"
            else "preflight_unresolved_diagnostic"
        )
    return row


def _checkpoint(path: Path, report: dict[str, object]) -> None:
    """
    Preserve every completed observation before progressing to the next case.
    """
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def run(_context: object, mode: str = "baseline", case_index: int = 0) -> None:
    """
    Execute exactly one indexed observation and archive it before returning.

    Native profiles and rejected controls are attempted only in this explicit
    diagnostic mode. Constructed solids are not automatically rule-valid.
    """
    if mode not in ("smoke", "baseline", "planes", "caps", "dense", "compact", "spatial"):
        raise ValueError("Unknown diagnosis mode.")
    app = adsk.core.Application.get()
    if str(app.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before diagnosis.")
    hashes = verify_sources()
    matrix = (
        spatial_cases()
        if mode == "spatial"
        else compact_cases()
        if mode == "compact"
        else stress_cases()
    )
    if mode == "smoke":
        selected = tuple(
            case for case in matrix if case.name in ("straight_3x1", "straight_19x0.5")
        )
    elif mode in ("caps", "dense"):
        selected = tuple(
            case
            for case in matrix
            if case.name in ("straight_3x1", "near_return_3x1", "straight_19x0.5")
        )
    elif mode == "planes":
        selected = tuple(case for case in matrix if case.expectation is Expectation.BUILD)
    else:
        selected = matrix
    policies = (
        (PlanePolicy.PATH, PlanePolicy.FRAME)
        if mode == "smoke"
        else (PlanePolicy.PATH if mode == "baseline" else PlanePolicy.FRAME,)
    )
    plan = tuple((policy, case) for policy in policies for case in selected)
    if not 0 <= case_index < len(plan):
        raise ValueError(f"Case index must be between 0 and {len(plan) - 1}.")
    directory = REPORT_DIRECTORY / f"{mode}-{case_index:02d}-{uuid4().hex}"
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "report.json"
    for index, previous in enumerate(tuple(app.documents)):
        if previous.name == SCRATCH_NAME:
            owned = adsk.fusion.FusionDocument.cast(previous)
            if owned is None:
                raise RuntimeError("Could not identify the previous diagnostic design.")
            archive_and_close(owned, directory / f"previous-{index}.f3d")
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = SCRATCH_NAME
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Fusion did not activate the diagnostic design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    rows: list[dict[str, object]] = []
    report: dict[str, object] = {
        "completed": False,
        "completion_scope": "one case, not the full matrix",
        "mode": mode,
        "case_index": case_index,
        "planned_case_count": len(plan),
        "next_case_index": case_index + 1 if case_index + 1 < len(plan) else None,
        "production_modified": False,
        "source_sha256": hashes,
        "matrix_fingerprint": matrix_fingerprint(matrix),
        "matrix_version": 8 if mode == "spatial" else 6 if mode == "compact" else 4,
        "audit_version": 10 if mode == "spatial" else 6 if mode == "compact" else 4,
        "entry_point": "Copied fitted loft; no sweep fallback.",
        "known_controls_attempted": mode == "baseline",
        "universal_prediction_proof": False,
        "cases": rows,
    }
    _checkpoint(path, report)
    policy, case = plan[case_index]
    guide_policy = (
        GuidePolicy.EXACT
        if mode in ("caps", "dense", "compact", "spatial")
        else GuidePolicy.SAMPLED
    )
    section_count = 128 if mode == "dense" else 32
    rows.append(
        _case(design, case, policy, guide_policy, section_count, directory / "preflight.json")
    )
    _checkpoint(path, report)
    archive_path = directory / "geometry.f3d"
    archive(design, archive_path)
    report["geometry_archive"] = str(archive_path)
    report["summary"] = summarize(rows)
    report["constructed_trunks"] = sum(row["fitted_body_constructed"] is True for row in rows)
    report["retained_solids"] = sum(
        component.bRepBodies.count for component in design.allComponents
    )
    report["completed"] = True
    _checkpoint(path, report)
    document.activate()
    app.activeViewport.fit()
