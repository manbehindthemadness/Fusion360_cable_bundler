"""
Inspect existing Interface contacts for direct electronics identifiers.

Requires Fusion and an open 3D design with saved Interface contacts. Run through
Fusion's script runner. For development MCP execution, compile this source in a
separate namespace and call its run entry point with readOnly=true; submitting
it verbatim conflicts with the server's wrapper and future-import placement.
Reads only the active design and its contact owners; does not alter geometry,
attributes, selection, documents, or the active workspace. Missing identifiers
do not prove that an electronics link is unavailable through other APIs.
"""

from __future__ import annotations

import json
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion


def _describe(entity: Any) -> dict[str, object] | None:
    """
    Report bounded metadata without dumping geometry or saved harness payloads.
    """
    if entity is None:
        return None
    attributes = getattr(entity, "attributes", None)
    values = []
    if attributes is not None:
        for index in range(min(attributes.count, 40)):
            attribute = attributes.item(index)
            values.append(
                {
                    "group": attribute.groupName,
                    "name": attribute.name,
                    "value": "<harness data omitted>"
                    if attribute.groupName == "kev0.cable_bundler"
                    else attribute.value[:3000],
                }
            )
    return {
        "type": getattr(entity, "objectType", ""),
        "name": getattr(entity, "name", ""),
        "attributes": values,
        "electronicsProperties": [
            name
            for name in dir(entity)
            if any(term in name.lower() for term in ("electr", "pcb", "pad", "signal", "ecad"))
        ],
    }


def run(_context: object) -> None:
    """
    Print contact and parent metadata from the current design as bounded JSON.
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("The active product must be the 3D PCB design.")
    contacts = []
    ancestors = {}
    for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition"):
        definition = json.loads(attribute.value)
        for interface in definition.get("interfaces", []):
            for contact in interface.get("contacts", [])[:20]:
                for entity in design.findEntityByToken(contact["entity_token"]) or []:
                    body = getattr(entity, "body", None)
                    occurrence = getattr(entity, "assemblyContext", None)
                    parent = occurrence
                    for _depth in range(8):
                        if parent is None:
                            break
                        path = parent.fullPathName
                        if path in ancestors:
                            break
                        reference = (
                            parent.documentReference if parent.isReferencedComponent else None
                        )
                        data_file = getattr(reference, "dataFile", None)
                        ancestors[path] = {
                            "occurrence": _describe(parent),
                            "native": _describe(getattr(parent, "nativeObject", None)),
                            "component": _describe(parent.component),
                            "referenceProperties": [
                                name for name in dir(parent) if "reference" in name.lower()
                            ],
                            "source": None
                            if data_file is None
                            else {
                                "name": data_file.name,
                                "extension": data_file.fileExtension,
                            },
                        }
                        parent = parent.assemblyContext
                    contacts.append(
                        {
                            "interface": interface.get("name"),
                            "contactId": contact.get("contact_id"),
                            "entity": _describe(entity),
                            "native": _describe(getattr(entity, "nativeObject", None)),
                            "body": _describe(body),
                            "component": _describe(getattr(body, "parentComponent", None)),
                            "occurrence": _describe(occurrence),
                        }
                    )
    print(
        json.dumps(
            {
                "document": app.activeDocument.name,
                "root": _describe(design.rootComponent),
                "contacts": contacts,
                "ancestors": ancestors,
                "products": [
                    app.activeDocument.products.item(index).objectType
                    for index in range(app.activeDocument.products.count)
                ],
            },
            sort_keys=True,
        )
    )
