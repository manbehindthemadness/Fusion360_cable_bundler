"""
Carry actual failed feature evidence into one coupled incident correction using only unused work.
"""

from __future__ import annotations

from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report
from .feature_guidance import FeatureEvidence, IncidentGuidance, RetainedFeatures
from .fold_recovery import FeatureProjection
from .fold_recovery import recover as recover_fold
from .gate import Gate
from .joint_contact import recover as recover_joints
from .model import Hardware
from .recovery_limits import Work
from .reversal_model import incident_fold
from .straight_quality import StraightQuality


class _ObservedGate:
    """
    Retain actual immutable report/route pairs while delegating every measurement to the original gate.
    """

    def __init__(self, gate: Gate) -> None:
        """
        Bind the existing gate without creating another time, cell or cache allowance.
        """
        self.gate = gate
        self.evidence: list[FeatureEvidence] = []

    @property
    def hardware(self) -> Hardware:
        """
        Return the original fixed hardware lazily without copying its state.
        """
        return self.gate.hardware

    def measure(self, route: FoldRoute, stage: str) -> Report:
        """
        Record only a completed actual measurement, propagating caller failures.
        """
        report = self.gate.measure(route, stage)
        self.evidence.append(FeatureEvidence(route, report))
        return report

    def certify(self, route: FoldRoute, stage: str) -> Report:
        """
        Retain the actual refined candidate report without allocating another check budget.
        """
        report = self.gate.certify(route, stage)
        self.evidence.append(FeatureEvidence(route, report))
        return report


def recover(
    original: FoldRoute,
    evidence: Report,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    quality: StraightQuality | None = None,
    maximum_updates: int = 4,
) -> Result | None:
    """
    Preserve legacy successes and continue only measured feature closure failures.

    Keep all prior reports, then reflect exactly the fold incident to the latest
    intrusion and solve its caps, complete feature members and length together.
    All failed preceding corrections, preparation and certificates debit the same
    original four-update/24-Newton/CPU/wall/pair allocation. No new angle, event,
    radius family or target is tried. Unsupported or exhausted evidence retains
    the original unresolved result. Explicit straight-quality callers stay legacy.
    A reflected action that proves linear infeasibility before any motion may
    yield to the same three measured features without another sign change.
    Both preceding actions debit preparation, updates, contact and clocks before
    that continuation; successful legacy reflection is never displaced.
    A physical no-descent stop may instead continue its actual blocked proposals
    with independent occupied-member inequalities, preserving signs, radii, the
    preceding ceiling and only unused work. No successful result is displaced.
    Retained grouped projection infeasibility may use the same member model with
    its original quality ceiling active from the first correction, after all
    preceding failed work is debited. Existing successful retained actions stay.
    """
    allocation = Work(maximum_updates, remaining_pairs, maximum_cpu_seconds, maximum_seconds)
    cpu, wall = process_time(), perf_counter()
    observed = _ObservedGate(terminal)
    prior = recover_fold(
        original,
        evidence,
        terminal if quality is not None else observed,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        quality=quality,
        maximum_updates=maximum_updates,
    )
    if (
        quality is None
        and prior is not None
        and prior.contact is None
        and prior.detail.get("stop_reason") == "joint_no_descent"
    ):
        blocked = tuple(
            e
            for e in observed.evidence
            if e.report.status == "blocked" and e.report.witness is not None
        )
        left = allocation.remaining(
            updates=prior.detail["iterations"],
            pairs=prior.detail["contact_pairs"],
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - wall,
        )
        if blocked and len(blocked) <= 2 and left is not None:
            latest = blocked[-1]
            record(
                {
                    "stage": "member_feature_handoff",
                    "status": "started",
                    "before": dict(prior.detail),
                    "remaining_updates": left.updates,
                    "remaining_pairs": left.pairs,
                    "feature_reports": len(blocked) + 1,
                }
            )
            child = recover_fold(
                latest.route,
                latest.report,
                terminal,
                checkpoint,
                record,
                maximum_length_mm=prior.detail["maximum_length_mm"],
                minimum_straight_mm=minimum_straight_mm,
                remaining_pairs=left.pairs,
                maximum_cpu_seconds=left.cpu_seconds,
                maximum_seconds=left.wall_seconds,
                maximum_updates=left.updates,
                continuation=RetainedFeatures((FeatureEvidence(original, evidence), *blocked)),
                projection=FeatureProjection.MEMBERS,
            )
            if child is not None:
                return _combined_result(
                    original, prior, child, allocation, cpu, wall, "before_member_inequalities"
                )
    if (
        quality is not None
        or prior is None
        or prior.contact is not None
        or prior.detail.get("stop_reason") != "feature_constraint_limit"
        or not observed.evidence
    ):
        return prior
    latest = observed.evidence[-1]
    if latest.report.status != "blocked" or latest.report.witness is None:
        return prior
    selected = incident_fold(latest.route, latest.report.witness)
    earlier = tuple(e for e in observed.evidence[:-1] if e.report.status == "blocked")
    if selected is None or len(earlier) > 1:
        return prior
    left = allocation.remaining(
        updates=prior.detail["iterations"],
        pairs=prior.detail["contact_pairs"],
        cpu_seconds=process_time() - cpu,
        wall_seconds=perf_counter() - wall,
    )
    if left is None:
        return prior
    guidance = IncidentGuidance(selected, (latest, FeatureEvidence(original, evidence), *earlier))
    record(
        {
            "stage": "coupled_incident_handoff",
            "status": "started",
            "selected_fold": selected,
            "terminal": latest.report.witness.terminal,
            "piece": latest.report.witness.piece,
            "before": dict(prior.detail),
            "remaining_updates": left.updates,
        }
    )
    child = recover_joints(
        latest.route,
        latest.report,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=prior.detail["maximum_length_mm"],
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=left.pairs,
        maximum_cpu_seconds=left.cpu_seconds,
        maximum_seconds=left.wall_seconds,
        maximum_updates=left.updates,
        mode=guidance,
    )
    if child is None:
        return prior
    if (
        child.contact is None
        and child.detail.get("stop_reason") == "linear_projection_infeasible"
        and child.detail["newton_steps"] == 0
        and child.detail["iterations"] == 0
    ):
        remaining = allocation.remaining(
            updates=prior.detail["iterations"] + child.detail["iterations"],
            pairs=prior.detail["contact_pairs"] + child.detail["contact_pairs"],
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - wall,
        )
        if remaining is not None:
            record(
                {
                    "stage": "coupled_retained_handoff",
                    "status": "started",
                    "feature_reports": len(guidance.evidence),
                    "remaining_updates": remaining.updates,
                    "remaining_pairs": remaining.pairs,
                }
            )
            continued = _recover_retained(
                latest,
                RetainedFeatures(guidance.evidence),
                terminal,
                checkpoint,
                record,
                maximum_length_mm=prior.detail["maximum_length_mm"],
                minimum_straight_mm=minimum_straight_mm,
                allocation=remaining,
            )
            if continued is not None:
                continued.detail["before_unmoved_incident"] = dict(child.detail)
                for field in (
                    "iterations",
                    "newton_steps",
                    "contacts",
                    "contact_pairs",
                    "contact_seconds",
                ):
                    continued.detail[field] += child.detail[field]
                child = continued
    return _combined_result(
        original, prior, child, allocation, cpu, wall, "before_coupled_incident"
    )


def _recover_retained(
    latest: FeatureEvidence,
    evidence: RetainedFeatures,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    allocation: Work,
) -> Result | None:
    """
    Preserve grouped retained successes; continue infeasible closure with bounded member inequalities.

    Keep the same measured cap-closed source and all actual feature reports.
    After grouped projection failure, combine the original quality ceiling and
    member inequalities immediately, without spending unused corrections on an
    overlong preliminary closure. Both actions share the caller's unused work.
    """
    cpu, wall = process_time(), perf_counter()
    prior = recover_fold(
        latest.route,
        latest.report,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=allocation.pairs,
        maximum_cpu_seconds=allocation.cpu_seconds,
        maximum_seconds=allocation.wall_seconds,
        maximum_updates=allocation.updates,
        continuation=evidence,
    )
    if (
        prior is None
        or prior.contact is not None
        or prior.detail.get("stop_reason") != "joint_projection_infeasible"
    ):
        return prior
    left = allocation.remaining(
        updates=prior.detail["iterations"],
        pairs=prior.detail["contact_pairs"],
        cpu_seconds=process_time() - cpu,
        wall_seconds=perf_counter() - wall,
    )
    if left is None:
        return prior
    record(
        {
            "stage": "member_retained_handoff",
            "status": "started",
            "before": dict(prior.detail),
            "remaining_updates": left.updates,
            "remaining_pairs": left.pairs,
            "feature_reports": len(evidence.evidence),
        }
    )
    child = recover_fold(
        latest.route,
        latest.report,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=left.pairs,
        maximum_cpu_seconds=left.cpu_seconds,
        maximum_seconds=left.wall_seconds,
        maximum_updates=left.updates,
        continuation=evidence,
        projection=FeatureProjection.MEMBERS,
        quality=StraightQuality(maximum_length_mm, left.updates),
    )
    return (
        prior
        if child is None
        else _combined_result(
            latest.route, prior, child, allocation, cpu, wall, "before_grouped_retained"
        )
    )


def _combined_result(
    original: FoldRoute,
    prior: Result,
    child: Result,
    allocation: Work,
    cpu: float,
    wall: float,
    history_key: str,
) -> Result:
    """
    Charge all preceding actions and reject any continuation exceeding its shared allocation.
    """
    detail = dict(child.detail)
    detail[history_key] = dict(prior.detail)
    for field in ("iterations", "newton_steps", "contacts", "contact_pairs", "contact_seconds"):
        detail[field] += prior.detail[field]
    detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
    if (
        detail["iterations"] > allocation.updates
        or detail["newton_steps"] > 6 * allocation.updates
        or detail["contact_pairs"] > allocation.pairs
        or detail["cpu_seconds"] >= allocation.cpu_seconds
        or detail["elapsed_seconds"] >= allocation.wall_seconds
    ):
        detail.update(status="unresolved", stop_reason="shared_budget")
        return Result(original, None, detail)
    return Result(child.route if child.contact is not None else original, child.contact, detail)
