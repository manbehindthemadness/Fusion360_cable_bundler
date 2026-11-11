"""
Find strict new flat-region crossings without granting clearance to an open-cap proposal.
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping

from experiments.experiment_ribbon_feature_insertion.separation import Side, regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .flat_separation import FlatSeparation
from .material_constraint import MaterialConstraint

PhasePair = tuple[FlatPhase, FlatPhase]


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
) -> ContactResult:
    """
    Screen original nonadjacent pairs once, returning penetration or explicitly unmeasured contact.

    Charge root visits and every optional hull comparison to the supplied original
    pair allowance. The caller owns the probe's shared support ceiling and decides
    whether an already represented witness needs another constraint. Recheck both
    strict material inverse maps before exposing any new witness. Adjacent/curved
    misses and pair/support exhaustion never imply separation. Cancellation is
    propagated so the owner can charge interrupted work conservatively.
    """
    if type(maximum_pairs) is not int or maximum_pairs < 0:
        raise ValueError("Use a nonnegative remaining contact allowance")
    checked = 0
    for first in range(len(route.pieces)):
        for second in range(first + 2, len(route.pieces)):
            checkpoint()
            if checked >= maximum_pairs or probe.supports >= 2048:
                return ContactResult(
                    "unresolved", checked, reason="Negative screen allowance exhausted"
                )
            checked += 1
            excluded = (
                covered_phases.get((first, second), frozenset()) if covered_phases else frozenset()
            )
            result = (
                probe(
                    route,
                    first,
                    second,
                    maximum_pairs - checked,
                    checkpoint,
                    excluded_phases=excluded,
                )
                if excluded
                else probe(route, first, second, maximum_pairs - checked, checkpoint)
            )
            if (
                type(result.pairs_checked) is not int
                or not 0 <= result.pairs_checked <= maximum_pairs - checked
            ):
                raise ArithmeticError("Negative screen exceeded its original contact allowance")
            checked += result.pairs_checked
            witness = result.witness
            if witness is not None:
                if witness.pieces != (first, second):
                    raise ArithmeticError("Negative screen changed original piece identities")
                first_coordinates, second_coordinates = tuple(
                    occupied_coordinates(
                        piece, witness.point, route.targets.lines, route.targets.diameter_mm
                    )
                    for piece in (route.pieces[first], route.pieces[second])
                )
                if first_coordinates is None or second_coordinates is None:
                    raise ArithmeticError("Negative screen supplied no strict material crossing")
                verified = Penetration(
                    (first, second), first_coordinates, second_coordinates, witness.point
                )
                if retain(verified):
                    return ContactResult(
                        "penetration",
                        checked,
                        witness=verified,
                        reason="Strict new material crossing during cap restoration",
                    )
            if result.limit is not None:
                return ContactResult(
                    "unresolved", checked, reason="Negative probe allowance exhausted"
                )
    return ContactResult(
        "unresolved",
        checked,
        reason="Negative screen supplied no new witness; clearance unmeasured",
    )
