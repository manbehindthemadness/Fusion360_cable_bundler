"""
Splice boundary-closed local material while retaining explicit unchanged-piece lineage.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps

EventId = tuple[int, int]


def events(route: FoldRoute) -> int:
    """
    Count actual bend primitives, independently of primitive indices and straight slots.
    """
    return sum(isinstance(piece.geometry, CylindricalFold) for piece in route.pieces)


@dataclass(frozen=True)
class Window:
    """
    Keep one closed local boundary contract and its exact parent interval.
    """

    source: FoldRoute
    begin: int
    end: int

    def __post_init__(self) -> None:
        """
        Reject missing or malformed intervals before interpreting either boundary frame.
        """
        if (
            type(self.begin) is not int
            or type(self.end) is not int
            or not 0 <= self.begin < self.end <= len(self.source.pieces)
        ):
            raise ValueError("Use one nonempty ordered material window")

    @property
    def route(self) -> FoldRoute:
        """
        Freeze actual entry and exit frames, retaining profile and radius floor.
        """
        pieces = self.source.pieces[self.begin : self.end]
        first, last = pieces[0].pose, pieces[-1].end_pose()
        target = replace(
            Targets.capture(self.source.targets),
            start=first.origin,
            start_tangent=first.tangent,
            start_width=first.width,
            end=last.origin,
            end_tangent=last.tangent,
            end_width=last.width,
        )
        return FoldRoute(target, pieces, self.source.radius_mm)

    def splice(self, local: FoldRoute) -> FoldRoute:
        """
        Require actual ordered local caps before preserving every outer piece by identity.
        """
        target = self.route.targets
        if local.targets != target or not ordered_mating_caps(local.pieces, target):
            raise ValueError("Adaptive window lost its fixed ordered boundary poses")
        if local.radius_mm != self.source.radius_mm:
            raise ValueError("Adaptive window changed the radius floor")
        pieces = self.source.pieces[: self.begin] + local.pieces + self.source.pieces[self.end :]
        return FoldRoute(self.source.targets, pieces, self.source.radius_mm)


def select(route: FoldRoute, members: tuple[int, ...]) -> Window:
    """
    Choose a small incident fold pair with the most existing adjacent straight workspace.

    This is a deterministic structural choice, not a bank of geometry trials.
    The local constructor stays bounded while the parent may have any event count.
    """
    if not members or any(type(i) is not int or not 0 <= i < len(route.pieces) for i in members):
        raise ValueError("Select existing witnessed material members")
    folds = [i for i, p in enumerate(route.pieces) if isinstance(p.geometry, CylindricalFold)]
    candidates: set[tuple[int, int]] = set()
    for member in members:
        if not folds:
            candidates.add((member, member + 1))
            continue
        if member in folds:
            ordinal = folds.index(member)
            pairs = [(max(0, ordinal - 1), ordinal), (ordinal, min(len(folds) - 1, ordinal + 1))]
        else:
            before = [i for i, index in enumerate(folds) if index < member]
            after = [i for i, index in enumerate(folds) if index > member]
            left = before[-1] if before else 0
            right = after[0] if after else len(folds) - 1
            if left == right and len(folds) > 1:
                left, right = (0, 1) if not before else (len(folds) - 2, len(folds) - 1)
            pairs = [(left, right)]
        for left, right in pairs:
            begin, end = folds[left], folds[right] + 1
            if begin and isinstance(route.pieces[begin - 1].geometry, Straight):
                begin -= 1
            if end < len(route.pieces) and isinstance(route.pieces[end].geometry, Straight):
                end += 1
            if begin <= member < end:
                candidates.add((begin, end))
    begin, end = min(
        candidates,
        key=lambda interval: (
            -sum(
                p.geometry.material_length_mm
                for p in route.pieces[interval[0] : interval[1]]
                if isinstance(p.geometry, Straight)
            ),
            interval,
        ),
    )
    return Window(route, begin, end)


@dataclass(frozen=True)
class Edit:
    """
    Permit undo only while the complete inserted ID range survives unchanged and contiguous.
    """

    children: tuple[EventId, ...]
    parents: tuple[EventId, ...]
    original: tuple[PlacedPiece, ...]
    replacement: tuple[PlacedPiece, ...]

    def undo(
        self, route: FoldRoute, lineage: tuple[EventId, ...]
    ) -> tuple[FoldRoute, tuple[EventId, ...]] | None:
        """
        Decline overlapping later rewrites instead of guessing a shifted material index.
        """
        if len(lineage) != len(route.pieces) or len(set(lineage)) != len(lineage):
            raise ValueError("Require one unique identity per actual material piece")
        if not self.children or self.children[0] not in lineage:
            return None
        begin = lineage.index(self.children[0])
        end = begin + len(self.children)
        if (
            lineage[begin:end] != self.children
            or len(self.replacement) != len(self.children)
            or any(a is not b for a, b in zip(route.pieces[begin:end], self.replacement))
        ):
            return None
        return (
            FoldRoute(
                route.targets,
                route.pieces[:begin] + self.original + route.pieces[end:],
                route.radius_mm,
            ),
            lineage[:begin] + self.parents + lineage[end:],
        )
