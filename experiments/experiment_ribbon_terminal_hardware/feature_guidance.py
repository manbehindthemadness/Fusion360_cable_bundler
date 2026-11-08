"""
Retain actual feature evidence and independent complete-member clearance inequalities.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from cable_bundler.routing.geometry import dot, magnitude, unit
from experiments.experiment_ribbon_feature_insertion.separation import Side, locate
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .model import Hardware


class FeatureGate(Protocol):
    """
    Expose only the existing shared hardware and route-bound measurement needed by feature correction.
    """

    @property
    def hardware(self) -> Hardware:
        """
        Return the same immutable hardware without allocating another measurement budget.
        """
        ...

    def measure(self, route: FoldRoute, stage: str) -> Report:
        """
        Measure one immutable proposal under the caller's existing shared allowance.
        """
        ...

    def certify(self, route: FoldRoute, stage: str) -> Report:
        """
        Certify a completed proposal with refined separation under the same shared allowance.
        """
        ...


@dataclass(frozen=True)
class FeatureEvidence:
    """
    Keep each measured report attached to its actual immutable material route.
    """

    route: FoldRoute
    report: Report


def _bind_features(
    evidence: tuple[FeatureEvidence, ...],
    model: SignedJoints,
    hardware: Hardware,
    values: tuple[float, ...],
    coverage: FeatureCoverage,
) -> list[FeaturePlane] | None:
    """
    Rebind actual immutable reports using the caller's explicit material coverage policy.
    """
    planes: list[FeaturePlane] = []
    for observed in evidence:
        plane = FeaturePlane.create(
            model, observed.route, observed.report, hardware, values, coverage=coverage
        )
        if plane is None:
            return None
        planes.append(plane)
    return planes


@dataclass(frozen=True)
class IncidentGuidance:
    """
    Reflect one actually witnessed event while retaining up to three earlier feature reports.
    """

    selected_fold: int
    evidence: tuple[FeatureEvidence, ...]

    def __post_init__(self) -> None:
        """
        Reject guessed, incomplete, over-capacity or differently targeted evidence.
        """
        if type(self.selected_fold) is not int or self.selected_fold < 0:
            raise ValueError("Select an existing witnessed fold")
        if not 1 <= len(self.evidence) <= 3:
            raise ValueError("Retain one to three actual feature reports")
        targets = self.evidence[0].route.targets
        if any(
            e.route.targets != targets or e.report.status != "blocked" or e.report.witness is None
            for e in self.evidence
        ):
            raise ValueError("Incident guidance requires actual intrusion reports at fixed targets")

    def planes(
        self, model: SignedJoints, hardware: Hardware, values: tuple[float, ...]
    ) -> list[FeaturePlane] | None:
        """
        Rebind every original observed feature to the one reflected model without forging witnesses.
        """
        return _bind_features(
            self.evidence, model, hardware, values, FeatureCoverage.ADJOINING_INTERNAL
        )


def member_planes(
    planes: list[FeaturePlane], model: SignedJoints, values: tuple[float, ...]
) -> list[FeaturePlane]:
    """
    Derive each occupied member's own closest algebraic separating plane, deduplicating identical bounds.

    A fold and adjoining straight need not clear the same face of a finite box.
    Each member still encloses its complete width and thickness. The final shared
    hardware certificate remains authoritative; these are correction equations.
    """
    parts: list[FeaturePlane] = []
    keys: set[tuple[object, ...]] = set()
    pieces = model.pieces(values)
    for whole in planes:
        for member in whole.members:
            prototype = replace(whole, reference=member, members=(member,))
            piece = locate(model.original, pieces, member)
            choices: list[tuple[float, FeaturePlane]] = []
            for family, raw in enumerate(prototype._axes(piece)):
                if magnitude(raw) < 1e-10:
                    continue
                axis = unit(raw)
                bound = prototype._span(pieces, axis)
                coordinates = tuple(dot(point, axis) for point in prototype.corners)
                for side, gap in (
                    (Side.AFTER, bound.low - max(coordinates)),
                    (Side.BEFORE, min(coordinates) - bound.high),
                ):
                    choices.append((gap, replace(prototype, family=family, side=side)))
            part = max(choices, key=lambda pair: pair[0])[1]
            key = (part.box.terminal, part.reference, part.family, part.side)
            if key not in keys:
                parts.append(part)
                keys.add(key)
    return parts


@dataclass(frozen=True)
class RetainedFeatures:
    """
    Continue at most three actual observed features without changing any fold sign.
    """

    evidence: tuple[FeatureEvidence, ...]

    def __post_init__(self) -> None:
        """
        Retain actual intrusion reports at identical fixed targets, without guessed constraints.
        """
        if not 1 <= len(self.evidence) <= 3:
            raise ValueError("Retain one to three actual reports")
        target = self.evidence[0].route.targets
        if any(
            e.report.status != "blocked" or e.report.witness is None or e.route.targets != target
            for e in self.evidence
        ):
            raise ValueError("Retain actual intrusion evidence at fixed targets")

    def planes(
        self, model: SignedJoints, hardware: Hardware, values: tuple[float, ...]
    ) -> list[FeaturePlane] | None:
        """
        Rebind the actual observed features while retaining their original terminalward coverage.
        """
        return _bind_features(
            self.evidence, model, hardware, values, FeatureCoverage.TERMINAL_RUNWAY
        )
