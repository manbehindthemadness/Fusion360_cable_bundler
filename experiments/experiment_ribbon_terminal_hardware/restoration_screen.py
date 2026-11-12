"""
Find strict current material crossings without granting clearance to an open-cap proposal.
"""

from __future__ import annotations

from itertools import chain
from typing import Callable, Iterable, Mapping

from experiments.experiment_ribbon_feature_insertion.separation import Side, regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration, ProbeResult
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.contact_phase_core import CoreProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .curved_discovery import CurvedProbe
from .flat_separation import FlatSeparation
from .material_constraint import MaterialConstraint
from .restoration_order import MaterialFocus, ordered_pairs

PhasePair = tuple[FlatPhase, FlatPhase]


def _verified_witness(
    route: FoldRoute,
    pair: tuple[int, int],
    result: ProbeResult,
    retain: Callable[[Penetration], bool],
) -> Penetration | None:
    """
    Revalidate original current material identity and both strict inverses at the owner boundary.
    """
    witness = result.witness
    if witness is None:
        return None
    if witness.pieces != pair:
        raise ArithmeticError("Negative screen changed original piece identities")
    first, second = tuple(
        occupied_coordinates(
            route.pieces[index], witness.point, route.targets.lines, route.targets.diameter_mm
        )
        for index in pair
    )
    if first is None or second is None:
        raise ArithmeticError("Negative screen supplied no strict material crossing")
    verified = Penetration(pair, first, second, witness.point)
    return verified if retain(verified) else None


def represented_phases(
    route: FoldRoute,
    constraints: Iterable[tuple[FlatSeparation | MaterialConstraint, Side]],
) -> dict[tuple[int, int], frozenset[PhasePair]]:
    """
    Identify complete represented flat phases using stable ordered material slots.

    Both parts must cover the whole current width and thickness. Partial profile
    arcs, curved bounds and missing slots authorize no omission. Piece indices
    are resolved anew for this pose, so appearing straight slots cannot move an
    exclusion onto different material. This is duplicate guidance identity, never
    a clearance certificate for the phase or either complete piece.
    """
    identities = regions(route)
    indices = {tag: index for index, tag in enumerate(identities) if identities.count(tag) == 1}
    result: dict[tuple[int, int], set[PhasePair]] = {}
    for bound, _ in constraints:
        parts = bound.parts
        if len(parts) != 2 or not all(
            part.low_q <= -route.half_width_mm
            and part.high_q >= route.half_width_mm
            and part.half_height >= route.targets.diameter_mm / 2
            for part in parts
        ):
            continue
        first, second = (indices.get(tag) for tag in bound.pair)
        if first is None or second is None or first >= second:
            continue
        phases = (parts[0].phase, parts[1].phase)
        result.setdefault((first, second), set()).add(phases)
    return {pair: frozenset(phases) for pair, phases in result.items()}


def screen(
    route: FoldRoute,
    probe: FlatProbe,
    maximum_pairs: int,
    checkpoint: Callable[[], None],
    retain: Callable[[Penetration], bool],
    *,
    covered_phases: Mapping[tuple[int, int], frozenset[PhasePair]] | None = None,
    focus: MaterialFocus | None = None,
    curved_probe: CurvedProbe | None = None,
    flat_core_probe: CoreProbe | None = None,
) -> ContactResult:
    """
    Screen original nonadjacent pairs once, returning penetration or explicitly unmeasured contact.

    Charge root visits and every optional hull comparison to the supplied original
    pair allowance. The caller owns the probe's shared support ceiling and decides
    whether an already represented witness needs another constraint. Recheck both
    strict material inverse maps before exposing any new witness. Adjacent/curved
    misses and pair/support exhaustion never imply separation. Cancellation is
    propagated so the owner can charge interrupted work conservatively.
    Optional exact-route material focus changes discovery order only. Every
    original nonadjacent pair remains eligible under the same comparison pool;
    stale focus uses the unchanged global order and supplies no certificate.
    A supplied curved context reserves at most half this same comparison pool for
    actual phase-midpoint proposals before flat hull refinement. Roots are charged
    once across both passes; the remaining pool and shared support ceiling cannot
    renew. Every miss remains unmeasured and the full final proof is unchanged.
    An explicit flat-prism context replaces hull refinement for this negative
    screen only, charging every outer/inner proposal to the same comparisons
    and preserving the original support stop.
    It cannot report clearance or renew support work; complete positive checking
    retains the caller's ordinary profile-hull probe.
    """
    if type(maximum_pairs) is not int or maximum_pairs < 0:
        raise ValueError("Use a nonnegative remaining contact allowance")
    checked = 0
    flat_probe = probe if flat_core_probe is None else flat_core_probe
    roots = ordered_pairs(route, focus, checkpoint)
    visited: list[tuple[int, int]] = []
    if curved_probe is not None and probe.supports < 2048:
        reserved = maximum_pairs // 2
        while checked < reserved:
            pair = next(roots, None)
            if pair is None:
                break
            visited.append(pair)
            checked += 1
            result = curved_probe(route, *pair, reserved - checked, checkpoint)
            if (
                type(result.pairs_checked) is not int
                or not 0 <= result.pairs_checked <= reserved - checked
            ):
                raise ArithmeticError("Curved discovery exceeded its original contact allowance")
            checked += result.pairs_checked
            witness = _verified_witness(route, pair, result, retain)
            if witness is not None:
                return ContactResult(
                    "penetration",
                    checked,
                    witness=witness,
                    reason="Strict curved material crossing during cap restoration",
                )
    for ordinal, (first, second) in enumerate(chain(visited, roots)):
        if checked >= maximum_pairs or probe.supports >= 2048:
            return ContactResult(
                "unresolved", checked, reason="Negative screen allowance exhausted"
            )
        if ordinal >= len(visited):
            checked += 1
        excluded = (
            covered_phases.get((first, second), frozenset()) if covered_phases else frozenset()
        )
        result = (
            flat_probe(
                route,
                first,
                second,
                maximum_pairs - checked,
                checkpoint,
                excluded_phases=excluded,
            )
            if excluded
            else flat_probe(route, first, second, maximum_pairs - checked, checkpoint)
        )
        if (
            type(result.pairs_checked) is not int
            or not 0 <= result.pairs_checked <= maximum_pairs - checked
        ):
            raise ArithmeticError("Negative screen exceeded its original contact allowance")
        checked += result.pairs_checked
        witness = _verified_witness(route, (first, second), result, retain)
        if witness is not None:
            return ContactResult(
                "penetration",
                checked,
                witness=witness,
                reason=flat_core_probe.discovery_reason
                if flat_core_probe is not None
                else "Strict new material crossing during cap restoration",
            )
        if result.limit is not None:
            return ContactResult("unresolved", checked, reason="Negative probe allowance exhausted")
    return ContactResult(
        "unresolved",
        checked,
        reason="Negative screen supplied no new witness; clearance unmeasured",
    )
