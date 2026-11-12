"""
Discover strict affine-phase material crossings without convex profile support work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, ClassVar

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact import Penetration, ProbeResult, validate_negative_probe
from .contact_flat_geometry import FlatPhase
from .contact_inverse import occupied_coordinates
from .contact_phase_prism import (
    CorePreparations,
    FlatCore,
    PrismKind,
    height_separated,
    intersection_vertices,
)
from .geometry import FoldRoute


@dataclass
class CoreProbe:
    """
    Count phase comparisons and actual edge/inverse work, never acceptance or clearance.

    One owner supplies every comparison allocation and resource checkpoint.
    This uses no convex-profile supports. Exact immutable prism preparation
    may be reused within sixty-four entries; no witness or result is cached.
    """

    comparisons: int = 0
    edges: int = 0
    inverse_tests: int = 0
    witnesses: int = 0
    skipped_phase_pairs: int = 0
    height_filter_attempts: int = 0
    height_rejected_proposals: int = 0

    proposal_kinds: ClassVar[tuple[PrismKind, ...]] = (PrismKind.VALLEY,)
    discovery_reason: ClassVar[str] = "Strict flat-core material crossing during cap restoration"

    @cached_property
    def _cores(self) -> CorePreparations:
        """
        Own bounded pure phase geometry preparation independently of all other models.
        """
        return CorePreparations()

    def preparations(self) -> dict[str, int]:
        """
        Report exact preparation reuse separately from discovery comparisons.
        """
        return self._cores.statistics()

    def _charge(self, kind: PrismKind) -> None:
        """
        Charge a proposal before its geometry or inverse work begins.
        """
        self.comparisons += 1

    def _proposal(
        self,
        route: FoldRoute,
        pair: tuple[int, int],
        cores: tuple[FlatCore, FlatCore],
        checkpoint: Callable[[], None],
    ) -> tuple[Penetration | None, bool]:
        """
        Return a strict witness and whether the bounded prism intersection supplied vertices.

        The second result schedules inner proposals only; neither an empty
        intersection nor failed inverses supply actual material clearance.
        Complete proposal world bounds and padded height planes can reject an
        empty intersection before edge work. Attempts include interrupted height
        filtering; rejections count only completed strict proposal exclusions.
        """
        if any(a[1] < b[0] or b[1] < a[0] for a, b in zip(cores[0].bounds, cores[1].bounds)):
            return None, False
        self.height_filter_attempts += 1
        if height_separated(*cores, checkpoint):
            self.height_rejected_proposals += 1
            return None, False
        before = self.edges

        def visit_edge() -> None:
            """
            Preserve cancellation and the original thirty-edge ceiling for this proposal.
            """
            checkpoint()
            if self.edges - before >= 30:
                raise ArithmeticError("Flat core exceeded its original phase edge ceiling")
            self.edges += 1

        vertices = intersection_vertices(*cores, visit_edge)
        if len(vertices) > 60:
            raise ArithmeticError("Flat core exceeded its original endpoint ceiling")
        if not vertices:
            return None, False
        point = Vector3(*(math.fsum(p[i] for p in vertices) / len(vertices) for i in range(3)))
        coordinates = []
        for index in pair:
            checkpoint()
            self.inverse_tests += 1
            coordinates.append(
                occupied_coordinates(
                    route.pieces[index], point, route.targets.lines, route.targets.diameter_mm
                )
            )
        one, two = coordinates
        if one is None or two is None:
            return None, True
        self.witnesses += 1
        return Penetration(pair, one, two, point), True

    def __call__(
        self,
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None],
        *,
        excluded_phases: frozenset[tuple[FlatPhase, FlatPhase]] = frozenset(),
    ) -> ProbeResult:
        """
        Charge every selected phase proposal and verify at most one centroid per comparison.

        Full nominal-width valley cores retain actual bank-dependent flat cuts.
        The default policy proposes only the valley core. Subclasses may select
        an outer-height prism before a separately charged inner-core fallback.
        Every tested point must occupy both original strict material interiors.
        Empty, tangent, curved or lobe-only misses return no witness, never an
        axis or clearance. Exclusions name represented guidance only; they do
        not persist or affect the original complete material certificate.
        """
        validate_negative_probe(route, first, second, remaining_pairs)
        checkpoint()
        checked = 0
        pieces = (route.pieces[first], route.pieces[second])
        phases = tuple(
            (FlatPhase.BEFORE, FlatPhase.AFTER)
            if isinstance(piece.geometry, CylindricalFold)
            else (FlatPhase.STRAIGHT,)
            for piece in pieces
        )
        for left in phases[0]:
            for right in phases[1]:
                checkpoint()
                if (left, right) in excluded_phases:
                    self.skipped_phase_pairs += 1
                    continue
                for kind in self.proposal_kinds:
                    checkpoint()
                    if checked >= remaining_pairs:
                        return ProbeResult(checked, limit="pairs")
                    checked += 1
                    self._charge(kind)
                    a, b = (
                        self._cores(
                            piece, phase, route.targets.lines, route.targets.diameter_mm, kind
                        )
                        for piece, phase in zip(pieces, (left, right))
                    )
                    if a is None or b is None:
                        break
                    witness, nonempty = self._proposal(route, (first, second), (a, b), checkpoint)
                    if witness is not None:
                        return ProbeResult(checked, witness)
                    if not nonempty:
                        break
        return ProbeResult(checked)


@dataclass
class ProfileProbe(CoreProbe):
    """
    Discover nominal-width lobe crossings before a separately charged valley fallback.

    Outer prisms cover full lobe height, including empty profile valleys. Their
    centroids have no authority without both original strict material inverses.
    A nonempty invalid centroid permits a valley proposal inside the SAME caller
    comparison pool. Empty outer intersections skip inner proposal work only.
    No side-extension/curved coverage, support renewal or clearance is implied.
    """

    lobe_comparisons: int = 0
    valley_fallbacks: int = 0

    proposal_kinds: ClassVar[tuple[PrismKind, ...]] = (
        PrismKind.LOBE_HEIGHT,
        PrismKind.VALLEY,
    )
    discovery_reason: ClassVar[str] = "Strict flat-profile prism crossing during cap restoration"

    def _charge(self, kind: PrismKind) -> None:
        """
        Count the selected proposal kind independently of its actual edge and inverse work.
        """
        super()._charge(kind)
        if kind is PrismKind.LOBE_HEIGHT:
            self.lobe_comparisons += 1
        else:
            self.valley_fallbacks += 1
