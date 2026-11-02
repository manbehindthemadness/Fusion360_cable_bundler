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


def improves(candidate: Branch, baseline: Branch) -> bool:
    """
    Require strictly shorter material and non-increasing ordered guide position/direction.

    No weighted tradeoff or tolerance allowance can buy a worsening in another
    measure. These are sampled routing preferences, not physical certificates.
    """
    return (
        candidate.route.material_length_mm < baseline.route.material_length_mm
        and candidate.guide.rms_mm <= baseline.guide.rms_mm
        and candidate.guide.mean_direction_loss <= baseline.guide.mean_direction_loss
    )


def select(
    branches: Sequence[Branch],
    certify: Callable[[Branch], bool],
    policy: Policy = Policy.MONOTONIC,
) -> Branch | None:
    """
    Preserve original two-attempt feasibility and use spare contact work for a dominating branch.

    Try the original midpoint-ranked first branch. If separated, certify at most
    one strictly shorter/non-worsening alternative, keeping the baseline if that
    check fails. Otherwise try the original second branch and stop. Thus neither
    contact failures nor conflicting preferences displace an original safe route,
    and no execution exceeds two certificates. Hard errors propagate.
    """
    ordered = sorted(
        branches,
        key=lambda b: (round(b.site_error_mm2, 12), b.route.material_length_mm, b.roots),
    )
    for index, baseline in enumerate(ordered[:2]):
        if not certify(baseline):
            continue
        if index == 0 and policy is Policy.MONOTONIC:
            alternatives = sorted(
                (b for b in ordered if improves(b, baseline)), key=lambda b: b.priority
            )
            if alternatives and certify(alternatives[0]):
                return alternatives[0]
        return baseline
    return None
