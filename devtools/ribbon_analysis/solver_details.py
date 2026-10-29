"""
Keep solver metadata and gauges directly inside their experiment as visible sketches.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Callable, Protocol

# noinspection PyUnresolvedReferences
import adsk.core

from cable_bundler.routing.geometry import Vector3

from .constraint_geometry import Overlay
from .provenance import mark_loaded

_GROUP = "RibbonAnalysisSolverDetails"


class DetailSource(Protocol):
    """
    Identify frozen detail metadata without requiring an intrinsic ribbon model.
    """

    @property
    def identifier(self) -> str:
        """
        Identify the selected frozen geometry and numerical disposition.
        """
        ...

    @property
    def fingerprint(self) -> str:
        """
        Address the exact displayed source/settings/measurement snapshot.
        """
        ...


def _point(sketch: Any, point: Vector3) -> Any:
    """
    Convert component-local millimeters to native sketch coordinates.
    """
    return sketch.modelToSketchSpace(
        adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)
    )


def retain_solver_details(
    component: Any,
    evidence: DetailSource,
    overlay: Overlay,
    checkpoint: Callable[[], None] = lambda: None,
    *,
    text_scale: float = 1.0,
) -> Any:
    """
    Retain one initially visible solver-details sketch in its owner.

    Keep full measurements/source snapshot as attributes and native gauge lines
    plus readable sketch text. Reuse complete matching sketches without changing
    user visibility; partial work requires review instead of automatic retries.
    """
    if overlay.key != "solver_limits":
        raise ValueError("Only solver restrictions belong in the solver-details sketch.")
    if not 0 < text_scale <= 1:
        raise ValueError("Solver detail text scale must be within (0,1].")
    payload: dict[str, Any] = {
        "evidence": evidence.fingerprint,
        "overlay": asdict(overlay),
        "layout_version": 2,
    }
    if text_scale != 1:
        payload["text_scale"] = text_scale
    snapshot = json.dumps(
        payload,
        sort_keys=True,
        allow_nan=False,
    )
    digest = hashlib.sha256(snapshot.encode()).hexdigest()
    matches = []
    for sketch in component.sketches:
        stamp = sketch.attributes.itemByName(_GROUP, "fingerprint")
        if stamp is not None and stamp.value == digest:
            matches.append(sketch)
    if len(matches) > 1:
        raise RuntimeError("Duplicate solver-detail sketches require review.")
    if matches:
        if matches[0].attributes.itemByName(_GROUP, "complete") is None:
            raise RuntimeError("Incomplete solver-detail sketch requires review.")
        return matches[0]
    checkpoint()
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = f"{evidence.identifier} - Solver details"
    sketch.isLightBulbOn = True
    sketch.attributes.add(_GROUP, "fingerprint", digest)
    sketch.attributes.add(_GROUP, "snapshot", snapshot)
    sketch.isComputeDeferred = True
    try:
        for stroke in overlay.strokes:
            checkpoint()
            for first, last in zip(stroke.points, stroke.points[1:]):
                line = sketch.sketchCurves.sketchLines.addByTwoPoints(
                    _point(sketch, first), _point(sketch, last)
                )
                if line is None:
                    raise RuntimeError("Solver gauge line creation failed.")
                line.isConstruction = True
        captions = ((overlay.title, 2.0, 2.0),) + tuple(
            (note, 5.0 + i * 3, 1.7) for i, note in enumerate(overlay.notes)
        )
        for note, offset, height in captions:
            checkpoint()
            offset, height = offset * text_scale, height * text_scale
            # Literal text is an expression in Fusion's current Sketch Text API.
            expression = "'" + note.replace("\\", "\\\\").replace("'", "\\'") + "'"
            text_input = sketch.sketchTexts.createInput3(
                expression, adsk.core.ValueInput.createByReal(height / 10)
            )
            if text_input is None:
                raise RuntimeError("Solver-detail text input failed.")
            anchor = overlay.anchor.translated(Vector3(0, -1, 0), offset)
            low = _point(sketch, anchor.translated(Vector3(0, -1, 0), height))
            high = _point(
                sketch,
                anchor.translated(Vector3(1, 0, 0), max(30, len(note) * height)).translated(
                    Vector3(0, 1, 0), 1
                ),
            )
            if not text_input.setAsMultiLine(
                low,
                high,
                adsk.core.HorizontalAlignments.LeftHorizontalAlignment,
                adsk.core.VerticalAlignments.TopVerticalAlignment,
                0,
            ):
                raise RuntimeError("Solver-detail text placement failed.")
            if sketch.sketchTexts.add(text_input) is None:
                raise RuntimeError("Solver-detail text creation failed.")
    finally:
        sketch.isComputeDeferred = False
    sketch.attributes.add(_GROUP, "complete", "true")
    return sketch


mark_loaded(__file__)
