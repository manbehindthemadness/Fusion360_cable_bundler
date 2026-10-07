"""
Resolve native section curves in the owned component occurrence without copying them.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    import adsk.fusion


def occurrence_curve(
    curve: adsk.fusion.SketchCurve, occurrence: adsk.fusion.Occurrence
) -> adsk.fusion.SketchCurve:
    """
    Return an explicit assembly proxy; reject missing or already-contextual inputs.

    This only resolves the entity reference. It creates no sketch, curve or feature
    and applies no geometric transform. Inputs must be native to the owned component.
    """
    if curve.assemblyContext is not None:
        raise ValueError("Expected a native section curve before applying occurrence context.")
    proxy = curve.createForAssemblyContext(occurrence)
    if proxy is None:
        raise RuntimeError("Section curve occurrence proxy unavailable.")
    return proxy


def connected_curve_order(
    curves: Iterable[adsk.fusion.SketchCurve],
) -> tuple[adsk.fusion.SketchCurve, ...]:
    """
    Order a single closed endpoint chain without modifying or reversing geometry.

    Match world-coordinate endpoints rounded to 1e-9cm for reference lookup only;
    do not snap native points. Reject branches, gaps and disconnected loops. Fusion
    Path creation can otherwise return only part of an unordered contour collection.
    """
    remaining = list(curves)
    if not remaining:
        raise ValueError("Empty contour collection.")

    def endpoints(curve: adsk.fusion.SketchCurve) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """
        Read both world endpoints without changing curve orientation.
        """
        keys = []
        for point in (curve.startSketchPoint, curve.endSketchPoint):
            world = point.worldGeometry
            keys.append((round(world.x, 9), round(world.y, 9), round(world.z, 9)))
        return keys[0], keys[1]

    ordered = [remaining.pop(0)]
    first, end = endpoints(ordered[0])
    while end != first:
        matches = [curve for curve in remaining if end in endpoints(curve)]
        if len(matches) != 1:
            raise ValueError("Contour has an ambiguous or missing endpoint connection.")
        curve = matches[0]
        remaining.remove(curve)
        ordered.append(curve)
        start, stop = endpoints(curve)
        end = stop if end == start else start
    if remaining:
        raise ValueError("Contour contains disconnected closed chains.")
    return tuple(ordered)
