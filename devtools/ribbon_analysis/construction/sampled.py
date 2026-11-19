"""
Adapt the existing application ribbon shape to shared diagnostic display records.
"""

from __future__ import annotations

from cable_bundler.routing.ribbon_shape import RibbonShape

from .journal import Journal


def capture_shape(journal: Journal, shape: RibbonShape, identity: str) -> None:
    """
    Show available sampled frames and final lanes without inventing internal fold events.

    This read-only adapter leaves the production solver unchanged. For actual
    intermediate decisions a caller must emit stages while they occur; a final
    sampled shape cannot recover an original primitive-construction history.
    """
    if len(shape.frames) > 1024 or len(shape.lanes) > 64:
        raise ValueError("Sampled ribbon display exceeds1024frames/64lanes")
    journal.define(
        identity,
        identity,
        "sampled ribbon",
        (),
        "cable_bundler/routing/ribbon_shape.py:RibbonShape",
    )
    centers = [[f.origin.x, f.origin.y, f.origin.z] for f in shape.frames]
    if len(centers) < 2:
        raise ValueError("Sampled shape requires at least two frames")
    base = {
        "feature": identity,
        "space": "world",
        "paths": [centers],
        "frame": None,
        "material_mm": None,
        "details": {"frame_count": len(shape.frames)},
    }
    journal.emit(
        "placement", "Available route-frame center samples", "reference", "observed", [base]
    )
    journal.emit(
        "primitive",
        "Internal primitive and fold decisions were not recorded",
        "unavailable",
        "unavailable",
        [],
        {
            "reason": "Final RibbonShape stores sampled frames/lanes, not a construction event journal."
        },
    )
    result = {
        **base,
        "paths": [[[p.x, p.y, p.z] for p in lane] for lane in shape.lanes],
        "details": {
            "lengths_mm": shape.lengths_mm,
            "spread": shape.spread,
            "folded": shape.folded,
            "physical_qualification": "not established by display",
        },
    }
    journal.emit(
        "output",
        "Existing solver output: sampled conductor geometry",
        "unresolved",
        "observed",
        [result],
    )
