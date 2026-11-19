"""
Join exact terminal turnarounds constrained to the open sides of their mating planes.

The guide handles define one construction, not a physical feasibility theorem.
Both cap frames and whole-material outward rows participate in the same length
allocation. Independent occupied-material and connector audits remain required.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from itertools import product
from typing import Any, Callable

from cable_bundler.routing.geometry import difference, dot, magnitude, unit
from devtools.ribbon_analysis.prepath import controls
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.guide_frames import transport
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices

from .linear import Row
from .support import fold_support


def bridge(boundary: Boundary, *, trace: Callable[[dict[str, Any]], None] | None = None) -> Pose:
    """
    Derive a common frame between outward handles without heading or roll trials.

    The endpoint chord/3 handle convention is retained from the existing guide.
    Width is the bisector of separately transported ordered terminal widths.
    Opposite transport and width ambiguities reject; no world axis resolves them.
    The returned origin is a reference, not a waypoint imposed on the ribbon.
    Optional tracing publishes computed handles/frame without changing arithmetic;
    recorder errors propagate and stop the caller rather than losing history.
    """
    target = boundary.targets
    _, departure, arrival, _ = controls(target)
    if trace is not None:
        trace({"stage": "handles", "departure": asdict(departure), "arrival": asdict(arrival)})
    displacement = difference(arrival, departure)
    if magnitude(displacement) <= 1e-10:
        raise ValueError("Outward handles do not define a bridge direction")
    tangent = unit(displacement)
    widths = (
        transport(target.start_width, target.start_tangent, tangent),
        transport(target.end_width, target.end_tangent, tangent),
    )
    mean = widths[0].translated(widths[1], 1)
    if magnitude(mean) <= 1e-10:
        raise ValueError("Opposed transported widths leave the bridge frame ambiguous")
    origin = departure.translated(displacement, 0.5)
    result = Pose(origin, tangent, unit(mean))
    if trace is not None:
        trace(
            {
                "stage": "bridge",
                "pose": asdict(result),
                "transported_widths": [asdict(value) for value in widths],
                "origin_is_reference_not_waypoint": True,
            }
        )
    return result


def chains(
    boundary: Boundary,
    checkpoint: Callable[[], None],
    *,
    trace: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Chain, ...]:
    """
    Factor both fixed terminal frames through one common outward-handle bridge.

    Retain existing exact algebraic roots and material order. No root is selected
    by a saved specimen or local fold-sign flip. Empty terminal groups and more
    than six folds remain unsupported representations, rather than fallbacks.
    Optional tracing publishes endpoint inputs, rotation factors and declared
    chains as computed; it neither supplies values nor selects roots.
    """
    target = boundary.targets
    if trace is not None:
        trace({"stage": "targets", "targets": asdict(target), "radius_mm": boundary.radius_mm})
    middle = bridge(boundary, trace=trace)
    start = Pose(target.start, target.start_tangent, target.start_width)
    end = Pose(target.end, target.end_tangent, target.end_width)
    width = 2 * boundary.half_width_mm
    first = rotation_choices(start, middle, boundary.radius_mm, width)
    if trace is not None:
        trace(
            {
                "stage": "rotation_factors",
                "terminal": "A",
                "start": asdict(start),
                "end": asdict(middle),
                "choices": [[asdict(fold) for fold in group] for group in first],
            }
        )
    last = rotation_choices(middle, end, boundary.radius_mm, width)
    if trace is not None:
        trace(
            {
                "stage": "rotation_factors",
                "terminal": "B",
                "start": asdict(middle),
                "end": asdict(end),
                "choices": [[asdict(fold) for fold in group] for group in last],
            }
        )
    if len(first) * len(last) > 8:
        raise ValueError("Terminal approach roots exceed the existing eight-root allowance")
    result = []
    for a, b in product(range(len(first)), range(len(last))):
        checkpoint()
        entry, exit_ = first[a], last[b]
        if not entry or not exit_ or len(entry) + len(exit_) > 6:
            raise ValueError(
                "Terminal approaches require two nonempty groups and at most six folds"
            )
        result.append(
            Chain(
                Topology(f"outward-{a}-{b}", entry + exit_, None),
                (len(entry),),
                (middle,),
                2,
                (a, b),
            )
        )
        if trace is not None:
            trace({"stage": "chain", "chain": asdict(result[-1])})
    return tuple(result)


def corridors(model: Model, chain: Chain, checkpoint: Callable[[], None]) -> tuple[Row, ...]:
    """
    Require each terminal group's full folds to remain outside its own mating plane.

    Departure uses +start_tangent; backward arrival uses -end_tangent, preserving
    A-to-B material order. Supports include full width and thickness, not merely
    centerlines. These conservative rows constrain construction only. Model
    closure fixes B simultaneously; no cap snapping or rigid output repair runs.
    """
    if model.topology != chain.topology or len(chain.group_ends) != 1:
        raise ValueError("Use the matching two-terminal-group construction")
    split = chain.group_ends[0]
    count = len(chain.topology.folds)
    if not 0 < split < count:
        raise ValueError("Both terminal groups must contain folds")
    target = model.source.targets
    rows = []
    for index in range(count):
        checkpoint()
        entry = index < split
        origin = target.start if entry else target.end
        axis = (
            target.start_tangent if entry else target.end_tangent.translated(target.end_tangent, -2)
        )
        support = fold_support(model, index, axis)
        rows.append(
            Row(
                f"{'start' if entry else 'end'} outward fold {index}",
                support.translation_mm,
                math.fsum((dot(origin, axis), -support.low_mm)),
            )
        )
    return tuple(rows)
