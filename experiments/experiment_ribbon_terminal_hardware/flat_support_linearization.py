"""
Keep tied complete-prism support branches separate inside the original bounded linear projector.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import fsum, isfinite
from typing import AbstractSet, Callable, Sequence, Union

from experiments.experiment_ribbon_feature_insertion.separation import Side

from .flat_separation import FlatSeparation
from .material_constraint import MaterialConstraint
from .projection_system import CoordinateBounds

Constraint = Union[FlatSeparation, MaterialConstraint]


@dataclass(frozen=True)
class SupportBundle:
    """
    Retain every active full-prism vertex pair without granting physical separation.
    """

    flat: FlatSeparation
    side: Side
    pairs: tuple[tuple[int, int], ...]
    sizes: tuple[int, int]
    minimum_gap_mm: float = 1e-8

    def residuals(self, values: tuple[float, ...]) -> tuple[float, ...] | None:
        """
        Follow identical polygon/height identities, declining changed vertex topology.
        """
        first, second = self.flat.support_values(values)
        if (len(first), len(second)) != self.sizes:
            return None
        sign = 1 if self.side is Side.BEFORE else -1
        return tuple(
            (self.minimum_gap_mm + sign * (first[i] - second[j])) / self.flat.model.scale
            for i, j in self.pairs
        )


class SupportSelection(Enum):
    """
    Distinguish diagnosis in an existing replacement from continuation of already diagnosed supports.
    """

    IDENTIFY = "identify"
    RETAIN = "retain"


class SupportMemory:
    """
    Own diagnosed support identities for one correction action, never across routes or stages.

    Strong constraint ownership prevents object-id reuse. Removed or replaced
    constraints are retired, including changed axes. This retains linear model
    evidence only; geometry still requires full current-pose nonlinear proofs.
    """

    def __init__(self) -> None:
        """
        Begin with no diagnosed nonsmooth constraints.
        """
        self._supports: dict[int, SupportBundle] = {}

    @property
    def active(self) -> bool:
        """
        Report whether a previous guarded correction diagnosed any retained support identities.
        """
        return bool(self._supports)

    def get(self, flat: FlatSeparation, side: Side) -> SupportBundle | None:
        """
        Require identical immutable constraint ownership and separating side.
        """
        found = self._supports.get(id(flat))
        return found if found is not None and found.flat is flat and found.side is side else None

    def remember(self, supports: tuple[SupportBundle, ...]) -> None:
        """
        Retain only complete bundles actually admitted by the current bounded linear model.
        """
        for support in supports:
            self._supports[id(support.flat)] = support

    def prune(self, constraints: Sequence[tuple[Constraint, Side]]) -> None:
        """
        Release evidence for removed constraints, replaced axes or changed separating sides.
        """
        current = {
            id(constraint.bound if isinstance(constraint, MaterialConstraint) else constraint): side
            for constraint, side in constraints
        }
        self._supports = {
            key: support
            for key, support in self._supports.items()
            if key in current and current[key] is support.side
        }


def active_supports(
    flat: FlatSeparation, side: Side, values: tuple[float, ...], *, minimum_gap_mm: float = 1e-8
) -> SupportBundle:
    """
    Select all tied full-region support pairs using the existing normalized numerical row precision.

    Nearly tied branches within1e-14 are included conservatively. Every selected
    pair retains full polygon and signed-height identity; a subset never becomes
    a contact certificate. Smooth single-support bounds need no expanded rows.
    """
    first, second = flat.support_values(values)
    sign = 1 if side is Side.BEFORE else -1
    supports = tuple(
        (sign * (x - y) / flat.model.scale, i, j)
        for i, x in enumerate(first)
        for j, y in enumerate(second)
    )
    maximum = max(term for term, _, _ in supports)
    pairs = tuple((i, j) for term, i, j in supports if maximum - term <= 1e-14)
    return SupportBundle(flat, side, pairs, (len(first), len(second)), minimum_gap_mm)


@dataclass(frozen=True)
class Linearization:
    """
    Own immutable linear rows while raw nonlinear equations remain the caller's unchanged authority.
    """

    terms: tuple[float, ...]
    rows: tuple[tuple[float, ...], ...]
    bundles: int
    added_rows: int
    capacity_declines: int
    topology_declines: int
    supports: tuple[SupportBundle, ...] = ()

    def contradicts(
        self,
        original_terms: tuple[float, ...],
        original_rows: list[list[float]],
        direction: tuple[float, ...],
    ) -> bool:
        """
        Request substitution only when complete branch prediction contradicts scalar maximum-merit descent.

        This selects a model for an already allocated replacement projection,
        never another optimizer or permission to accept a nonlinear proposal.
        """
        if (
            len(original_terms) != len(original_rows)
            or len(self.terms) != len(self.rows)
            or any(len(row) != len(direction) for row in (*original_rows, *self.rows))
        ):
            raise ValueError("Compare complete linear rows and correction coordinates")
        if not self.bundles:
            return False

        def merit(terms: tuple[float, ...]) -> float:
            """
            Preserve the existing six-cap and positive-inequality maximum metric.
            """
            return max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(terms))

        original = tuple(
            term + fsum(a * b for a, b in zip(row, direction))
            for term, row in zip(original_terms, original_rows)
        )
        expanded = tuple(
            term + fsum(a * b for a, b in zip(row, direction))
            for term, row in zip(self.terms, self.rows)
        )
        before = merit(original_terms)
        return merit(original) < before <= merit(expanded)


def _derivatives(
    bundle: SupportBundle,
    values: tuple[float, ...],
    base: tuple[float, ...],
    model: CoordinateBounds,
    fixed: AbstractSet[int],
    admissible: Callable[[tuple[float, ...]], bool],
    checkpoint: Callable[[], None],
) -> tuple[tuple[float, ...], ...] | None:
    """
    Use the original one-sided1e-5 endpoints on smooth support branches, without another optimizer.
    """
    rows = [[0.0] * len(values) for _ in base]
    for index, value in enumerate(values):
        checkpoint()
        if index in fixed:
            continue
        low, high = model.bounds(index)
        probe = list(values)
        probe[index] = min(high, value + 1e-5)
        if probe[index] == value or not admissible(tuple(probe)):
            probe[index] = max(low, value - 1e-5)
            if probe[index] == value or not admissible(tuple(probe)):
                return None
        sample = bundle.residuals(tuple(probe))
        if sample is None:
            return None
        for row, before, after in zip(rows, base, sample):
            row[index] = (after - before) / (probe[index] - value)
    return tuple(tuple(row) for row in rows)


def linearize(
    constraints: Sequence[tuple[Constraint, Side]],
    values: tuple[float, ...],
    terms: tuple[float, ...],
    jacobian: list[list[float]],
    model: CoordinateBounds,
    fixed: AbstractSet[int],
    admissible: Callable[[tuple[float, ...]], bool],
    checkpoint: Callable[[], None],
    *,
    memory: SupportMemory | None = None,
    selection: SupportSelection = SupportSelection.IDENTIFY,
    minimum_gap_mm: float = 1e-8,
) -> Linearization:
    """
    Expand violated tied flat rows only when their entire active bundle fits the original thirteen rows.

    Constraints must occupy distinct final raw-equation rows in their original
    order. Curved, satisfied and single-support bounds retain their exact rows.
    Capacity, vertex-topology or base-span disagreement declines that complete
    bundle before projection; no support subset, fallback solve or extra trial
    is allocated. Changed geometry still uses the original complete nonlinear
    equations and final certificates. Native fixed columns stay exactly zero.
    """
    if not isinstance(selection, SupportSelection):
        raise ValueError("Select support diagnosis or retained-model continuation explicitly")
    if (
        type(minimum_gap_mm) not in (int, float)
        or not isfinite(minimum_gap_mm)
        or minimum_gap_mm <= 0
    ):
        raise ValueError("Preserve a finite positive physical support gap")
    if (
        not 7 <= len(terms) <= 19
        or len(jacobian) != len(terms)
        or len(constraints) > len(terms) - 6
        or any(len(row) != len(values) for row in jacobian)
    ):
        raise ValueError("Supply six cap rows and distinct final material inequalities")
    start = len(terms) - len(constraints)
    output_terms = list(terms[:start])
    output_rows = [tuple(row) for row in jacobian[:start]]
    retained: list[SupportBundle] = []
    if memory is not None:
        memory.prune(constraints)
    bundles = added_rows = capacity = topology = 0
    for offset, (constraint, side) in enumerate(constraints):
        checkpoint()
        row = start + offset
        flat = constraint.bound if isinstance(constraint, MaterialConstraint) else constraint
        previous = (
            memory.get(flat, side)
            if memory is not None and isinstance(flat, FlatSeparation)
            else None
        )
        bundle = (
            active_supports(flat, side, values, minimum_gap_mm=minimum_gap_mm)
            if isinstance(flat, FlatSeparation)
            and terms[row] > 0
            and (selection is SupportSelection.IDENTIFY or previous is not None)
            else None
        )
        if bundle is not None and previous is not None:
            if previous.sizes != bundle.sizes:
                topology += 1
                bundle = None
            else:
                pairs = tuple(dict.fromkeys((*previous.pairs, *bundle.pairs)))
                bundle = SupportBundle(bundle.flat, side, pairs, bundle.sizes, minimum_gap_mm)
        if bundle is not None and len(bundle.pairs) > 1:
            extra = len(bundle.pairs) - 1
            if len(terms) + added_rows + extra > 19:
                capacity += 1
            else:
                base = bundle.residuals(values)
                assert base is not None
                derivatives = (
                    _derivatives(bundle, values, base, model, fixed, admissible, checkpoint)
                    if abs(max(base) - terms[row]) <= 1e-13
                    else None
                )
                if derivatives is not None:
                    output_terms.extend(base)
                    output_rows.extend(derivatives)
                    retained.append(bundle)
                    bundles, added_rows = bundles + 1, added_rows + extra
                    continue
                topology += 1
        output_terms.append(terms[row])
        output_rows.append(tuple(jacobian[row]))
    return Linearization(
        tuple(output_terms),
        tuple(output_rows),
        bundles,
        added_rows,
        capacity,
        topology,
        tuple(retained),
    )
