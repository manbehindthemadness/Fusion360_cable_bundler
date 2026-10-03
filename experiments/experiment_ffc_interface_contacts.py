"""
Display the saved Interface contact faces beside the textured FFC sweep.

Run through the local Fusion MCP script runner with no command active. The
saved design is read only. Exact assembly-context contact faces are copied
into the active unsaved sweep scratch and remain open for visual inspection.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import HarnessDefinition, loads
from cable_bundler.fusion.attachment_targets import resolve_attachment_target
from cable_bundler.fusion.harness_gateway import FusionHarnessGateway
from cable_bundler.fusion.solid_ribbon import SolidRibbonPlan
from experiments.experiment_live_ffc_correspondence import _live_plan


@dataclass(frozen=True)
class _ContactCopy:
    """
    Retain a copied source face and its authoritative pin/contact identity.
    """

    end: int
    pin: int
    contact_id: str
    body: adsk.fusion.BRepBody
    center_cm: tuple[float, float, float]


def _definition_for_plan(design: adsk.fusion.Design, group_id: str) -> HarnessDefinition:
    """
    Find the saved harness owning the planned FFC group.
    """
    for stored in FusionHarnessGateway(design).list_stored_harnesses():
        definition = loads(stored.serialized_definition)
        if any(str(group.cable_group_id) == group_id for group in definition.cable_groups):
            return definition
    raise RuntimeError("The saved source no longer contains the planned FFC group.")


def _contact_copies(
    design: adsk.fusion.Design, definition: HarnessDefinition, plan: SolidRibbonPlan
) -> tuple[_ContactCopy, ...]:
    """
    Resolve every ordered attachment back to its persisted Interface contact.
    """
    contacts = {
        (contact.kind, contact.entity_token): str(contact.contact_id)
        for interface in definition.interfaces
        for contact in interface.contacts
    }
    attachments = {
        str(attachment.attachment_id): attachment
        for connection in definition.connections
        for attachment in connection.attachments
    }
    manager = adsk.fusion.TemporaryBRepManager.get()
    copies: list[_ContactCopy] = []
    for end in (0, 1):
        for pin, (attachment_id, expected_contact_id) in enumerate(
            zip(plan.attachment_ids[end], plan.contact_ids[end]), start=1
        ):
            attachment = attachments.get(attachment_id)
            if attachment is None or not attachment.has_target:
                raise RuntimeError(f"Interface {end} pin {pin} has no saved attachment target.")
            actual_contact_id = contacts.get((attachment.target_kind, attachment.entity_token))
            if actual_contact_id != expected_contact_id:
                raise RuntimeError(f"Interface {end} pin {pin} has mismatched contact identity.")
            face = adsk.fusion.BRepFace.cast(resolve_attachment_target(design, attachment))
            if face is None:
                raise RuntimeError(f"Interface {end} pin {pin} is not a live face contact.")
            copied_body = manager.copy(face)
            if copied_body is None or copied_body.faces.count != 1:
                raise RuntimeError(f"Fusion could not copy Interface {end} pin {pin} face.")
            center = face.centroid
            copies.append(
                _ContactCopy(
                    end,
                    pin,
                    expected_contact_id,
                    copied_body,
                    (center.x, center.y, center.z),
                )
            )
    if len(copies) != sum(len(identities) for identities in plan.contact_ids):
        raise RuntimeError("Not every planned Interface contact was copied.")
    return tuple(copies)


def _appearance(
    design: adsk.fusion.Design, name: str, rgb: tuple[int, int, int]
) -> adsk.core.Appearance:
    """
    Create a document-local opaque reference color without changing source faces.
    """
    application = adsk.core.Application.get()
    library = application.materialLibraries.itemById("BA5EE55E-9982-449B-9D66-9F036540E140")
    if library is None:
        raise RuntimeError("Fusion's built-in appearance library is unavailable.")
    generic = library.appearances.itemById("Prism-129")
    if generic is None:
        raise RuntimeError("Fusion's generic opaque appearance is unavailable.")
    appearance = design.appearances.addByCopy(generic, name)
    if appearance is None:
        raise RuntimeError(f"Fusion could not create the {name} appearance.")
    color_property = appearance.appearanceProperties.itemById("opaque_albedo")
    if color_property is None:
        raise RuntimeError(f"The {name} appearance has no editable albedo.")
    color_property.value = adsk.core.Color.create(*rgb, 255)
    return appearance


def _add_contacts(
    design: adsk.fusion.Design, copies: tuple[_ContactCopy, ...]
) -> list[dict[str, object]]:
    """
    Persist the exact source contact sheets in two labeled scratch components.
    """
    appearances = {
        "ordinary": _appearance(design, "FFC contact reference · gold", (238, 176, 48)),
        "first": _appearance(design, "FFC contact reference · pin 1", (250, 55, 170)),
        "last": _appearance(design, "FFC contact reference · pin 19", (40, 215, 235)),
    }
    components = []
    for name in (
        "FFC START Interface contacts · pins 1–19",
        "FFC END Interface contacts · pins 1–19",
    ):
        occurrence = design.rootComponent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        components.append(occurrence.component)
        occurrence.component.name = name
    results: list[dict[str, object]] = []
    for copy in copies:
        body = components[copy.end].bRepBodies.add(copy.body)
        if body is None or body.faces.count != 1:
            raise RuntimeError(f"Fusion could not place Interface {copy.end} pin {copy.pin}.")
        body.name = f"Pin {copy.pin:02d} · contact {copy.contact_id}"
        color = "first" if copy.pin == 1 else "last" if copy.pin == 19 else "ordinary"
        body.appearance = appearances[color]
        centroid = body.faces.item(0).centroid
        gap_mm = 10.0 * math.dist(copy.center_cm, (centroid.x, centroid.y, centroid.z))
        if gap_mm > 1e-5:
            raise RuntimeError(
                f"Interface {copy.end} pin {copy.pin} moved {gap_mm:g} mm during copy."
            )
        results.append(
            {
                "end": copy.end,
                "pin": copy.pin,
                "contact_id": copy.contact_id,
                "center_mm": [round(value * 10.0, 6) for value in copy.center_cm],
                "copy_gap_mm": gap_mm,
                "appearance": body.appearance.name if body.appearance else None,
            }
        )
    return results


def run(_context: object) -> None:
    """
    Copy exactly the two connected Interface banks into the active test design.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before adding contact references.")
    scratch = application.activeDocument
    if scratch is None or scratch.name != "Untitled" or scratch.isSaved:
        raise RuntimeError("Activate the unsaved textured FFC sweep scratch first.")
    scratch_design = adsk.fusion.Design.cast(application.activeProduct)
    if (
        scratch_design is None
        or scratch_design.appearances.itemByName("FFC procedural 19-trace stripe test") is None
    ):
        raise RuntimeError("The active scratch has no procedural 19-trace stripe test.")
    if any(
        occurrence.component.name.startswith("FFC START Interface contacts")
        for occurrence in scratch_design.rootComponent.occurrences
    ):
        raise RuntimeError("Interface contact references are already present in this scratch.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("Open the saved Wire creation tester source design first.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved source is not a Fusion design.")
    modified_before = source.isModified
    plan, _thickness_mm, _dimensions, group_id = _live_plan(source_design)
    definition = _definition_for_plan(source_design, group_id)
    copies = _contact_copies(source_design, definition, plan)
    rows = _add_contacts(scratch_design, copies)
    if source.isModified != modified_before:
        raise RuntimeError("The source design's modified state changed unexpectedly.")
    application.activeViewport.refresh()
    output = (
        Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_interface_contacts.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "source": source.name,
        "source_modified_before": modified_before,
        "source_modified_after": source.isModified,
        "scratch_open": scratch.isValid,
        "group_id": group_id,
        "contacts": rows,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "FFC_INTERFACE_CONTACTS="
        + json.dumps(
            {
                "source": source.name,
                "contacts": len(rows),
                "largest_copy_gap_mm": max(row["copy_gap_mm"] for row in rows),
                "source_modified_after": source.isModified,
                "scratch_open": scratch.isValid,
                "report": str(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
