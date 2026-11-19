"""
Declare conservative whole-material separation arrangements before straight allocation.

These affine envelopes are construction guidance. Independent occupied-material
checks still include every real piece and neighboring seam after construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_terminal_hardware.model import Hardware

from .linear import Row
from .support import Support, fold_support, outside_box, separated


@dataclass(frozen=True)
class Exclusion:
    """
    Require one alternative conjunction of halfspaces for one declared material exclusion.
    """

    name: str
    alternatives: tuple[tuple[Row, ...], ...]


def axes(first: tuple[Vector3, ...], second: tuple[Vector3, ...]) -> tuple[Vector3, ...]:
    """
    Derive nonparallel support directions from both intrinsic frames and their cross products.
    """
    result: list[Vector3] = []
    for axis in (*first, *second, *(cross(a, b) for a in first for b in second)):
        if magnitude(axis) > 1e-10:
            direction = unit(axis)
            if all(abs(dot(direction, previous)) < 1 - 1e-10 for previous in result):
                result.append(direction)
    return tuple(result)


def constraints(
    model: Model, hardware: Hardware, checkpoint: Callable[[], None]
) -> tuple[Exclusion, ...]:
    """
    Prepare hardware and nonneighbor exclusions independently of any allocated route or witness.

    Logical straights exist even at zero travel. Their two complete cap slabs
    enclose the full straight prism, and every cap bound participates in a chosen
    halfspace. Zero length introduces no actual output primitive. Immediate
    material neighbors are omitted only from this conservative construction
    relaxation, never from the independent final contact check.
    """
    if model.source.targets != hardware.targets:
        raise ValueError("Use the same immutable targets for construction and hardware")
    folds = model.pieces((0.0,) * model.size)
    count = len(folds)
    if not 1 <= count <= 6:
        raise ValueError("This construction adapter supports one to six folds")
    poses = tuple(p.pose for p in folds) + (folds[-1].end_pose(),)
    frames = tuple((p.tangent, p.width, unit(cross(p.tangent, p.width))) for p in poses)
    cache: dict[tuple[int, Vector3], tuple[Support, ...]] = {}

    def support(index: int, axis: Vector3) -> tuple[Support, ...]:
        """
        Share one fixed fold or endpoint-slab envelope within this declared problem.
        """
        key = (index, axis)
        if key in cache:
            return cache[key]
        slot = index // 2
        if index % 2:
            output = (fold_support(model, slot, axis),)
        else:
            pose = poses[slot]
            piece = PlacedPiece(pose, Straight(1.0), "analysis cap slab only")
            bound = projection(
                piece,
                Cell(
                    0,
                    Span(0, 0),
                    Span(-model.source.half_width_mm, model.source.half_width_mm),
                    Span(
                        -model.source.targets.diameter_mm / 2, model.source.targets.diameter_mm / 2
                    ),
                ),
                axis,
            )
            before = tuple(
                dot(poses[j].tangent, axis) * model.source.targets.diameter_mm if j < slot else 0.0
                for j in range(count + 1)
            )
            after = tuple(
                value
                + (dot(pose.tangent, axis) * model.source.targets.diameter_mm if j == slot else 0.0)
                for j, value in enumerate(before)
            )
            output = (
                Support(bound.low, bound.high, before, axis),
                Support(bound.low, bound.high, after, axis),
            )
        cache[key] = output
        return output

    output = []
    for index in range(2 * count + 1):
        frame = frames[index // 2]
        for box in hardware.boxes:
            checkpoint()
            options = []
            for axis in axes(frame, box.axes):
                slabs = support(index, axis)
                choices = tuple(outside_box(slab, box) for slab in slabs)
                options.extend(tuple(choice[side] for choice in choices) for side in (0, 1))
            output.append(
                Exclusion(f"part {index} versus {box.terminal.value} hardware", tuple(options))
            )
        for other in range(index + 2, 2 * count + 1):
            checkpoint()
            options = []
            for axis in axes(frame, frames[other // 2]):
                first, second = support(index, axis), support(other, axis)
                options.append(tuple(separated(a, b) for a in first for b in second))
                options.append(tuple(separated(b, a) for a in first for b in second))
            output.append(Exclusion(f"nonneighbor parts {index}/{other}", tuple(options)))
    return tuple(output)


def satisfied(group: Exclusion, values: tuple[float, ...]) -> bool:
    """
    Check the supplied arrangement numerically without granting physical clearance.
    """
    return any(
        all(
            math.fsum(a * b for a, b in zip(row.coefficients, values)) >= row.right - 1e-8
            for row in alternative
        )
        for alternative in group.alternatives
    )
