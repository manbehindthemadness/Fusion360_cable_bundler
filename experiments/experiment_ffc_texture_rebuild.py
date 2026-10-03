"""
Compare textured, section-valid one-face FFC sweeps across fresh builds.

Run with Fusion ``Python.Run`` while the user's textured FFC scratch is active
and no command is running. The source is only inspected; a new unsaved design
is created and left open. This does not edit/regenerate a production route.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_ffc_spline_seam import _case


def _source_texture(
    design: adsk.fusion.Design,
) -> tuple[adsk.core.Appearance | None, dict[str, object] | None]:
    """
    Find the first textured body or face appearance in the active design.
    """
    for index in range(design.rootComponent.bRepBodies.count):
        body = design.rootComponent.bRepBodies.item(index)
        candidates = [body, *(body.faces.item(face) for face in range(body.faces.count))]
        for candidate in candidates:
            appearance = candidate.appearance
            if appearance is not None and appearance.hasTexture:
                return appearance, _map_report(body)
    return None, None


def _map_report(body: adsk.fusion.BRepBody) -> dict[str, object] | None:
    """
    Record the body's texture projection without modifying its settings.
    """
    control = body.textureMapControl
    if control is None:
        return None
    row: dict[str, object] = {"type": control.objectType}
    projected = adsk.core.ProjectedTextureMapControl.cast(control)
    if projected is not None:
        row["projection"] = str(projected.projectedTextureMapType)
        row["transform"] = list(projected.transform.asArray())
    return row


def _side_face(body: adsk.fusion.BRepBody) -> adsk.fusion.BRepFace:
    """
    Select the single three-edge swept side, excluding the one-edge caps.
    """
    sides = [
        body.faces.item(index)
        for index in range(body.faces.count)
        if body.faces.item(index).edges.count == 3
    ]
    if len(sides) != 1:
        raise RuntimeError(f"Expected one three-edge FFC side face; found {len(sides)}.")
    return sides[0]


def _mesh_samples(face: adsk.fusion.BRepFace, offset_y_cm: float) -> dict[str, object]:
    """
    Read rendered mesh UVs paired with offset-normalized model coordinates.

    Surface parameters and appearance mapping are not assumed equivalent;
    these are the UVs reported by Fusion's display mesh itself.
    """
    manager = face.meshManager
    meshes = manager.displayMeshes
    if meshes.count == 0:
        calculator = manager.createMeshCalculator()
        mesh = calculator.calculate()
    else:
        mesh = meshes.item(0)
    if mesh is None:
        raise RuntimeError("Fusion did not provide an FFC side-face mesh.")
    positions = mesh.nodeCoordinates
    coordinates = mesh.textureCoordinates
    if len(coordinates) != len(positions):
        raise RuntimeError("Side-face mesh nodes and texture coordinates differ in count.")
    samples = [
        (
            round(point.x, 7),
            round(point.y - offset_y_cm, 7),
            round(point.z, 7),
            round(uv.x, 7),
            round(uv.y, 7),
        )
        for point, uv in zip(positions, coordinates)
    ]
    samples.sort(key=lambda sample: sample[:3])
    return {"nodes": len(samples), "samples": samples}


def _compare_meshes(first: dict[str, object], second: dict[str, object]) -> dict[str, object]:
    """
    Compare UVs only when both rebuilds yielded matching local mesh nodes.
    """
    left = first["samples"]
    right = second["samples"]
    if len(left) != len(right):
        return {"comparable": False, "reason": "node counts differ"}
    max_position_delta_cm = max(
        (max(abs(a[index] - b[index]) for index in range(3)) for a, b in zip(left, right)),
        default=0.0,
    )
    if max_position_delta_cm > 0.0001:
        return {
            "comparable": False,
            "reason": "local mesh positions differ",
            "max_position_delta_cm": max_position_delta_cm,
            "first_samples": [left[0], right[0]],
        }
    return {
        "comparable": True,
        "nodes": len(left),
        "max_position_delta_cm": max_position_delta_cm,
        "max_u_delta": max((abs(a[3] - b[3]) for a, b in zip(left, right)), default=0.0),
        "max_v_delta": max((abs(a[4] - b[4]) for a, b in zip(left, right)), default=0.0),
    }


def run(_context: object) -> None:
    """
    Rebuild two section-valid FFC cases in a new, retained Fusion scratch.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    source = application.activeDocument
    source_modified_before = source.isModified
    source_design = adsk.fusion.Design.cast(application.activeProduct)
    if source_design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    texture, source_map = _source_texture(source_design)
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the texture-rebuild scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The new scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    copied_texture = (
        design.appearances.addByCopy(texture, "FFC texture rebuild probe")
        if texture is not None
        else None
    )
    results: list[dict[str, object]] = []
    for lines, separation in ((3, 10.0), (5, 20.0)):
        attempts: list[dict[str, object]] = []
        meshes: list[dict[str, object]] = []
        for repeat in range(2):
            offset_y_cm = (len(results) * 2 + repeat) * 8.0
            row = _case(design.rootComponent, lines, separation, 180.0, offset_y_cm)
            if row["result"] != "solid" or row["midpoint_section"]["wire_count"] != 1:
                raise RuntimeError(f"FFC {lines}-trace build did not pass its section check.")
            features = design.rootComponent.features.sweepFeatures
            body = features.item(features.count - 1).bodies.item(0)
            if copied_texture is not None:
                body.appearance = copied_texture
            side = _side_face(body)
            mesh = _mesh_samples(side, offset_y_cm)
            attempts.append(
                {
                    "repeat": repeat,
                    "offset_y_cm": offset_y_cm,
                    "geometry": row,
                    "mesh_nodes": mesh["nodes"],
                    "texture_map": _map_report(body),
                }
            )
            meshes.append(mesh)
        results.append(
            {
                "lines": lines,
                "separation_mm": separation,
                "attempts": attempts,
                "mesh_comparison": _compare_meshes(*meshes),
            }
        )
    application.activeViewport.fit()
    report = {
        "source_document": source.name,
        "source_modified_before": source_modified_before,
        "source_modified_after": source.isModified,
        "texture_found": texture is not None,
        "texture_name": texture.name if texture is not None else None,
        "source_texture_map": source_map,
        "texture_copied": copied_texture is not None,
        "scratch_document": scratch.name,
        "results": results,
    }
    root_path = Path(cable_bundler.__file__).resolve().parents[1]
    output = root_path / "artifacts/verification/ffc_texture_rebuild.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "FFC_TEXTURE_REBUILD="
        + json.dumps(
            {
                "cases": len(results),
                "texture_found": texture is not None,
                "mesh_comparable": [result["mesh_comparison"]["comparable"] for result in results],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
