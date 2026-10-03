"""
Read the open Macaroni v1 design without changing Fusion geometry.

Run through Fusion ``Python.Run``. The ignored JSON report records the
sketch primitives, sweep references, and resulting body's basic topology.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler


def _point(point: object) -> list[float] | None:
    """
    Convert a Fusion point into millimetres, retaining its three axes.
    """
    if point is None:
        return None
    return [round(float(getattr(point, axis)) * 10.0, 6) for axis in ("x", "y", "z")]


def _safe_property(value: object, name: str) -> object:
    """
    Read an optional Fusion API property; report unsupported ones explicitly.

    Fusion's Python bindings expose properties that can raise when the
    feature type does not support them, so this reflective diagnostic treats
    each property independently and never mutates the target object.
    """
    try:
        return getattr(value, name)
    except Exception as error:  # Intentional read-only API capability probe.
        return f"unavailable: {type(error).__name__}: {error}"


def _geometry(curve: object) -> dict[str, object]:
    """
    Capture one curve's local geometry and world-space sketch endpoints.
    """
    geometry = _safe_property(curve, "geometry")
    result: dict[str, object] = {
        "object_type": str(_safe_property(curve, "objectType")),
        "is_construction": bool(_safe_property(curve, "isConstruction")),
    }
    if isinstance(geometry, str):
        result["geometry_error"] = geometry
        return result
    for name in ("center", "startPoint", "endPoint"):
        value = _safe_property(geometry, name)
        if not isinstance(value, str) and value is not None:
            result[f"{name}_mm"] = _point(value)
    for name in ("radius", "majorRadius", "minorRadius", "startAngle", "endAngle"):
        value = _safe_property(geometry, name)
        if isinstance(value, (int, float)):
            result[name] = float(value) * (10.0 if "Radius" in name or name == "radius" else 1.0)
    for name in ("startSketchPoint", "endSketchPoint"):
        sketch_point = _safe_property(curve, name)
        if not isinstance(sketch_point, str) and sketch_point is not None:
            point = _safe_property(sketch_point, "worldGeometry")
            if not isinstance(point, str):
                result[f"{name}_mm"] = _point(point)
    return result


def _sketch(sketch: adsk.fusion.Sketch) -> dict[str, object]:
    """
    Inventory visible and construction sketch geometry without editing it.
    """
    curves = sketch.sketchCurves
    groups = (
        ("lines", curves.sketchLines),
        ("circles", curves.sketchCircles),
        ("arcs", curves.sketchArcs),
        ("ellipses", curves.sketchEllipses),
        ("fitted_splines", curves.sketchFittedSplines),
        ("control_splines", curves.sketchControlPointSplines),
    )
    result: dict[str, object] = {
        "name": sketch.name,
        "profiles": sketch.profiles.count,
        "origin_mm": _point(sketch.origin),
        "curves": {},
    }
    for name, collection in groups:
        result["curves"][name] = [
            _geometry(collection.item(index)) for index in range(collection.count)
        ]
    return result


def _feature(feature: adsk.fusion.SweepFeature) -> dict[str, object]:
    """
    Record sweep settings and the referred path/profile objects when exposed.
    """
    result: dict[str, object] = {"name": feature.name, "is_valid": feature.isValid}
    for name in ("twistAngle", "taperAngle", "orientation", "operation", "distance"):
        value = _safe_property(feature, name)
        expression = _safe_property(value, "expression") if not isinstance(value, str) else value
        result[name] = str(
            expression
            if not isinstance(expression, str) or not expression.startswith("unavailable:")
            else value
        )
    for name in ("profile", "path", "guideRail"):
        value = _safe_property(feature, name)
        result[f"{name}_type"] = str(_safe_property(value, "objectType"))
        if name == "path" and not isinstance(value, str):
            count = _safe_property(value, "count")
            result["path_count"] = count if isinstance(count, int) else str(count)
    result["body_count"] = feature.bodies.count
    return result


def run(_context: object) -> None:
    """
    Inspect only the active Macaroni document and write an ignored report.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.name != "Macaroni v1":
        raise RuntimeError("Open and activate Macaroni v1 before inspecting it.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Macaroni v1 is not an active Fusion design.")
    root = design.rootComponent
    modified_before = document.isModified
    report: dict[str, object] = {
        "document": document.name,
        "modified_before": modified_before,
        "sketches": [_sketch(root.sketches.item(index)) for index in range(root.sketches.count)],
        "sweeps": [
            _feature(root.features.sweepFeatures.item(index))
            for index in range(root.features.sweepFeatures.count)
        ],
        "bodies": [
            {
                "name": root.bRepBodies.item(index).name,
                "is_solid": root.bRepBodies.item(index).isSolid,
                "is_valid": root.bRepBodies.item(index).isValid,
                "volume_cm3": root.bRepBodies.item(index).volume,
                "face_count": root.bRepBodies.item(index).faces.count,
                "edge_count": root.bRepBodies.item(index).edges.count,
                "bounds_min_mm": _point(root.bRepBodies.item(index).boundingBox.minPoint),
                "bounds_max_mm": _point(root.bRepBodies.item(index).boundingBox.maxPoint),
            }
            for index in range(root.bRepBodies.count)
        ],
        "modified_after": document.isModified,
    }
    project_root = Path(cable_bundler.__file__).resolve().parents[1]
    output = project_root / "artifacts/verification/macaroni_document_inspect.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "MACARONI_DOCUMENT_INSPECT="
        + json.dumps(
            {
                "document": document.name,
                "sketches": len(report["sketches"]),
                "sweeps": len(report["sweeps"]),
                "bodies": len(report["bodies"]),
                "modified_before": modified_before,
                "modified_after": document.isModified,
                "report": str(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
