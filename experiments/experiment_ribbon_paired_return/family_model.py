"""
Move owned pair banks and existing straight slots while eliminating dependent orientation coordinates.
"""

from __future__ import annotations

import math
from functools import cached_property, lru_cache
from typing import Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_relaxation.steps import MAXIMUM_ANGULAR_STEP_RADIANS
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import fixed_fold_frames_match
from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import PROBE_STEP

from .frame_family import FrameFamily


class CoupledJoints(SignedJoints):
    """
    Keep other bends fixed while retaining every owned pair's signed material branch.

    Straight slots and one bank per owned pair are independent. Each other bank and
    both bend angles follow FrameFamily, so no rotational Newton equations are
    needed. Every material placement and final certificate still uses the shared
    full geometry model. Radius, profile width and extra flat leads remain fixed.
    """

    pairs: tuple[tuple[int, int], ...]
    native_floor: float | None

    def __init__(
        self,
        original: FoldRoute,
        pairs: tuple[tuple[int, int], ...],
        minimum_straight_mm: float | None = None,
    ) -> None:
        """
        Require disjoint owned pairs without changing material or caller action order.
        """
        super().__init__(original)
        if any(type(fold) is not CylindricalFold for fold in self.folds):
            raise ValueError("An orientation family requires ordinary material folds")
        if not fixed_fold_frames_match(original.pieces, original.targets):
            raise ValueError("An eliminated orientation must already match both target frames")
        if not pairs or any(
            len(pair) != 2
            or any(type(i) is not int for i in pair)
            or not 0 <= pair[0] < pair[1] < len(self.folds)
            or pair[1] != pair[0] + 1
            for pair in pairs
        ):
            raise ValueError("Use existing consecutive material-fold pairs")
        identities = tuple(i for pair in pairs for i in pair)
        if len(set(identities)) != len(identities):
            raise ValueError("Owned orientation families must not overlap")
        object.__setattr__(self, "pairs", pairs)
        floor = (
            None
            if minimum_straight_mm is None
            else minimum_coordinate(minimum_straight_mm, self.scale)
        )
        if minimum_straight_mm is not None and floor is None:
            raise ValueError("Use the existing positive native minimum")
        object.__setattr__(self, "native_floor", floor)

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep existing positive native material inside coordinate bounds during restoration.

        A native floor is not a soft restoration inequality. Absent source slots
        retain their original zero lower face; bank bounds remain unchanged.
        """
        low, high = super().bounds(index)
        if (
            self.native_floor is not None
            and index in self.straight_indices
            and self.initial[index] > 0
        ):
            low = max(low, self.native_floor)
        return low, high

    def compensation_pairs(self) -> tuple[tuple[int, int], ...]:
        """
        Extend owned pairs with regular disjoint charts in untouched material order.

        A chart starts on the current signed branch, without reflection or root
        enumeration. Unsupported pairs remain fixed. Existing ownership and its
        caller order stay authoritative; each additional fold belongs to at most
        one chart. No folds or straight slots are inserted.
        """
        pairs = list(self.pairs)
        occupied = {i for pair in pairs for i in pair}
        placed = tuple(p for p in self.original.pieces if type(p.geometry) is CylindricalFold)
        index = 0
        while index + 1 < len(self.folds):
            if index in occupied or index + 1 in occupied:
                index += 1
                continue
            family = FrameFamily(
                placed[index].pose,
                placed[index + 1].end_pose(),
                (self.folds[index], self.folds[index + 1]),
            )
            if family.at(self.folds[index].bank_radians) is None:
                index += 1
                continue
            pairs.append((index, index + 1))
            occupied.update((index, index + 1))
            index += 2
        return tuple(pairs)

    @cached_property
    def indices(self) -> tuple[int, ...]:
        """
        Expose all straight slots and one independent bank per owned pair.
        """
        banks = {4 * pair[0] + 2 for pair in self.pairs}
        return tuple(i for i in range(len(self.full.initial)) if i % 4 == 0 or i in banks)

    @cached_property
    def bank_indices(self) -> tuple[int, ...]:
        """
        Map independent banks in the caller's retained pair-ownership order.
        """
        return tuple(self.indices.index(4 * pair[0] + 2) for pair in self.pairs)

    @cached_property
    def families(self) -> tuple[FrameFamily, ...]:
        """
        Bind each immutable pair boundary without changing straight or event identity.
        """
        placed = tuple(p for p in self.original.pieces if type(p.geometry) is CylindricalFold)
        return tuple(
            FrameFamily(placed[a].pose, placed[b].end_pose(), (self.folds[a], self.folds[b]))
            for a, b in self.pairs
        )

    @cached_property
    def factor_caches(
        self,
    ) -> tuple[Callable[[float], tuple[CylindricalFold, CylindricalFold] | None], ...]:
        """
        Bound each model-local family cache to64immutable bank samples.
        """
        return tuple(lru_cache(maxsize=64)(family.at) for family in self.families)

    def expanded(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Eliminate dependent angle/bank coordinates before the established placement kernel.
        """
        expanded = list(super().expanded(values))
        for pair, bank, evaluate in zip(self.pairs, self.bank_indices, self.factor_caches):
            factors = evaluate(values[bank])
            if factors is None:
                raise ValueError("Unsupported continuous material-frame coordinate")
            for ordinal, factor in zip(pair, factors):
                expanded[4 * ordinal + 1], expanded[4 * ordinal + 2] = (
                    factor.angle_radians,
                    factor.bank_radians,
                )
        return tuple(expanded)

    def admissible(self, values: tuple[float, ...]) -> bool:
        """
        Decline any invalid owned chart before the inherited material-domain check.
        """
        if len(values) != len(self.initial) or any(not math.isfinite(v) for v in values):
            return False
        if any(
            evaluate(values[bank]) is None
            for bank, evaluate in zip(self.bank_indices, self.factor_caches)
        ):
            return False
        return super().admissible(values)

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Eliminate analytically fixed rotation rows; final ordered-frame checks remain independent.
        """
        return super().residual(values)[:3] + (0.0, 0.0, 0.0)

    def allows_step(self, before: tuple[float, ...], after: tuple[float, ...]) -> bool:
        """
        Enforce the original angular limit on dependent angles and banks as well as free banks.
        """
        for bank, evaluate in zip(self.bank_indices, self.factor_caches):
            first, last = evaluate(before[bank]), evaluate(after[bank])
            if (
                first is None
                or last is None
                or any(
                    max(
                        abs(a.angle_radians - b.angle_radians), abs(a.bank_radians - b.bank_radians)
                    )
                    > MAXIMUM_ANGULAR_STEP_RADIANS
                    for a, b in zip(first, last)
                )
            ):
                return False
        return True

    def length_gradient(self, values: tuple[float, ...]) -> list[float]:
        """
        Include dependent factor changes in the normalized material-length derivative.
        """
        gradient = [1.0 if i in self.straight_indices else 0.0 for i in range(len(values))]
        for bank in self.bank_indices:
            low, high = self.bounds(bank)
            a, b = list(values), list(values)
            a[bank], b[bank] = (
                max(low, values[bank] - PROBE_STEP),
                min(high, values[bank] + PROBE_STEP),
            )
            for probe in (a, b):
                if not self.admissible(tuple(probe)):
                    probe[bank] = values[bank]
            if a[bank] == b[bank]:
                raise ArithmeticError("Continuous bank has no regular derivative endpoint")
            lengths = [
                math.fsum(p.geometry.material_length_mm for p in self.pieces(tuple(probe)))
                / self.scale
                for probe in (a, b)
            ]
            gradient[bank] = (lengths[1] - lengths[0]) / (b[bank] - a[bank])
        return gradient


class FamilyJoints(CoupledJoints):
    """
    Preserve the intention-revealing single-pair entry point over the shared coordinate model.
    """

    def __init__(self, original: FoldRoute, pair: tuple[int, int]) -> None:
        """
        Own exactly one existing consecutive pair without another coordinate policy.
        """
        super().__init__(original, (pair,))

    @property
    def pair(self) -> tuple[int, int]:
        """
        Return the single owned material interval.
        """
        return self.pairs[0]

    @property
    def bank_index(self) -> int:
        """
        Retain the compact single-bank coordinate identity.
        """
        return self.bank_indices[0]

    @property
    def family(self) -> FrameFamily:
        """
        Retain the single-family analytical boundary.
        """
        return self.families[0]

    @property
    def factors(self) -> Callable[[float], tuple[CylindricalFold, CylindricalFold] | None]:
        """
        Retain the bounded single-family factor evaluator.
        """
        return self.factor_caches[0]
