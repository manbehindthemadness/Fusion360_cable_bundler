"""
Resolve endpoint side candidates only when one complete original cyclic assignment exists.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field

from .boundary_cycle_junctions import BoundaryCycleJunctions
from .boundary_traversal import BoundaryTraversal, BoundaryTraversalPolicy
from .material_polygon import ORDER, MaterialPolygon
from .native_boundary_distance import BoundarySide


@dataclass(frozen=True)
class BoundaryCycleCandidates:
    """
    Count complete cyclic side assignments, saturating at two instead of ranking geometric errors.

    Fixed source-side subsets account for exact zero tips. For each cyclic
    orientation a small dynamic program permits contiguous split coedges and
    an initial group continued at the end. Counts saturate at two; any ambiguity
    remains unresolved. Endpoint evidence still only prepares queries and never
    grants whole-edge or filled-domain acceptance. Every state visits the shared
    caller checkpoint; no independent search or resource reserve is introduced.
    Explicit finite-bridge patterns prepare queries only; the caller must bound
    actual junctions against all omitted source corners before using them.
    """

    polygon: MaterialPolygon
    candidates: tuple[tuple[BoundarySide, ...], ...]
    checkpoint: InitVar[Callable[[], None]]
    policy: BoundaryTraversalPolicy = BoundaryTraversalPolicy.COMPLETE
    junctions: BoundaryCycleJunctions | None = None
    assignment_count: int = field(init=False)
    unique_assignment: tuple[BoundarySide, ...] | None = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Enumerate only fixed polygon patterns and count bounded-state paths without nearest-error choices.
        """
        checkpoint()
        if not isinstance(self.policy, BoundaryTraversalPolicy):
            raise ValueError("An explicit source boundary traversal policy required")
        if self.junctions is not None and (
            self.junctions.polygon is not self.polygon
            or len(self.junctions.points) != len(self.candidates)
        ):
            raise ValueError("The SAME polygon and every actual boundary junction required")
        if not self.candidates or any(
            any(not isinstance(side, BoundarySide) for side in row) or len(set(row)) != len(row)
            for row in self.candidates
        ):
            raise ValueError(
                "Nonempty ordered endpoint candidate sets without duplicate labels required"
            )
        patterns: set[tuple[BoundarySide, ...]] = set()
        for mask in range(16):
            row = tuple(side for i, side in enumerate(ORDER) if mask & (1 << i))
            try:
                if self.policy is BoundaryTraversalPolicy.COMPLETE:
                    self.polygon.validate_sides(row)
                else:
                    BoundaryTraversal(self.polygon, row, self.policy, checkpoint)
            except ValueError:
                continue
            for i in range(len(row)):
                rotated = row[i:] + row[:i]
                patterns.add(rotated)
                patterns.add(tuple(reversed(rotated)))
        total = 0
        unique = None
        for pattern in sorted(patterns, key=lambda row: tuple(side.value for side in row)):
            checkpoint()
            if pattern[0] not in self.candidates[0]:
                continue
            traversal = (
                None
                if self.junctions is None
                else BoundaryTraversal(self.polygon, pattern, self.policy, checkpoint)
            )
            extended = pattern + (pattern[0],)
            states = {0: (1, (pattern[0],))}
            for position, allowed in enumerate(self.candidates[1:], start=1):
                following: dict[int, tuple[int, tuple[BoundarySide, ...]]] = {}
                for index, (count, path) in states.items():
                    checkpoint()
                    for target in (index, index + 1):
                        if target >= len(extended) or extended[target] not in allowed:
                            continue
                        if self.junctions is not None:
                            assert traversal is not None
                            if not self.junctions.allows(
                                traversal,
                                extended[index],
                                extended[target],
                                position - 1,
                                checkpoint,
                            ):
                                continue
                        old = following.get(target)
                        following[target] = (
                            (count, path + (extended[target],))
                            if old is None
                            else (min(2, old[0] + count), old[1])
                        )
                states = following
            for index in (len(pattern) - 1, len(pattern)):
                if index in states:
                    if self.junctions is not None:
                        assert traversal is not None
                        if not self.junctions.allows(
                            traversal,
                            extended[index],
                            pattern[0],
                            len(self.candidates) - 1,
                            checkpoint,
                        ):
                            continue
                    count, path = states[index]
                    total = min(2, total + count)
                    unique = path if total == 1 else None
        object.__setattr__(self, "assignment_count", total)
        object.__setattr__(self, "unique_assignment", unique)
        checkpoint()
