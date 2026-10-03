"""
Expose the exact Interface contact references beyond the textured FFC ends.

Run in the existing unsaved Fusion scratch after experiment_ffc_interface_contacts.
Display copies are shifted 4 mm straight outward from each ribbon end; the
original, identity-bearing contact sheets remain at their exact locations.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

_STANDOFF_CM = 0.4
_ENDS = (
    ("FFC START Interface contacts · pins 1–19", (0.0, -_STANDOFF_CM, 0.0)),
    ("FFC END Interface contacts · pins 1–19", (0.0, 0.0, -_STANDOFF_CM)),
)


def _reference_component(design: adsk.fusion.Design, name: str) -> adsk.fusion.Component:
    """
    Resolve one uniquely named contact bank in the active scratch.
    """
    matches = [
        occurrence.component
        for occurrence in design.rootComponent.occurrences
        if occurrence.component.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {name} component, found {len(matches)}.")
    return matches[0]


def run(_context: object) -> None:
    """
    Add longitudinally displaced display copies while retaining exact sheets.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before adding display copies.")
    scratch = application.activeDocument
    if scratch is None or scratch.name != "Untitled" or scratch.isSaved:
        raise RuntimeError("Activate the unsaved textured FFC sweep scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if (
        design is None
        or design.appearances.itemByName("FFC procedural 19-trace stripe test") is None
    ):
        raise RuntimeError("The active scratch has no procedural 19-trace stripe test.")
    if any(
        "contact display · 4 mm outward" in occurrence.component.name
        for occurrence in design.rootComponent.occurrences
    ):
        raise RuntimeError("Offset contact displays are already present in this scratch.")
    banks = [(_reference_component(design, name), delta) for name, delta in _ENDS]
    for component, _delta in banks:
        if component.bRepBodies.count != 19 or any(
            not component.bRepBodies.item(index).name.startswith("Pin ") for index in range(19)
        ):
            raise RuntimeError(f"{component.name} is not an untouched 19-contact bank.")
    manager = adsk.fusion.TemporaryBRepManager.get()
    rows: list[dict[str, object]] = []
    for end, (component, delta) in enumerate(banks):
        display = design.rootComponent.occurrences.addNewComponent(
            adsk.core.Matrix3D.create()
        ).component
        display.name = f"FFC {('START', 'END')[end]} contact display · 4 mm outward"
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(*delta)
        for index in range(19):
            source = component.bRepBodies.item(index)
            temporary = manager.copy(source)
            if temporary is None or not manager.transform(temporary, transform):
                raise RuntimeError(f"Could not offset {component.name} pin {index + 1}.")
            body = display.bRepBodies.add(temporary)
            if body is None or body.faces.count != 1:
                raise RuntimeError(f"Could not display {component.name} pin {index + 1}.")
            body.name = f"DISPLAY {source.name} · 4 mm outward"
            body.appearance = source.appearance
            original = source.faces.item(0).centroid
            displaced = body.faces.item(0).centroid
            actual_delta = (
                displaced.x - original.x,
                displaced.y - original.y,
                displaced.z - original.z,
            )
            error_mm = 10.0 * math.dist(delta, actual_delta)
            if error_mm > 1e-5:
                raise RuntimeError(f"Display pin {index + 1} displacement is inaccurate.")
            rows.append(
                {
                    "end": end,
                    "pin": index + 1,
                    "display_offset_mm": [value * 10.0 for value in delta],
                    "offset_error_mm": error_mm,
                }
            )
    application.activeViewport.refresh()
    output = (
        Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_contact_standoffs.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(
        "FFC_CONTACT_STANDOFFS="
        + json.dumps(
            {
                "display_contacts": len(rows),
                "maximum_offset_error_mm": max(row["offset_error_mm"] for row in rows),
                "scratch_open": scratch.isValid,
                "report": str(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
