"""
Bind a shared material cap and bound adjacent overlap outside a finite cap collar.

This does not accept contact inside that collar, establish native seam ownership,
or glue two material maps. Those remain separate complete-output requirements.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .contact_cell import BendPreparation
from .flat_chart import FlatChart, FlatRegion, MaterialCut
from .global_chart import cross
from .volume_field import BendVolume, Point


def _dot(first: Point, second: Point) -> Fraction:
    """
    Project exact three-dimensional coefficients without unit-normal rounding.
    """
    return sum((a * b for a, b in zip(first, second)), Fraction(0))


@dataclass(frozen=True)
class BendCapCollar:
    """
    Preserve original shared labels and explicit limits of the adjacent-interior evidence.

    Positive rates and cap projection spread prove that any coincident points
    of the two complete regions must lie within BOTH reported longitudinal
    material collars. The unresolved collar is retained, not exempted or passed.
    """

    chart: FlatChart
    volume: BendVolume
    axis: Point
    cap_position_upper_mm: Fraction
    cap_projection_spread: tuple[Fraction, Fraction]
    flat_projection_rate: Fraction
    bend_phase_projection_rate: Fraction | None
    flat_collar_mm: Fraction | None
    bend_collar_mm: Fraction | None
    status: str


def certify_bend_cap(
    chart: FlatChart,
    checkpoint: Callable[[], None],
    *,
    preparation: BendPreparation | None = None,
) -> BendCapCollar:
    """
    Prove whole-volume separation outside a bounded collar at an original bend/flat cap.

    The flat cap is an exact plane in its original q/b coordinates. Relative
    bend projection is bounded below by m times distance in global phase using
    EVERY original tensor coefficient, including full width and thickness.
    At coincident world points the two outward distances' projected sum cannot
    exceed the captured cap's projection offset. Dividing by their positive
    rates gives physical material-distance bounds without normalizing the axis.

    Matching cap positions and collars use the shared inclusive0.01mm policy.
    Failure of a conservative bound is unresolved, not a penetration witness.
    """
    checkpoint()
    if not isinstance(chart.source, BendVolume) or chart.region not in (
        FlatRegion.BEFORE,
        FlatRegion.AFTER,
    ):
        raise ValueError("An original before/after chart of the SAME canonical bend required")
    volume = chart.source
    if preparation is None:
        preparation = BendPreparation(volume)
    elif preparation.region is not volume:
        raise ValueError("Preparation must own the SAME original canonical bend")
    entry = chart.region is FlatRegion.BEFORE
    cut = chart.high if entry else chart.low
    breaks = volume.source.surface.basis.breaks
    expected_cut = MaterialCut(
        volume.before_mm
        if entry
        else volume.before_mm + volume.radius_mm * breaks[-1] / volume.cosine,
        -volume.sine / volume.cosine,
    )
    if breaks[0] != 0 or cut != expected_cut:
        raise ValueError("The original zero-based phase and shared material cut required")
    along, transverse, thickness = chart.columns
    cap_transverse = tuple(q + s * cut.slope for q, s in zip(transverse, along))
    axis = cross(
        (cap_transverse[0], cap_transverse[1], cap_transverse[2]),
        (thickness[0], thickness[1], thickness[2]),
    )
    rate = _dot(axis, along)
    if rate < 0:
        axis, rate = tuple(-x for x in axis), -rate
    cap_origin = tuple(o + a * cut.offset for o, a in zip(chart.origin, along))
    plane = _dot(axis, cap_origin)
    last = len(volume.source.spans) - 1
    cap_index, endpoint = (0, 0) if entry else (last, 5)
    cap = volume.source.spans[cap_index][endpoint]
    cap_normal = preparation.normal(cap_index, checkpoint)[endpoint]
    half, reach = volume.source.half_mm, volume.half_thickness_mm
    cap_offsets = []
    cap_error = Fraction(0)
    for j in range(3):
        q = -half + half * j
        for b in (-reach, reach):
            actual = tuple(cap[j][k] + b * cap_normal[k] for k in range(3))
            expected = tuple(
                cap_origin[k] + q * cap_transverse[k] + b * thickness[k] for k in range(3)
            )
            cap_error = max(
                cap_error, sum((abs(a - z) for a, z in zip(actual, expected)), Fraction(0))
            )
            cap_offsets.append(_dot(axis, actual) - plane)
    spread = min(cap_offsets), max(cap_offsets)

    def receipt(status: str, progress_rate: Fraction | None = None) -> BendCapCollar:
        """
        Retain uncertainty whenever orientation, cap correspondence or positive progress is absent.
        """
        flat_bound = bend_bound = None
        if rate > 0 and progress_rate is not None and progress_rate > 0:
            overlap = max(Fraction(0), -spread[0] if entry else spread[1])
            flat_bound = overlap / rate
            bend_bound = overlap * volume.radius_mm / (progress_rate * volume.cosine)
        return BendCapCollar(
            chart,
            volume,
            axis,
            cap_error,
            spread,
            rate,
            progress_rate,
            flat_bound,
            bend_bound,
            status,
        )

    if rate <= 0:
        return receipt("unresolved_flat_cap_orientation")
    if cap_error > Fraction(1, 100):
        return receipt("unresolved_cap_correspondence")
    theta = breaks[-1]
    direction = 1 if entry else -1
    minimum = None
    for index, net in enumerate(volume.source.spans):
        checkpoint()
        normals = preparation.normal(index, checkpoint)
        low, high = breaks[index : index + 2]
        for i in range(6):
            phase = low + (high - low) * Fraction(i, 5)
            distance = phase - breaks[0] if entry else theta - phase
            for j in range(3):
                for b in (-reach, reach):
                    delta = tuple(
                        net[i][j][k] + b * normals[i][k] - cap[j][k] - b * cap_normal[k]
                        for k in range(3)
                    )
                    value = direction * _dot(axis, delta)
                    if distance == 0:
                        if value < 0:
                            return receipt("unresolved_cap_projection_boundary")
                        continue
                    coefficient = value / distance
                    minimum = coefficient if minimum is None else min(minimum, coefficient)
    if minimum is None or minimum <= 0:
        return receipt("unresolved_bend_projection_progress", minimum)
    result = receipt("certified_material_cap_collar", minimum)
    if result.flat_collar_mm is None or result.bend_collar_mm is None:
        raise RuntimeError("Positive projection rates must produce both material collar bounds")
    if max(result.flat_collar_mm, result.bend_collar_mm) > Fraction(1, 100):
        return receipt("unresolved_material_cap_collar", minimum)
    return result
