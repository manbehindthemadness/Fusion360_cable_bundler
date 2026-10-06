"""
Append rigid specimens to a six-slot array while closing only archived owned scratch.
"""

from __future__ import annotations

from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_diagnosis.storage import archive

from .array_display import copy_bodies
from .native_budget import NativeBudget

ARRAY_NAME = "Tube ribbon 4x - absolute-faith certificate array"


def _document(name: str) -> adsk.core.Document:
    """
    Resolve exactly one document by its registered owned name without broad matching.
    """
    matches = [
        document for document in adsk.core.Application.get().documents if document.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError("Owned document missing or ambiguous: " + name)
    return matches[0]


def start_array(budget: NativeBudget) -> None:
    """
    Create one unsaved direct-design result while leaving user documents untouched.
    """
    app = adsk.core.Application.get()
    if str(app.userInterface.activeCommand) != "SelectCommand" or any(
        d.name in (ARRAY_NAME, ARRAY_NAME + " v1") for d in app.documents
    ):
        raise RuntimeError("Array exists or Fusion command active; no retry.")
    budget.check("array_document")
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = ARRAY_NAME
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Array design unavailable; document retained.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType


def append_and_close(
    name: str, center: Vector3, index: int, native_directory: Path, budget: NativeBudget
) -> dict[str, object]:
    """
    Copy one complete ribbon into its fixed slot, then close its archived scratch.

    Closure follows successful39-solid import only. On failure preserve documents;
    the caller records the original error and stops scheduling without a retry.
    """
    if not 0 <= index < 6 or not (native_directory / "calibration.f3d").is_file():
        raise RuntimeError("Slot or native archive unavailable; no scratch closure.")
    source = _document(name)
    if not source.activate():
        raise RuntimeError("Source activation failed; document retained.")
    app = adsk.core.Application.get()
    source_design = adsk.fusion.Design.cast(app.activeProduct)
    if source_design is None or source_design.rootComponent.occurrences.count != 1:
        raise RuntimeError("Source calibration component missing.")
    bodies = tuple(source_design.rootComponent.occurrences.item(0).component.bRepBodies)
    if len(bodies) != 39 or not all(body.isSolid for body in bodies):
        raise RuntimeError("Incomplete native ribbon; no display import.")
    target = _document(ARRAY_NAME)
    if not target.activate():
        raise RuntimeError("Array activation failed; documents retained.")
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Array design unavailable.")
    x, y = (index % 3 - 1) * 140, (0.5 - index // 3) * 140
    transform = adsk.core.Matrix3D.create()
    for row, value in enumerate((x - center.x, y - center.y, -center.z)):
        transform.setCell(row, 3, value / 10)
    budget.check("array_component")
    occurrence = design.rootComponent.occurrences.addNewComponent(transform)
    if occurrence is None:
        raise RuntimeError("Array component unavailable; documents retained.")
    occurrence.component.name = f"{index + 1} - {name}"
    copy_bodies(bodies, occurrence.component, budget)
    budget.check("scratch_close")
    if not source.close(False):
        raise RuntimeError("Owned archived scratch did not close.")
    return {
        "source": name,
        "slot": index,
        "solids": occurrence.component.bRepBodies.count,
        "sphere_center_mm": [x, y, 0],
        "scratch_closed": True,
    }


def finish_array(directory: Path, budget: NativeBudget) -> None:
    """
    Fit, photograph and archive the result even when remaining slots were stopped.
    """
    document = _document(ARRAY_NAME)
    if not document.activate():
        raise RuntimeError("Array activation failed.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Array design unavailable.")
    budget.check("array_finish")
    camera = app.activeViewport.camera
    camera.isFitView = True
    app.activeViewport.camera = camera
    app.activeViewport.refresh()
    app.activeViewport.saveAsImageFile(str(directory / "array.png"), 1800, 1100)
    budget.check("array_archive")
    archive(design, directory / "array.f3d")
