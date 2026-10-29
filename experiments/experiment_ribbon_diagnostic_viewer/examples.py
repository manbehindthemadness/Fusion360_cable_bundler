"""
Author fixed diagnostic examples independently of routing search outcomes.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from cable_bundler.routing.geometry import difference
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    snapshot_payload,
    targets_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.geometry import freeze_curve, freeze_path, local_frame
from devtools.ribbon_analysis.inspection.measurements import observations
from experiments.experiment_ribbon_cap_transition.director_fields import DirectorField
from experiments.experiment_ribbon_cap_transition.director_transport import DirectorPath, integrate
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .fixture import SpatialSBend
from .procedures import source_pins

EXAMPLES = (
    {"id": "single", "label": "Single conductor · S / lateral 90°"},
    {"id": "ribbon", "label": "Three-conductor ribbon · spatial reversal"},
)


def ribbon(checkpoint: Callable[[], None]) -> tuple[DirectorPath, EndpointCase]:
    """
    Author a spatial signed reversal with tight material guides and normal caps.

    With bend B*sin(2pi*u), ruling A*sin(2pi*u), and half-width h, lane curvature
    is |B*sin|/(L+q*2pi*A*cos). Choosing L=hypot(3D*B,h*2pi*A) makes the worst
    material-lane radius exactly3D analytically, with positive material progress.
    This is an authored reference, not a routing solution or solid-clearance proof.
    The wide-ribbon centre/edge minimum ratio and profile flex remain unresolved.
    """
    diameter, lines, amplitude, bend = 1.5, 3, 0.35, 2 * math.pi
    half = lines * diameter / 2 + diameter * 0.1
    length = math.hypot(3 * diameter * bend, half * 2 * math.pi * amplitude)
    field = DirectorField(
        "R001 three-conductor spatial reversal",
        length,
        (0, 0, bend, 0),
        (0, 0, amplitude, 0),
        lines,
        diameter,
    )
    path = integrate(field, 512, checkpoint)
    frames = []
    for u in (0.0, 1.0):
        position, velocity = path.lane(u, 0)
        across = difference(path.lane(u, half)[0], path.lane(u, -half)[0])
        frames.append(local_frame(position, velocity, across))
    start, end = frames
    targets = EndpointCase(
        field.name, start.origin, end.origin, start.z, end.z, start.x, end.x, lines, diameter
    )
    return path, targets


def create(directory: Path, identifier: str, checkpoint: Callable[[], None]) -> Path:
    """
    Freeze one declared reference in a new directory without routing or construction.
    """
    if identifier not in {item["id"] for item in EXAMPLES}:
        raise ValueError("Choose a registered diagnostic example.")
    checkpoint()
    sources = source_pins()
    directory.mkdir(parents=True, exist_ok=False)
    write_document(
        directory / "plan.json",
        {
            "question": "Author a fixed diagnostic example, without solving endpoint routing.",
            "example": identifier,
            "sources": sources,
            "definition": "SpatialSBend"
            if identifier == "single"
            else "DirectorField B=2pi*sin(2pi*u), eta=.35*sin(2pi*u), L=hypot(3D*2pi,h*2pi*.35), N=3, D=1.5mm",
            "target_radius_utilization": 1.0,
            "guide_radius_reference_diameters": 3.0,
            "scope": "Forward-authored development reference; wide-ribbon radius ratio/scalar/flex and bonded contour unresolved. No physical acceptance.",
            "limits": {"seconds": 10, "rss_kib": 4 * 1024 * 1024, "native_solid_attempts": 0},
        },
    )
    if identifier == "single":
        curve = SpatialSBend()
        targets = curve.targets()
        snapshot = freeze_curve("S001-reference", curve, 1.5)
        detail = "Original one-conductor S / lateral90. Analytic minimum centre radius=3D."
    else:
        path, targets = ribbon(checkpoint)
        snapshot = freeze_path("R001-reference", path, intervals=512, sections=33)
        detail = "Three-conductor spatial reversal. Analytic minimum material-guide radius=3D; positive material progress. Open material rulings, no invented bonded contour or conductor bodies."
    checkpoint()
    if source_pins() != sources:
        raise RuntimeError("Sources changed while authoring the example.")
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "targets": targets_payload(targets),
        "solvers": [
            {
                "id": "reference",
                "label": EXAMPLES[0 if identifier == "single" else 1]["label"],
                "status": "reference",
                "source": str(Path(__file__).resolve()),
                "detail": detail + " Fixture authoring, not solver success or physical acceptance.",
                "snapshot": snapshot_payload(snapshot),
                "rules": [asdict(rule) for rule in observations(snapshot, targets, 4.5)],
            }
        ],
    }
    destination = directory / "reference.json"
    write_document(destination, document)
    return destination
