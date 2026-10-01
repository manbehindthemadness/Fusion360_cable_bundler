"""
Inspect the open, unsaved multi-ribbon trial without changing it.
"""

from __future__ import annotations

import json

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion


def run(_context: object) -> None:
    """
    Report the retained trial's components and persistent solid state.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    design = adsk.fusion.Design.cast(application.activeProduct)
    if document is None or design is None:
        raise RuntimeError("Open the trial design before inspecting its state.")
    components: list[dict[str, object]] = []
    for occurrence in design.rootComponent.occurrences:
        component = occurrence.component
        bodies = list(component.bRepBodies)
        branches = [body for body in bodies if body.name.startswith("Lane ")]
        components.append(
            {
                "name": component.name,
                "body_count": len(bodies),
                "branch_count": len(branches),
                "branch_names": [body.name for body in branches],
                "invalid_branches": [
                    body.name
                    for body in branches
                    if not body.isValid or not body.isSolid or body.volume <= 0
                ],
            }
        )
    print(
        "RIBBON_MULTI_STATE="
        + json.dumps({"document": document.name, "components": components}, sort_keys=True)
    )


if __name__ == "__main__":
    run(None)
