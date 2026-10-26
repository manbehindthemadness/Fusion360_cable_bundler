"""
Freeze shared numerical/visual evidence from an explicitly supplied candidate.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Callable

from .contracts import RibbonPath, TargetPose, Targets
from .provenance import mark_loaded, verify_loaded
from .regions import Region, Series, measure, summary
from .traces import TracePath, trace


@dataclass(frozen=True)
class Candidate:
    """
    Identify a stable path and fixed targets with caller-supplied source provenance.

    The caller must keep the path unchanged until analyze returns. Source is a
    descriptive revision/input token,not a verified physical or source certificate.
    """

    identifier: str
    path: RibbonPath
    targets: TargetPose
    source: str
    primary: str = "material J"


@dataclass(frozen=True)
class Evidence:
    """
    Store one immutable snapshot consumed by both Fusion graphics and inspection.
    """

    identifier: str
    source: str
    targets: Targets
    primary: str
    series: tuple[Series, ...]
    regions: tuple[Region, ...]
    guides: tuple[TracePath, ...]
    analysis_seconds: float
    guide_seconds: float
    fingerprint: str

    def inspect(
        self, *, kind: str | None = None, trace_number: int | None = None
    ) -> dict[str, object]:
        """
        Return the same filtered intervals/extrema represented by the scene.
        """
        series = tuple(
            s
            for s in self.series
            if (kind is None or s.kind == kind)
            and (trace_number is None or s.trace == trace_number)
        )
        findings = tuple(
            r
            for r in self.regions
            if (kind is None or r.kind == kind)
            and (trace_number is None or r.trace == trace_number)
        )
        return {
            "identifier": self.identifier,
            "source": self.source,
            "fingerprint": self.fingerprint,
            **summary(series, findings),
        }


def freeze(
    candidate: Candidate,
    series: tuple[Series, ...],
    findings: tuple[Region, ...],
    *,
    analysis_seconds: float = 0.0,
) -> Evidence:
    """
    Copy fixed inputs and guide cubics without retaining the mutable solver object.

    Used by the historical renderer adapter for already measured series. It does
    not claim those measurements were independently verified against this path.
    """
    if (
        not isinstance(candidate.identifier, str)
        or not candidate.identifier.strip()
        or not isinstance(candidate.source, str)
        or not candidate.source.strip()
    ):
        raise ValueError("Candidate identity and source provenance must be nonempty.")
    if candidate.primary not in ("center macaroni", "material J"):
        raise ValueError("Choose center macaroni or material J as the primary graph.")
    targets = Targets.capture(candidate.targets)
    field = candidate.path.field
    if (
        field.lines != targets.lines
        or field.diameter_mm != targets.diameter_mm
        or not math.isfinite(field.half_width_mm)
        or field.half_width_mm <= 0
    ):
        raise ValueError("Path dimensions must match fixed targets and finite material width.")
    started = perf_counter()
    guides = tuple(
        trace(candidate.path, number, offset)
        for number, offset in ((-1, field.half_width_mm), (0, 0.0), (-2, -field.half_width_mm))
    )
    guide_seconds = perf_counter() - started
    digest = hashlib.sha256(
        json.dumps(
            {
                "id": candidate.identifier,
                "source": candidate.source,
                "targets": asdict(targets),
                "primary": candidate.primary,
            },
            sort_keys=True,
            allow_nan=False,
        ).encode()
    )
    for row in series:
        digest.update(
            json.dumps(
                (row.kind, row.trace, row.offset_mm, row.limit, row.direction, row.amber_margin),
                allow_nan=False,
            ).encode()
        )
        for sample in row.samples:
            digest.update(
                struct.pack(
                    "<6d",
                    sample.u,
                    sample.point.x,
                    sample.point.y,
                    sample.point.z,
                    sample.value or 0.0,
                    float(sample.value is not None),
                )
            )
    for guide in guides:
        for point in guide.controls:
            if not all(math.isfinite(v) for v in (point.x, point.y, point.z)):
                raise ValueError("Guide controls must be finite;check actual lane derivatives.")
            digest.update(struct.pack("<3d", point.x, point.y, point.z))
    return Evidence(
        candidate.identifier,
        candidate.source,
        targets,
        candidate.primary,
        series,
        findings,
        guides,
        analysis_seconds,
        guide_seconds,
        digest.hexdigest(),
    )


def analyze(
    candidate: Candidate, checkpoint: Callable[[], None] = lambda: None, *, intervals: int = 512
) -> Evidence:
    """
    Measure a stable candidate once;freeze all scene data for later shared inspection.

    Existing prototype center.8/lane3D/J>0policies remain reference-model checks.
    No searches,native construction,repair,contact or continuous certificate.
    """
    verify_loaded()
    # Validate fixed inputs before allocating the station arrays.
    Targets.capture(candidate.targets)
    if (
        candidate.path.field.lines != candidate.targets.lines
        or candidate.path.field.diameter_mm != candidate.targets.diameter_mm
    ):
        raise ValueError("Path dimensions differ from the fixed targets.")
    started = perf_counter()
    series, findings = measure(candidate.path, checkpoint, intervals)
    seconds = perf_counter() - started
    checkpoint()
    return freeze(candidate, series, findings, analysis_seconds=seconds)


mark_loaded(__file__)
