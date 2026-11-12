"""
Share negative discovery between moved and retained material without transferring clearance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, Iterator, Sequence

from experiments.experiment_ribbon_feature_insertion.separation import Region, Side
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_plane import SignedJoints
from .flat_separation import FlatSeparation
from .material_constraint import MaterialConstraint
from .material_pose import current_regions
from .motion_order import motion_priority

Pair = tuple[int, int]


class FocusKind(Enum):
    """
    Identify ordering guidance without implying a contact measurement or certificate.
    """

    EXPLICIT = "explicit"
    RETAINED = "retained"
    MOTION = "motion"
    COMBINED = "combined"


@dataclass(frozen=True)
class MaterialFocus:
    """
    Bind a duplicate-free discovery prefix to one exact immutable current route.

    This stores ordering only. Known material pairs still need new strict inverse
    tests at this pose, and no omitted phase, clearance or acceptance follows.
    """

    source: FoldRoute
    priority: tuple[Pair, ...]
    known_pairs: frozenset[Pair] = frozenset()
    kind: FocusKind = FocusKind.EXPLICIT

    def __post_init__(self) -> None:
        """
        Reject invented, adjacent, duplicated or unordered original pair identities.
        """
        if (
            not isinstance(self.priority, tuple)
            or any(
                not isinstance(pair, tuple)
                or len(pair) != 2
                or any(type(index) is not int for index in pair)
                or not (0 <= pair[0] and pair[0] + 2 <= pair[1] < len(self.source.pieces))
                for pair in self.priority
            )
            or len(set(self.priority)) != len(self.priority)
            or not isinstance(self.known_pairs, frozenset)
            or not self.known_pairs.issubset(self.priority)
            or not isinstance(self.kind, FocusKind)
        ):
            raise ValueError("Use unique ordered nonadjacent pairs of the current route")

    @classmethod
    def from_motion(
        cls,
        route: FoldRoute,
        model: SignedJoints,
        values: tuple[float, ...],
        checkpoint: Callable[[], None],
    ) -> MaterialFocus | None:
        """
        Focus actual moved material without requiring a previously known crossing.

        Sampled proximity proposes ordering only; it transfers no old witness or
        clearance. Missing or stale current identity leaves the global order.
        """
        priority = motion_priority(route, model, values, checkpoint)
        return cls(route, priority, kind=FocusKind.MOTION) if priority else None

    @classmethod
    def for_correction(
        cls,
        route: FoldRoute,
        model: SignedJoints,
        values: tuple[float, ...],
        constraints: Sequence[tuple[FlatSeparation | MaterialConstraint, Side]],
        checkpoint: Callable[[], None],
    ) -> MaterialFocus | None:
        """
        Share the discovery prefix between actual motion and retained local material.

        Discovering a constraint must not suppress motion elsewhere. Alternate
        unknown motion and retained pairs, motion first, skipping duplicates and
        deferring known pairs. Bound the combined prefix to the existing32pool;
        every omitted pair remains eligible in the untouched global remainder.
        This gives ordering opportunities, not per-pair support or timing guarantees.
        """
        retained = (
            cls.from_constraints(route, model, values, constraints, checkpoint)
            if constraints
            else None
        )
        motion = cls.from_motion(route, model, values, checkpoint)
        if retained is None:
            return motion
        if motion is None:
            return retained
        known = retained.known_pairs
        priority: list[Pair] = []
        seen: set[Pair] = set()
        streams = [iter(motion.priority), iter(retained.priority)]
        while streams:
            for stream in streams[:]:
                for pair in stream:
                    checkpoint()
                    if pair in known or pair in seen:
                        continue
                    priority.append(pair)
                    seen.add(pair)
                    break
                else:
                    streams.remove(stream)
                if len(priority) == 32:
                    return cls(route, tuple(priority), kind=FocusKind.COMBINED)
        for pair in retained.priority:
            checkpoint()
            if pair in known:
                priority.append(pair)
                if len(priority) == 32:
                    break
        selected_known = known.intersection(priority)
        return cls(route, tuple(priority), selected_known, FocusKind.COMBINED)

    @classmethod
    def from_constraints(
        cls,
        route: FoldRoute,
        model: SignedJoints,
        values: tuple[float, ...],
        constraints: Iterable[tuple[FlatSeparation | MaterialConstraint, Side]],
        checkpoint: Callable[[], None],
    ) -> MaterialFocus | None:
        """
        Resolve model-owned stable regions at the exact working pose before choosing any prefix.

        Include each witnessed event interval's complete bends and boundary
        runways. Merge only ranges sharing actual material; absent boundary slots
        cannot bridge disjoint ranges. Prefer new local pairs, then known local
        pairs. Missing or unsupported guidance supplies no guessed neighborhood.
        Preparation performs no geometry proposal or contact comparison, and its
        checkpoints keep all ordering cost inside the caller's existing clocks.
        """
        checkpoint()
        tags = current_regions(route, model, values)
        if tags is None:
            return None
        locations = {tag: index for index, tag in enumerate(tags)}
        windows: list[tuple[int, int]] = []
        known: set[Pair] = set()
        for bound, _ in constraints:
            checkpoint()
            owner = (
                getattr(bound, "bound", None) if isinstance(bound, MaterialConstraint) else bound
            )
            if getattr(owner, "model", None) is not model:
                continue
            pair = getattr(owner, "pair", None)
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or any(
                    not isinstance(tag, Region)
                    or type(tag.fold) is not int
                    or tag.fold < 0
                    or type(tag.straight) is not bool
                    or tag not in locations
                    for tag in pair
                )
            ):
                continue
            first, second = (locations[tag] for tag in pair)
            if first >= second:
                continue
            low = min(tag.fold for tag in pair)
            high = max(tag.fold + int(not tag.straight) for tag in pair)
            members = []
            for index, tag in enumerate(tags):
                checkpoint()
                in_window = low <= tag.fold and (
                    tag.fold <= high if tag.straight else tag.fold < high
                )
                if in_window:
                    members.append(index)
            if members:
                windows.append((members[0], members[-1] + 1))
                known.add((first, second))
        merged: list[tuple[int, int]] = []
        for start, end in sorted(windows):
            checkpoint()
            if merged and start < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        new_pairs: list[Pair] = []
        known_pairs: list[Pair] = []
        for start, end in merged:
            for first in range(start, end):
                for second in range(first + 2, end):
                    checkpoint()
                    pair = (first, second)
                    (known_pairs if pair in known else new_pairs).append(pair)
        priority = tuple(new_pairs + known_pairs)
        checkpoint()
        return (
            cls(route, priority, frozenset(known_pairs), FocusKind.RETAINED) if priority else None
        )


def ordered_pairs(
    route: FoldRoute, focus: MaterialFocus | None, checkpoint: Callable[[], None]
) -> Iterator[Pair]:
    """
    Visit each original nonadjacent pair once, retaining the global order after the local prefix.

    A stale or equivalent copied route cannot inherit another object's prefix.
    Ordering never filters a pair or changes the screen's comparison allowance.
    """
    priority = focus.priority if focus is not None and focus.source is route else ()
    seen = set(priority)
    for pair in priority:
        checkpoint()
        yield pair
    for first in range(len(route.pieces)):
        for second in range(first + 2, len(route.pieces)):
            checkpoint()
            if (first, second) not in seen:
                yield first, second
