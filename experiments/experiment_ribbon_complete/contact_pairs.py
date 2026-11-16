"""
Traverse actual canonical material boxes with one bounded positive-contact allocation.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from cable_bundler.routing.geometry import Vector3, cross
from experiments.experiment_ribbon_fold_route.contact_bounds import Span

from .contact_cell import ContactCell, enclose, separated
from .contact_junction_binding import CapJunctionEvidence
from .contact_profile_cover import ProfileSupportCover


@dataclass
class ContactWork:
    """
    Debit every visited pair from one caller allocation without a renewal or refund.
    """

    maximum_pairs: int
    checkpoint: Callable[[], None]
    used_pairs: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """
        Require an explicit positive pair ceiling no larger than the shared2048 limit.
        """
        if type(self.maximum_pairs) is not int or not 1 <= self.maximum_pairs <= 2048:
            raise ValueError("A fixed pair allocation in1..2048 required")

    def claim(self) -> bool:
        """
        Check caller resources even when no pair allocation remains.
        """
        self.checkpoint()
        if self.used_pairs >= self.maximum_pairs:
            return False
        self.used_pairs += 1
        return True


@dataclass(frozen=True)
class PairEvidence:
    """
    Retain original pair ownership and conservative disposition after bounded traversal.
    """

    first: ContactCell
    second: ContactCell
    status: str
    visited: int
    separated_leaves: int
    pending_pairs: int
    junction: CapJunctionEvidence | None = None


def proposals(first: ContactCell, second: ContactCell) -> tuple[Vector3, ...]:
    """
    Choose global, cell-frame and center-difference axes without granting geometric authority.
    """
    centers = []
    for cell in (first, second):
        coordinates = tuple((s.low + s.high) / 2 for s in (cell.box.u, cell.box.q, cell.box.height))
        centers.append(
            Vector3(
                *(
                    getattr(cell.model.origin, k)
                    + sum(getattr(c, k) * x for c, x in zip(cell.model.columns, coordinates))
                    for k in "xyz"
                )
            )
        )
    a, b = centers
    axes = [
        Vector3(b.x - a.x, b.y - a.y, b.z - a.z),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
    ]
    for cell in (first, second):
        x, y, z = cell.model.columns
        axes.extend((cross(x, y), cross(y, z), cross(z, x)))
    return tuple(Vector3(sign * n.x, sign * n.y, sign * n.z) for n in axes for sign in (1, -1))


def children(cell: ContactCell, checkpoint: Callable[[], None]) -> tuple[ContactCell, ...]:
    """
    Bisect the largest physical affine extent without discarding any original material box.
    """
    spans = cell.box.u, cell.box.q, cell.box.height
    sizes = tuple(
        (s.high - s.low) * math.hypot(c.x, c.y, c.z) for s, c in zip(spans, cell.model.columns)
    )
    axis = max(range(3), key=lambda i: sizes[i])
    span = spans[axis]
    middle = span.low / 2 + span.high / 2
    if not span.low < middle < span.high:
        return ()
    output = []
    for part in (Span(span.low, middle), Span(middle, span.high)):
        selected = list(spans)
        selected[axis] = part
        box = replace(
            cell.box, u=selected[0], q=selected[1], height=selected[2], depth=cell.box.depth + 1
        )
        output.append(enclose(cell.region, box, checkpoint, preparation=cell.preparation))
    return tuple(output)


def inspect_pair(
    first: ContactCell,
    second: ContactCell,
    profile: ProfileSupportCover,
    work: ContactWork,
    maximum_depth: int = 6,
    *,
    junction: CapJunctionEvidence | None = None,
) -> PairEvidence:
    """
    Prove separation only when every covering leaf pair has a strict support gap.

    A limit or unseparated terminal leaf leaves the original pair unresolved.
    No inverse witness, adjacency exemption or sampled absence grants acceptance.
    Caller resource exceptions propagate, and all work uses the same allocation.
    Qualified junction evidence is retained after the initial whole-pair support
    query as unresolved_material_cap_collar, with one pending whole pair. It
    cannot grant separation, omit adjacent interiors or renew the work budget.
    """
    if type(maximum_depth) is not int or not 0 <= maximum_depth <= 6:
        raise ValueError("Explicit subdivision depth in0..6 required")
    if junction is not None and (
        junction.first is not first
        or junction.second is not second
        or junction.profile is not profile
    ):
        raise ValueError("Junction evidence must own the SAME original cells and profile")
    initial = work.used_pairs
    pending = [(first, second)]
    cleared = 0
    status = "certified_separated"
    while pending:
        if not work.claim():
            status = "unresolved_pair_limit"
            break
        a, b = pending.pop()
        clear = False
        for normal in proposals(a, b):
            work.checkpoint()
            if separated(a, b, profile, normal, a.model.origin):
                clear = True
                break
        if clear:
            cleared += 1
            continue
        if junction is not None:
            return PairEvidence(
                first,
                second,
                "unresolved_material_cap_collar",
                work.used_pairs - initial,
                cleared,
                1,
                junction,
            )
        if min(a.box.depth, b.box.depth) >= maximum_depth:
            pending.append((a, b))
            status = "unresolved_depth"
            break
        first_size = max(
            (s.high - s.low) * math.hypot(c.x, c.y, c.z)
            for s, c in zip((a.box.u, a.box.q, a.box.height), a.model.columns)
        )
        second_size = max(
            (s.high - s.low) * math.hypot(c.x, c.y, c.z)
            for s, c in zip((b.box.u, b.box.q, b.box.height), b.model.columns)
        )
        split_first = (
            first_size >= second_size and a.box.depth < maximum_depth
        ) or b.box.depth >= maximum_depth
        divided = children(a if split_first else b, work.checkpoint)
        if not divided:
            pending.append((a, b))
            status = "unresolved_unsplittable"
            break
        pending.extend((part, b) if split_first else (a, part) for part in divided)
    return PairEvidence(
        first, second, status, work.used_pairs - initial, cleared, len(pending), junction
    )
