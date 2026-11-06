"""
Order already-closed branches by actual material cost without midpoint overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_spline_guide.guide import Agreement, Guide, agreement


class Policy(Enum):
    """
    Keep the diagnostic midpoint ablation distinct from bounded monotonic selection.
    """

    MIDPOINT = "midpoint"
    MONOTONIC = "monotonic"


@dataclass(frozen=True)
class Branch:
    """
    Retain immutable geometry and whole-route preferences before contact acceptance.
    """

    roots: tuple[int, ...]
    route: FoldRoute
    guide: Agreement
    site_error_mm2: float = 0.0

    @classmethod
    def measure(
        cls,
        roots: tuple[int, ...],
        route: FoldRoute,
        guide: Guide,
        site_error_mm2: float = 0.0,
    ) -> Branch:
        """
        Measure the same ordered65station agreement used in existing diagnostics.
        """
        return cls(roots, route, agreement(route, guide), site_error_mm2)

    @property
    def priority(self) -> tuple[float, float, float, tuple[int, ...]]:
        """
        Minimize material length, then guide RMS/direction, with stable algebraic-root ties.

        This introduces no weighted tradeoff or feasibility waiver. It only orders
        existing closed branches; contact acceptance and the finite attempt budget
        remain the caller's responsibility. It proves no global routing optimum.
        """
        return (
            self.route.material_length_mm,
            self.guide.rms_mm,
            self.guide.mean_direction_loss,
            self.roots,
        )


class ImprovementPolicy(Enum):
    """
    Distinguish historical construction preferences from completed first-pass quality.
    """

    GUIDE_DOMINANCE = "guide_dominance"
    MATERIAL_LENGTH = "material_length"

    def accepts(self, candidate: Branch, baseline: Branch) -> bool:
        """
        Require strict shortening; apply guide vetoes only to historical initialization.

        Material-length policy belongs after baseline contraction. Choosing a
        shorter coarse route before that work can worsen the completed route.
        Neither preference replaces contact or fixed-target certification.
        """
        shorter = candidate.route.material_length_mm < baseline.route.material_length_mm
        return shorter and (
            self is ImprovementPolicy.MATERIAL_LENGTH
            or (
                candidate.guide.rms_mm <= baseline.guide.rms_mm
                and candidate.guide.mean_direction_loss <= baseline.guide.mean_direction_loss
            )
        )


def improves(candidate: Branch, baseline: Branch) -> bool:
    """
    Require strictly shorter material and non-increasing ordered guide position/direction.

    No weighted tradeoff or tolerance allowance can buy a worsening in another
    measure. These are sampled routing preferences, not physical certificates.
    """
    return ImprovementPolicy.GUIDE_DOMINANCE.accepts(candidate, baseline)


def select(
    branches: Sequence[Branch],
    permit: Callable[[Branch], bool],
    policy: Policy = Policy.MONOTONIC,
    *,
    maximum_attempts: int = 2,
) -> Branch | None:
    """
    Preserve original feasibility order within the caller's finite contact-work allowance.

    Try the original midpoint-ranked first branch. If permitted, evaluate at most
    one strictly shorter/non-worsening alternative, keeping the baseline if that
    check fails. Otherwise try subsequent midpoint-ranked branches in order. Thus neither
    contact failures nor conflicting preferences displace an original safe route,
    and an accepted original fallback still stops selection. The default retains
    two attempts; a caller may expose more existing branches under its own shared
    work budget. This helper never creates geometry or authorizes extra pair work.
    The caller retains raw contact
    results, including any explicitly authorized temporary measurement warning.
    Hard errors propagate.
    """
    if type(maximum_attempts) is not int or maximum_attempts < 1:
        raise ValueError("A positive finite branch-attempt count is required")
    ordered = sorted(
        branches,
        key=lambda b: (round(b.site_error_mm2, 12), b.route.material_length_mm, b.roots),
    )
    for index, baseline in enumerate(ordered[:maximum_attempts]):
        if not permit(baseline):
            continue
        if index == 0 and maximum_attempts > 1 and policy is Policy.MONOTONIC:
            alternatives = sorted(
                (b for b in ordered if improves(b, baseline)), key=lambda b: b.priority
            )
            if alternatives and permit(alternatives[0]):
                return alternatives[0]
        return baseline
    return None
