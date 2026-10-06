"""
Place unchanged audited body copies side-by-side in a retained live Fusion document.

Copies are presentation workload, never new geometry validation. No source body,
user document, curve, cap, connection target or native audit evidence is changed.
"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_diagnosis.storage import archive

from .native_budget import NativeBudget

ARRAY_NAME = "Tube ribbon 4x - three-family 360 array"


def create_array(
    document_names: tuple[str, ...],
    centers: tuple[Vector3, ...],
    directory: Path,
    budget: NativeBudget,
    *,
    array_name: str = ARRAY_NAME,
) -> None:
    """
    Copy three complete 39-solid results to rigidly translated display components.

    Check time/RSS before each copy, retain all documents on any failure. Existing
    source scratch documents are read-only; no lofts/solves or extra audit claims.
    """
    started = perf_counter()
    app = adsk.core.Application.get()
    if (
        str(app.userInterface.activeCommand) != "SelectCommand"
        or len(document_names) != 3
        or len(centers) != 3
    ):
        raise RuntimeError("Three complete cases and idle Fusion are required for display.")
    if any(document.name in (array_name, array_name + " v1") for document in app.documents):
        raise RuntimeError("Array document exists; no automatic copy retry.")
    sources = []
    for name in document_names:
        matches = [document for document in app.documents if document.name == name]
        if len(matches) != 1 or not matches[0].activate():
            raise RuntimeError(
                "Array source scratch is missing or ambiguous; all documents retained."
            )
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None or design.rootComponent.occurrences.count != 1:
            raise RuntimeError("Array source must have exactly one calibration component.")
        bodies = tuple(design.rootComponent.occurrences.item(0).component.bRepBodies)
        if len(bodies) != 39 or not all(body.isSolid for body in bodies):
            raise RuntimeError("Array source is not a complete 39-solid ribbon.")
        sources.append(bodies)
    budget.check("array_document")
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = array_name
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Array design unavailable; document retained.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    manager = adsk.fusion.TemporaryBRepManager.get()
    rows = []
    for index, (bodies, center, name) in enumerate(zip(sources, centers, document_names)):
        budget.check("array_component")
        transform = adsk.core.Matrix3D.create()
        transform.setCell(0, 3, ((index - 1) * 140 - center.x) / 10)
        transform.setCell(1, 3, -center.y / 10)
        transform.setCell(2, 3, -center.z / 10)
        occurrence = design.rootComponent.occurrences.addNewComponent(transform)
        if occurrence is None:
            raise RuntimeError("Array component creation failed; partial document retained.")
        occurrence.component.name = name
        for body in bodies:
            budget.check("array_body_copy")
            temporary = manager.copy(body)
            if temporary is None:
                raise RuntimeError("Array body copy failed; partial document retained.")
            copied = occurrence.component.bRepBodies.add(temporary)
            if copied is None or not copied.isSolid:
                raise RuntimeError("Array body import failed; partial document retained.")
            copied.name = body.name
        rows.append(
            {
                "source": name,
                "solids": occurrence.component.bRepBodies.count,
                "sphere_center_x_mm": (index - 1) * 140,
            }
        )
    camera = app.activeViewport.camera
    camera.isFitView = True
    app.activeViewport.camera = camera
    app.activeViewport.refresh()
    app.activeViewport.saveAsImageFile(str(directory / "array.png"), 1800, 1000)
    budget.check("array_archive")
    archive(design, directory / "array.f3d")
    report = {
        "document": document.name,
        "components": rows,
        "display_seconds": perf_counter() - started,
        "memory_samples": budget.samples,
        "final_rss_kib": budget.memory(),
        "scope": "Rigid copies of three already built cases; no additional solves/native validation coverage.",
    }
    (directory / "display.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
