"""
Derive full-material separating-plane guidance from a currently certified configuration.

Whole-piece projections can be conservative or nonsmooth. These moving bounds
guide kinematics only; independent complete occupied-material checks remain final.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, dot, unit
from experiments.experiment_ribbon_feature_insertion.separation import Region, locate, regions
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight
from experiments.experiment_ribbon_terminal_hardware.model import Box, Hardware, Terminal

from .envelopes import axes
from .waypoints import Hinges


@dataclass(frozen=True)
class Plane:
    """
    Retain one signed full-material separation relation on a fixed intrinsic axis.
    """

    model: Hinges
    name: str
    first: Region
    second: Region | None
    box: Box | None
    axis: Vector3
    minimum_mm: float

    def span(self, piece: PlacedPiece) -> Span:
        """
        Bound the entire width, thickness and material length of a current piece.
        """
        source = self.model.original
        return projection(
            piece,
            Cell(
                0,
                Span(0, 1),
                Span(-source.half_width_mm, source.half_width_mm),
                Span(-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2),
            ),
            self.axis,
        )

    def gap_mm(self, values: tuple[float, ...]) -> float:
        """
        Re-enclose the same ordered pieces after all hinge and straight motions.
        """
        pieces = self.model.pieces(values)
        first = self.span(locate(self.model.original, pieces, self.first))
        if self.second is not None:
            second = self.span(locate(self.model.original, pieces, self.second))
            return second.low - first.high
        if self.box is None:
            raise ValueError("A plane needs either another material region or hardware")
        return first.low - max(dot(point, self.axis) for point in self.box.corners())

    def residual(self, values: tuple[float, ...]) -> float:
        """
        Express the normalized upper-bound inequality minimum-gap<=0 for joint projection.
        """
        return (self.minimum_mm - self.gap_mm(values)) / self.model.scale


@dataclass(frozen=True)
class Selection:
    """
    Report represented and omitted guidance without treating omissions as clearance.
    """

    planes: tuple[Plane, ...]
    represented: int
    unsupported: tuple[str, ...]
    capacity_omitted: tuple[str, ...]


def select(
    model: Hinges,
    hardware: Hardware,
    values: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> Selection:
    """
    Keep at most thirteen closest already-separated intrinsic material/hardware planes.

    Immediate neighbors are omitted from guidance only, never final contact.
    A baseline projection within1e-8mm below zero retains that arithmetic bound
    as its reference, rather than declaring physical penetration or extra slack.
    Larger conservative overlaps stay explicitly unsupported. The allowance is
    an internal projection-consistency guard, not physical acceptance tolerance.
    """
    if hardware.targets != model.original.targets or len(model.folds) > 6:
        raise ValueError("Use matching fixed hardware and at most six material hinges")
    route = model.route(values)
    if route is None:
        raise ValueError("Clearance guidance requires nonempty complete material")
    pieces = route.pieces
    tags = regions(route)
    frames = tuple(
        (p.pose.tangent, p.pose.width, unit(cross(p.pose.tangent, p.pose.width))) for p in pieces
    )
    candidates: list[tuple[float, Plane]] = []
    unsupported: list[str] = []

    def retain(
        name: str,
        first_index: int,
        second_index: int | None,
        obstacle: Box | None,
        candidate_axes: tuple[Vector3, ...],
    ) -> None:
        """
        Choose the largest existing signed gap without trial route or witness lookup.
        """
        choices = []
        for axis in candidate_axes:
            checkpoint()
            plane = Plane(
                model,
                name,
                tags[first_index],
                tags[second_index] if second_index is not None else None,
                obstacle,
                axis,
                0.0,
            )
            choices.append((plane.gap_mm(values), plane))
        if not choices:
            unsupported.append(name)
            return
        gap, plane = max(choices, key=lambda item: item[0])
        if gap < -1e-8:
            unsupported.append(name)
            return
        plane = Plane(model, name, plane.first, plane.second, obstacle, plane.axis, min(0.0, gap))
        candidates.append((gap, plane))

    for first, piece in enumerate(pieces):
        for box in hardware.boxes:
            own_mating = isinstance(piece.geometry, Straight) and (
                (first == 0 and box.terminal is Terminal.START)
                or (first == len(pieces) - 1 and box.terminal is Terminal.END)
            )
            directions = (
                (box.pose.tangent,)
                if own_mating
                else tuple(
                    direction.translated(direction, sign - 1)
                    for direction in axes(frames[first], box.axes)
                    for sign in (1, -1)
                )
            )
            retain(f"material {first}/{box.terminal.value} hardware", first, None, box, directions)
        for second in range(first + 2, len(pieces)):
            directions = tuple(
                direction.translated(direction, sign - 1)
                for direction in axes(frames[first], frames[second])
                for sign in (1, -1)
            )
            retain(f"material {first}/{second}", first, second, None, directions)
    ranked = sorted(candidates, key=lambda item: item[0])
    return Selection(
        tuple(plane for _, plane in ranked[:13]),
        len(candidates),
        tuple(unsupported),
        tuple(plane.name for _, plane in ranked[13:]),
    )
