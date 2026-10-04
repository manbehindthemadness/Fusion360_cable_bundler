"""
Export/import the unsaved generated FFC component to test texture persistence.

The source scratch and saved design remain open. The archive and report are
written only under ignored verification artifacts; no existing file is
overwritten unless it is this experiment's own prior archive.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.cable_solid_parts.constants import GENERATED_CABLE_GROUP_ATTRIBUTE
from cable_bundler.fusion.harness_gateway import ATTRIBUTE_GROUP

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification"
ARCHIVE = OUTPUT / "ffc_generated_roundtrip.f3d"


def run(_context: object) -> None:
    """
    Verify a generated texture survives a Fusion archive round trip.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate the unsaved generated FFC scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active scratch is not a Fusion design.")
    matches = [
        occurrence.component
        for occurrence in design.rootComponent.occurrences
        if occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        is not None
        and occurrence.component.name.startswith("Cable Group 5_")
    ]
    if not matches:
        raise RuntimeError("The generated FFC product trial is unavailable.")
    component = matches[-1]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists():
        raise RuntimeError("The round-trip archive already exists; choose a fresh test name.")
    options = design.exportManager.createFusionArchiveExportOptions(str(ARCHIVE), component)
    if options is None or not design.exportManager.execute(options):
        raise RuntimeError("Fusion could not export the generated FFC component.")
    importer = application.importManager
    import_options = importer.createFusionArchiveImportOptions(str(ARCHIVE))
    if import_options is None:
        raise RuntimeError("Fusion could not define the FFC archive import.")
    reopened = importer.importToNewDocument(import_options)
    if reopened is None:
        raise RuntimeError("Fusion could not import the generated FFC archive.")
    reopened_design = adsk.fusion.Design.cast(application.activeProduct)
    if reopened_design is None:
        raise RuntimeError("The imported FFC archive is not a Fusion design.")
    textured = []
    for body_index in range(reopened_design.rootComponent.bRepBodies.count):
        body = reopened_design.rootComponent.bRepBodies.item(body_index)
        for face_index in range(body.faces.count):
            face = body.faces.item(face_index)
            appearance = face.appearance
            if appearance is None or not appearance.hasTexture:
                continue
            slot = appearance.appearanceProperties.itemById("opaque_albedo")
            texture = None if slot is None else slot.connectedTexture
            textured.append(
                {
                    "body": body.name,
                    "face_index": face_index,
                    "appearance": appearance.name,
                    "connected": texture is not None,
                }
            )
    report = {
        "source_scratch": scratch.name,
        "source_saved": scratch.isSaved,
        "archive": str(ARCHIVE),
        "archive_bytes": ARCHIVE.stat().st_size,
        "imported_document": application.activeDocument.name,
        "textured_faces": textured,
    }
    path = OUTPUT / "ffc_generated_roundtrip.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FFC_GENERATED_ROUNDTRIP=" + json.dumps(report))


if __name__ == "__main__":
    run(None)
