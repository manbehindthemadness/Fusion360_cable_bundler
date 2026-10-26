"""
Locate sampled intervals of reference-field failures for humans and agents alike.

These intrinsic measurements do not inspect native sweeps or certify continuous
geometry. Visuals must consume the same series and regions as the structured view.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3

from .contracts import RibbonPath as DirectorPath
from .provenance import mark_loaded


@dataclass(frozen=True)
class Sample:
    """
    Retain one material station, world-space point and optional valid measurement.
    """

    u: float
    point: Vector3
    value: float | None


@dataclass(frozen=True)
class Series:
    """
    Identify an ordered material path and an existing policy or model condition.

    Upper limits fail strictly above the limit. Lower limits fail at or below it.
    The amber margin is a display aid, never a relaxed acceptance threshold.
    """

    kind: str
    trace: int
    offset_mm: float
    limit: float
    direction: str
    amber_margin: float
    samples: tuple[Sample, ...]

    def severity(self, index: int) -> str:
        """
        Classify one measured sample without turning unavailable values into passes.
        """
        value = self.samples[index].value
        if value is None:
            return "unmeasured"
        if self.direction == "upper":
            return (
                "red"
                if value > self.limit
                else ("amber" if value >= self.limit - self.amber_margin else "blue")
            )
        return (
            "red"
            if value <= self.limit
            else ("amber" if value <= self.limit + self.amber_margin else "blue")
        )


@dataclass(frozen=True)
class Region:
    """
    Retain a contiguous run of sampled findings and unresolved crossing brackets.

    Entry/exit brackets bound adjacent classifications, not certified roots. A
    missing bracket means the region reaches the sampled domain boundary.
    """

    kind: str
    trace: int
    offset_mm: float
    severity: str
    first_index: int
    last_index: int
    first_u: float
    last_u: float
    entry_bracket: tuple[float, float] | None
    exit_bracket: tuple[float, float] | None
    worst_u: float
    worst_value: float
    worst_point: Vector3
    limit: float


def regions(series: Series) -> tuple[Region, ...]:
    """
    Extract disjoint red and amber sample runs with exact provenance to the series.
    """
    if series.direction not in ("upper", "lower") or not series.samples:
        raise ValueError("Expected a nonempty series with an upper or lower limit.")
    if (
        not math.isfinite(series.limit)
        or not math.isfinite(series.amber_margin)
        or series.amber_margin < 0
    ):
        raise ValueError("Series limits/margins must be finite and nonnegative margins.")
    if any(
        not math.isfinite(s.u)
        or not 0 <= s.u <= 1
        or (s.value is not None and not math.isfinite(s.value))
        or not all(math.isfinite(v) for v in (s.point.x, s.point.y, s.point.z))
        for s in series.samples
    ):
        raise ValueError("Station fractions,positions and available values must be finite.")
    if any(a.u >= b.u for a, b in zip(series.samples, series.samples[1:])):
        raise ValueError("Material samples must be strictly ordered.")
    found: list[Region] = []
    i = 0
    while i < len(series.samples):
        severity = series.severity(i)
        if severity not in ("red", "amber"):
            i += 1
            continue
        first = i
        while i + 1 < len(series.samples) and series.severity(i + 1) == severity:
            i += 1
        last = i
        measured = [s for s in series.samples[first : last + 1] if s.value is not None]
        worst = (
            max(measured, key=lambda s: float(s.value) if s.value is not None else -math.inf)
            if series.direction == "upper"
            else min(measured, key=lambda s: float(s.value) if s.value is not None else math.inf)
        )
        assert worst.value is not None
        found.append(
            Region(
                series.kind,
                series.trace,
                series.offset_mm,
                severity,
                first,
                last,
                series.samples[first].u,
                series.samples[last].u,
                (series.samples[first - 1].u, series.samples[first].u) if first else None,
                (series.samples[last].u, series.samples[last + 1].u)
                if last + 1 < len(series.samples)
                else None,
                worst.u,
                worst.value,
                worst.point,
                series.limit,
            )
        )
        i += 1
    return tuple(found)


def measure(
    path: DirectorPath, checkpoint: Callable[[], None], intervals: int = 512
) -> tuple[tuple[Series, ...], tuple[Region, ...]]:
    """
    Sample center macaroni, material J and regular-lane curvature at fixed stations.

    Lane curvature k/J is an intrinsic-model formula only while J>0; unavailable
    elsewhere. No native interpolation, contact, containment or cap audit occurs.
    """
    if isinstance(intervals, bool) or not isinstance(intervals, int) or not 16 <= intervals <= 1024:
        raise ValueError("Use16..1024bounded analysis intervals.")
    field = path.field
    diameter, half = field.diameter_mm, field.half_width_mm
    reach = math.hypot(half, diameter / 2)
    offsets = ((-1, half), (-2, -half)) + tuple(
        (i + 1, (i - (field.lines - 1) / 2) * diameter) for i in range(field.lines)
    )
    center_samples: list[Sample] = []
    jacobians: dict[int, list[Sample]] = {number: [] for number, _ in offsets}
    curvature: dict[int, list[Sample]] = {number: [] for number, _ in offsets}
    for i in range(intervals + 1):
        if i % 64 == 0:
            checkpoint()
        u = i / intervals
        k, _, eta_s = field.sample(u)
        center_samples.append(Sample(u, path.lane(u, 0)[0], abs(k) * reach))
        for number, q in offsets:
            point = path.lane(u, q)[0]
            jac = 1 + q * eta_s
            jacobians[number].append(Sample(u, point, jac))
            curvature[number].append(
                Sample(u, point, 3 * diameter * abs(k) / jac if jac > 1e-9 else None)
            )
    series = [Series("center macaroni", 0, 0, 0.8, "upper", 0.08, tuple(center_samples))]
    for number, q in offsets:
        series.extend(
            (
                Series("material J", number, q, 0.0, "lower", 0.1, tuple(jacobians[number])),
                Series(
                    "lane curvature x 3D", number, q, 1.0, "upper", 0.1, tuple(curvature[number])
                ),
            )
        )
    return tuple(series), tuple(r for row in series for r in regions(row))


def summary(series: tuple[Series, ...], findings: tuple[Region, ...]) -> dict[str, object]:
    """
    Give agents the same thresholds, intervals and witnesses displayed to the user.
    """
    return {
        "red_kinds": sorted({r.kind for r in findings if r.severity == "red"}),
        "amber_kinds": sorted({r.kind for r in findings if r.severity == "amber"}),
        "regions": [asdict(r) for r in findings],
        "unmeasured_samples": sum(s.value is None for row in series for s in row.samples),
        "series_extrema": [_extrema(row) for row in series],
        "scope": "sampled reference fields;not a native or complete physical certificate",
        "interpretation": {
            "center macaroni": "Curvature times enclosing profile reach;investigate distributing bend over more material length while retaining targets.",
            "lane curvature x 3D": "Regular modeled lane radius below3diameters;investigate local radius and ruling-gradient concentration together.",
            "material J": "J=1+q*eta_s;zero compresses stations to a singular map,negative reverses material order. Investigate ruling derivative or available run length,not a graphics-frame flip.",
        },
    }


def _extrema(row: Series) -> dict[str, object]:
    """
    Preserve useful measurements even for a baseline with no colored findings.
    """
    measured = [s for s in row.samples if s.value is not None]
    low = (
        min(measured, key=lambda s: s.value if s.value is not None else math.inf)
        if measured
        else None
    )
    high = (
        max(measured, key=lambda s: s.value if s.value is not None else -math.inf)
        if measured
        else None
    )
    return {
        "kind": row.kind,
        "trace": row.trace,
        "offset_mm": row.offset_mm,
        "limit": row.limit,
        "direction": row.direction,
        "minimum": asdict(low) if low is not None else None,
        "maximum": asdict(high) if high is not None else None,
        "measured_samples": len(measured),
        "total_samples": len(row.samples),
    }


mark_loaded(__file__)
