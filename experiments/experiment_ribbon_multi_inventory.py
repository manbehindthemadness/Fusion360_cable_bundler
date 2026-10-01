"""
Inventory generated ribbon groups in the active Fusion design.

Run through Fusion Text Commands ``Python.Run`` with the source design active.
"""

from __future__ import annotations

import json

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion


def run(_context: object) -> None:
    """
    Print generated ribbon bodies without modifying the active document.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    design = adsk.fusion.Design.cast(application.activeProduct)
    if document is None or design is None:
        raise RuntimeError("Open a Fusion design before inventorying ribbons.")
    groups: list[dict[str, object]] = []
    for occurrence in design.rootComponent.allOccurrences:
        attribute = occurrence.component.attributes.itemByName(
            "kev0.cable_bundler", "generated_cable_group"
        )
        if attribute is None:
            continue
        metadata = json.loads(attribute.value)
        bodies = [
            body
            for body in occurrence.component.bRepBodies
            if "Discrete Ribbon" in body.name and body.isValid and body.isSolid
        ]
        if bodies:
            groups.append(
                {
                    "component": occurrence.component.name,
                    "group_id": metadata.get("cable_group_id"),
                    "body_count": len(bodies),
                    "branch_count": len(metadata.get("connection_branches", [])),
                }
            )
    print(
        "RIBBON_MULTI_INVENTORY="
        + json.dumps(
            {"document": document.name, "modified": document.isModified, "groups": groups},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
