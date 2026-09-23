"""
Generated cable appearance lookup and persistent material metadata.
"""

from __future__ import annotations

from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import (
    CableAppearanceReference,
    CableColor,
    CableMaterialSettings,
)


def material_metadata(materials: CableMaterialSettings) -> dict[str, object]:
    """
    Serialize the resolved material values stored with generated output.
    """
    return {
        "insulation_material": materials.insulation_material,
        "main_color": materials.main_color.hex_rgb,
        "appearance": (
            None
            if materials.appearance is None
            else {
                "library_id": materials.appearance.library_id,
                "library_name": materials.appearance.library_name,
                "appearance_id": materials.appearance.appearance_id,
                "appearance_name": materials.appearance.appearance_name,
            }
        ),
        "conductor_material": materials.conductor_material,
        "shielding": materials.shielding,
        "manufacturer": materials.manufacturer,
        "part_number": materials.part_number,
        "notes": materials.notes,
        "pullback": {
            "mode": materials.pullback.mode.value,
            "value": materials.pullback.value,
            "color": materials.pullback.color.hex_rgb,
            "color_name": materials.pullback.color.name,
            "appearance": (
                None
                if materials.pullback.appearance is None
                else {
                    "library_id": materials.pullback.appearance.library_id,
                    "library_name": materials.pullback.appearance.library_name,
                    "appearance_id": materials.pullback.appearance.appearance_id,
                    "appearance_name": materials.pullback.appearance.appearance_name,
                }
            ),
        },
        "weld": {
            "value": materials.weld.value,
            "color": materials.weld.color.hex_rgb,
            "color_name": materials.weld.color.name,
            "appearance": (
                None
                if materials.weld.appearance is None
                else {
                    "library_id": materials.weld.appearance.library_id,
                    "library_name": materials.weld.appearance.library_name,
                    "appearance_id": materials.weld.appearance.appearance_id,
                    "appearance_name": materials.weld.appearance.appearance_name,
                }
            ),
        },
        "stripes": [
            {
                "color": stripe.color.hex_rgb,
                "color_name": stripe.color.name,
                "width_mm": stripe.width_mm,
                "pattern": stripe.pattern.value,
                "angle_deg": stripe.angle_deg,
                "repeat_mm": stripe.repeat_mm,
            }
            for stripe in materials.stripes
        ],
    }


def cable_appearance(
    design: adsk.fusion.Design,
    color: CableColor,
    reference: Optional[CableAppearanceReference] = None,
) -> adsk.core.Appearance:
    """
    Return a document-owned library appearance or opaque stored insulation color.

    Fusion's released appearance API requires copying a library appearance into
    the design before changing its ``opaque_albedo`` property.
    """
    name = (
        f"Cable Bundler {reference.library_name} · {reference.appearance_name} "
        f"[{reference.appearance_id}]"
        if reference is not None
        else f"Cable Bundler Insulation {color.hex_rgb}"
    )
    appearance = design.appearances.itemByName(name)
    if appearance is not None:
        return appearance
    application = adsk.core.Application.get()
    if reference is not None:
        library = application.materialLibraries.itemById(reference.library_id)
        if library is None:
            raise RuntimeError(
                f"Fusion appearance library '{reference.library_name}' is unavailable."
            )
        source = library.appearances.itemById(reference.appearance_id)
        if source is None:
            raise RuntimeError(
                f"Fusion appearance '{reference.appearance_name}' is unavailable in "
                f"'{reference.library_name}'."
            )
        appearance = design.appearances.addByCopy(source, name)
        if appearance is None:
            raise RuntimeError("Fusion could not copy the selected cable appearance.")
        return appearance
    library = application.materialLibraries.itemById("BA5EE55E-9982-449B-9D66-9F036540E140")
    if library is None:
        raise RuntimeError("Fusion's built-in appearance library is unavailable.")
    generic = library.appearances.itemById("Prism-129")
    if generic is None:
        raise RuntimeError("Fusion's generic opaque appearance is unavailable.")
    appearance = design.appearances.addByCopy(generic, name)
    if appearance is None:
        raise RuntimeError("Fusion could not create the cable insulation appearance.")
    color_property = appearance.appearanceProperties.itemById("opaque_albedo")
    if color_property is None:
        raise RuntimeError("Fusion's cable appearance has no editable color property.")
    color_property.value = adsk.core.Color.create(color.red, color.green, color.blue, 255)
    return appearance
