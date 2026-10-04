"""
Render a diagnostic image on both production-profile lofts in the open scratch.

Run through the local Fusion script runner after the 19-line controlled loft
comparison. This changes only the active unsaved experiment design, applies
the same image/scale policy to both lofts, and leaves the document open.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.cable_solid_parts.one_face_texture import (
    UV_SCALE_CM_PER_UNIT,
    _png_row,
)

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/production_loft_pattern"
SOURCE_APPEARANCE_LIBRARY = "BA5EE55E-9982-449B-9D66-9F036540E140"
SOURCE_APPEARANCE_ID = "Prism-129"
EXPECTED_NAMES = (
    "Production loft · Discrete · valid control",
    "Production loft · FFC · valid control",
)


def _image_row() -> bytes:
    """
    Encode one repeated, phase-marked transverse color pattern.
    """
    colors = ((255, 28, 28), (20, 230, 45), (30, 80, 255), (255, 220, 10))
    row = bytearray()
    for pixel in range(4096):
        band = pixel // 1024
        color = (0, 0, 0) if pixel % 1024 < 24 else colors[band]
        row.extend(color)
    return _png_row(bytes(row))


def _side_face_span(face: adsk.fusion.BRepFace) -> float:
    """
    Read Fusion's rendered transverse coordinate extent for one side face.
    """
    meshes = face.meshManager.displayMeshes
    if not meshes.count:
        raise RuntimeError("Fusion has not rendered a loft side-face mesh.")
    coordinates = meshes.item(0).textureCoordinates
    if not coordinates:
        raise RuntimeError("Fusion rendered a loft face without texture coordinates.")
    values = tuple(float(uv.x) for uv in coordinates)
    span = max(values) - min(values)
    if span <= 1e-6:
        raise RuntimeError("Fusion rendered a degenerate loft transverse UV span.")
    return span


def _case(
    design: adsk.fusion.Design,
    component: adsk.fusion.Component,
    source: adsk.core.Appearance,
    image: Path,
) -> dict[str, object]:
    """
    Apply one shared texture to every side face of one control loft.
    """
    lofts = component.features.loftFeatures
    if lofts.count != 1:
        raise RuntimeError(f"Expected one production loft in {component.name}.")
    feature = lofts.item(0)
    if feature.bodies.count != 1 or not feature.bodies.item(0).isSolid:
        raise RuntimeError(f"Expected one solid loft body in {component.name}.")
    faces = tuple(feature.sideFaces.item(index) for index in range(feature.sideFaces.count))
    spans = tuple(_side_face_span(face) for face in faces)
    median_span = statistics.median(spans)
    broad_span = max(spans)
    name = f"UV pattern · {component.name}"
    appearance = design.appearances.itemByName(name)
    if appearance is None:
        appearance = design.appearances.addByCopy(source, name)
    if appearance is None:
        raise RuntimeError("Fusion could not copy the diagnostic appearance.")
    appearance.colorTexture = str(image)
    slot = appearance.appearanceProperties.itemById("opaque_albedo")
    texture = None if slot is None else slot.connectedTexture
    if texture is None:
        raise RuntimeError("Fusion did not connect the diagnostic image.")
    scale = texture.properties.itemById("texture_RealWorldScaleX")
    offset = texture.properties.itemById("texture_RealWorldOffsetX")
    repeat = texture.properties.itemById("texture_URepeat")
    if scale is None or offset is None or repeat is None:
        raise RuntimeError("Fusion did not expose the required texture controls.")
    scale.value = UV_SCALE_CM_PER_UNIT * broad_span
    offset.value = 0.0
    repeat.value = True
    for face in faces:
        face.appearance = appearance
    return {
        "component": component.name,
        "side_faces": len(faces),
        "textured_faces": sum(
            face.appearance is not None and face.appearance.name == appearance.name
            for face in faces
        ),
        "appearance": appearance.name,
        "image": str(image),
        "u_span_min": min(spans),
        "u_span_median": median_span,
        "u_span_max": max(spans),
        "scale_basis": "maximum rendered side-face U span",
        "scale_cm": scale.value,
        "offset_cm": offset.value,
        "repeat_u": repeat.value,
    }


def run(_context: object) -> None:
    """
    Texture both lofts and capture Fusion's actual top and bottom rendering.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved controlled-loft scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    components = tuple(
        design.rootComponent.occurrences.item(index).component
        for index in range(design.rootComponent.occurrences.count)
    )
    if len(components) != 2 or {item.name for item in components} != set(EXPECTED_NAMES):
        raise RuntimeError("The active scratch is not the side-by-side control loft design.")
    library = application.materialLibraries.itemById(SOURCE_APPEARANCE_LIBRARY)
    source = None if library is None else library.appearances.itemById(SOURCE_APPEARANCE_ID)
    if source is None:
        raise RuntimeError("Fusion's generic opaque appearance is unavailable.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image = OUTPUT / "uv_quarters.png"
    image.write_bytes(_image_row())
    cases = tuple(_case(design, component, source, image) for component in components)
    viewport = application.activeViewport
    captures: dict[str, str] = {}
    for label, direction in (("top", 1.0), ("bottom", -1.0)):
        camera = viewport.camera
        camera.target = adsk.core.Point3D.create(5.5, 2.0, 0.0)
        camera.eye = adsk.core.Point3D.create(5.5, 2.0, 30.0 * direction)
        camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
        camera.viewExtents = 16.0
        viewport.camera = camera
        viewport.refresh()
        capture = OUTPUT / f"{label}.png"
        if not viewport.saveAsImageFile(str(capture), 0, 0):
            raise RuntimeError(f"Fusion could not capture the {label} rendering.")
        captures[label] = str(capture)
    report = OUTPUT / "report.json"
    report.write_text(
        json.dumps({"document": document.name, "cases": cases, "captures": captures}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(
        "PRODUCTION_LOFT_RENDERED_PATTERN="
        + json.dumps({"report": str(report), "captures": captures})
    )


if __name__ == "__main__":
    run(None)
