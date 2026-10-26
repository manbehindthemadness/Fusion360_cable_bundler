"""
Screen sampled complete rulings for remote material approaching within thickness.

Each ruling spans the full ribbon width. Longitudinal sampling and a deliberately
excluded local material neighborhood prevent this from being a surface certificate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

# noinspection PyProtectedMember
from cable_bundler.routing.avoidance import _segment_distance
from cable_bundler.routing.geometry import Vector3, magnitude

from .edge_first import EdgeCandidate, frame


@dataclass(frozen=True)
class Ruling:
    """
    Pair one spatial width segment with its unfolded material coordinates.

    Fractions run from permanent boundary A to B. All coordinates use millimeters.
    """

    fraction: float
    start: Vector3
    end: Vector3
    flat_start: Vector3
    flat_end: Vector3


def rulings(
    candidate: EdgeCandidate, stations: int, checkpoint: Callable[[], None]
) -> tuple[Ruling, ...]:
    """
    Sample a regular candidate,integrating boundary arc length by composite Simpson.

    Boundary-first flat coordinates are(x,q)=(arc_A+q*eta,q). Cached controls
    have eta=0 and use their existing material-length parameter. Reject failed
    compatibility or unsupported counts;never reconstruct or repair a candidate.
    """
    if not candidate.companion_allowed:
        raise ValueError("Clearance requires the prior material compatibility gate.")
    if isinstance(stations, bool) or stations not in (129, 257):
        raise ValueError("Use a registered129or257ruling diagnostic.")
    half = candidate.case.lines * candidate.case.diameter_mm / 2 + candidate.case.diameter_mm * 0.1
    result: list[Ruling] = []
    arc, previous_speed = 0.0, 0.0
    for i in range(stations):
        if i % 32 == 0:
            checkpoint()
        fraction = i / (stations - 1)
        if candidate.curve is not None:
            observed = frame(candidate.curve, fraction)
            if min(1.0, 1 - 2 * half * observed.slope_rate / observed.speed) <= 0:
                raise ValueError("Material regularity failed at a clearance station.")
            if i:
                middle = (i - 0.5) / (stations - 1)
                middle_speed = magnitude(candidate.curve.jet(middle)[1])
                arc += (previous_speed + 4 * middle_speed + observed.speed) / (6 * (stations - 1))
            previous_speed = observed.speed
            start, end = observed.position, observed.lane(-2 * half)[0]
            flat_start = Vector3(arc, 0, 0)
            flat_end = Vector3(arc - 2 * half * observed.slope, -2 * half, 0)
        elif candidate.retained_control is not None:
            strip = candidate.retained_control.strip
            # These retained planar controls have zero ruling slope throughout.
            if any(span.start_slope or span.end_slope for span in strip.spans):
                raise ValueError("Only cached zero-slope controls are registered here.")
            arc = fraction * strip.length_mm
            start, end = strip.jet(arc, half)[0], strip.jet(arc, -half)[0]
            flat_start, flat_end = Vector3(arc, half, 0), Vector3(arc, -half, 0)
        else:
            raise ValueError("Missing retained ribbon geometry.")
        result.append(Ruling(fraction, start, end, flat_start, flat_end))
    return tuple(result)


def screen(
    samples: tuple[Ruling, ...], thickness_mm: float, checkpoint: Callable[[], None]
) -> dict[str, Any]:
    """
    Find full-width ruling pairs closer than thickness outside a local flat zone.

    Exclude pairs whose unfolded segments approach within3thicknesses. Search
    spatial distances below2thicknesses using exact segment distances and AABB
    rejection. These exclusions can miss contacts: report them and never claim
    continuous surface or native-thickness clearance. Retain the closest eligible
    witness inside the search horizon and completed counters,not all pair records.
    """
    if not math.isfinite(thickness_mm) or thickness_mm <= 0:
        raise ValueError("Clearance thickness must be finite and positive.")
    horizon, local = 2 * thickness_mm, 3 * thickness_mm
    bounds: list[tuple[tuple[float, float], ...]] = [
        tuple(
            (
                min(float(getattr(s.start, a)), float(getattr(s.end, a))),
                max(float(getattr(s.start, a)), float(getattr(s.end, a))),
            )
            for a in ("x", "y", "z")
        )
        for s in samples
    ]
    pairs = broad_rejected = local_excluded = eligible = contacts = 0
    closest, witness = horizon, None
    started = perf_counter()
    for i, left in enumerate(samples):
        if i % 16 == 0:
            checkpoint()
        for j in range(i + 1, len(samples)):
            pairs += 1
            if any(max(a[0] - b[1], b[0] - a[1]) > horizon for a, b in zip(bounds[i], bounds[j])):
                broad_rejected += 1
                continue
            right = samples[j]
            distance, p, q = _segment_distance(left.start, left.end, right.start, right.end)
            if distance >= horizon:
                continue
            material, _, _ = _segment_distance(
                left.flat_start, left.flat_end, right.flat_start, right.flat_end
            )
            if material <= local:
                local_excluded += 1
                continue
            eligible += 1
            if distance < thickness_mm:
                contacts += 1
            if distance < closest:
                closest = distance
                witness = {
                    "stations": (i, j),
                    "fractions": (left.fraction, right.fraction),
                    "distance_mm": distance,
                    "flat_segment_distance_mm": material,
                    "points_mm": ((p.x, p.y, p.z), (q.x, q.y, q.z)),
                }
    return {
        "stations": len(samples),
        "pairs": pairs,
        "aabb_rejected": broad_rejected,
        "local_pairs_excluded": local_excluded,
        "eligible_near_pairs": eligible,
        "contact_pairs": contacts,
        "witness": witness,
        "search_horizon_mm": horizon,
        "local_exclusion_mm": local,
        "minimum_within_horizon_mm": closest if witness else None,
        "contact_detected": contacts > 0,
        "pair_seconds": perf_counter() - started,
    }


def audit(
    candidate: EdgeCandidate, stations: int, checkpoint: Callable[[], None]
) -> dict[str, Any]:
    """
    Measure sampling and pair work separately without mutating the input geometry.
    """
    started = perf_counter()
    samples = rulings(candidate, stations, checkpoint)
    sampling_seconds = perf_counter() - started
    result = screen(samples, candidate.case.diameter_mm, checkpoint)
    result.update(
        sampling_seconds=sampling_seconds,
        total_seconds=perf_counter() - started,
        integrated_boundary_length_mm=samples[-1].flat_start.x,
    )
    return result
