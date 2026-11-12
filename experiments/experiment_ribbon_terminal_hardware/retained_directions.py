"""
Offer learned material directions to the existing full-cell proof without transferring clearance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_route.contact import ProbeResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_plane import SignedJoints
from .flat_separation import FlatSeparation
from .material_constraint import MaterialConstraint
from .material_pose import current_regions


@dataclass(frozen=True)
class RetainedDirections:
    """
    Bind one untrusted direction per material pair to one exact immutable candidate.

    No projection, gap or certificate is retained. The contact checker must
    enclose both complete current material cells before any positive decision.
    Use MATERIAL_CELLS probe order to preserve the ordinary depth-first traversal.
    """

    source: FoldRoute
    axes: tuple[tuple[int, int, Vector3], ...]

    @classmethod
    def prepare(
        cls,
        route: FoldRoute,
        model: SignedJoints,
        values: tuple[float, ...],
        constraints: Iterable[tuple[FlatSeparation | MaterialConstraint, Side]],
        checkpoint: Callable[[], None],
    ) -> RetainedDirections | None:
        """
        Resolve only model-owned current material identities, declining changed or ambiguous placement.

        Full phases and partial guidance alike can suggest a direction, never
        authorize an exclusion. The first retained direction per pair wins;
        preparation performs no support search and renews no caller allowance.
        """
        checkpoint()
        tags = current_regions(route, model, values)
        if tags is None:
            return None
        locations = {tag: index for index, tag in enumerate(tags)}
        directions: dict[tuple[int, int], Vector3] = {}
        for bound, _ in constraints:
            checkpoint()
            owner = bound.bound if isinstance(bound, MaterialConstraint) else bound
            if owner.model is not model or any(tag not in locations for tag in owner.pair):
                continue
            first, second = (locations[tag] for tag in owner.pair)
            if first < second:
                directions.setdefault((first, second), owner.axis)
        checkpoint()
        axes = tuple((first, second, axis) for (first, second), axis in directions.items())
        return cls(route, axes) if axes else None

    def __call__(
        self,
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None] | None,
    ) -> ProbeResult:
        """
        Propose a retained axis without support queries, witnesses or additional pair comparisons.

        The existing checker validates finite nonzero directions and measures
        their outward-rounded projections. An unknown or copied source supplies
        no proposal. Caller cancellation and pair accounting remain authoritative.
        """
        if checkpoint is not None:
            checkpoint()
        if type(remaining_pairs) is not int or remaining_pairs < 0:
            raise ValueError("Use the original nonnegative remaining pair allowance")
        if route is self.source:
            for a, b, axis in self.axes:
                if (a, b) == (first, second):
                    return ProbeResult(0, axis_proposal=axis)
        return ProbeResult(0)
