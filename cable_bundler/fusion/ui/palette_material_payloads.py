"""
Serialize cable material and appearance settings for the Fusion palette.
"""

from __future__ import annotations

from typing import Any, Optional

# noinspection PyUnresolvedReferences
import adsk.core

from ...domain import (
    CableAppearanceReference,
    CableColor,
    CableMaterialOverrides,
    CableMaterialSettings,
    CablePullbackSettings,
    CableStripe,
    CableVisualOverrides,
    CableWeldSettings,
)


def _color_payload(color: CableColor) -> dict[str, object]:
    """
    Convert a stored cable color for the HTML palette.
    """
    return {
        "name": color.name,
        "red": color.red,
        "green": color.green,
        "blue": color.blue,
        "hex": color.hex_rgb,
    }


def _metadata_payload(entries: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    """
    Convert ordered searchable metadata rows for the palette.
    """
    return [{"key": key, "value": value} for key, value in entries]


def _appearance_reference_payload(
    appearance: Optional[CableAppearanceReference],
) -> Optional[dict[str, str]]:
    """
    Convert an optional stored Fusion appearance reference for the palette.
    """
    if appearance is None:
        return None
    return {
        "libraryId": appearance.library_id,
        "libraryName": appearance.library_name,
        "appearanceId": appearance.appearance_id,
        "appearanceName": appearance.appearance_name,
    }


def _appearance_libraries_payload(
    application: adsk.core.Application,
) -> list[dict[str, str]]:
    """
    List installed Fusion appearance libraries without loading their contents.
    """
    return _named_collection_payload(application.materialLibraries)


def _library_appearances_payload(
    application: adsk.core.Application,
    library_id: str,
) -> list[dict[str, str]]:
    """
    List appearances from one explicitly selected installed Fusion library.
    """
    library = application.materialLibraries.itemById(library_id)
    if library is None:
        raise ValueError("The selected Fusion appearance library is unavailable.")
    return _named_collection_payload(library.appearances)


def _named_collection_payload(collection: Any) -> list[dict[str, str]]:
    """
    Serialize and sort one Fusion collection whose members expose IDs and names.
    """
    result: list[dict[str, str]] = []
    for index in range(collection.count):
        item = collection.item(index)
        if item is not None:
            result.append({"id": item.id, "name": item.name})
    result.sort(key=lambda entry: entry["name"].casefold())
    return result


def _stripe_payload(stripe: CableStripe) -> dict[str, object]:
    """
    Convert one ordered procedural stripe for the HTML palette.
    """
    return {
        "color": _color_payload(stripe.color),
        "widthMm": stripe.width_mm,
        "pattern": stripe.pattern.value,
        "angleDeg": stripe.angle_deg,
        "repeatMm": stripe.repeat_mm,
    }


def _pullback_payload(settings: CablePullbackSettings) -> dict[str, object]:
    """
    Convert persisted pullback settings for the Materials dialog.
    """
    return {
        "mode": settings.mode.value,
        "value": settings.value,
        "color": _color_payload(settings.color),
        "appearance": _appearance_reference_payload(settings.appearance),
    }


def _weld_payload(settings: CableWeldSettings) -> dict[str, object]:
    """
    Convert persisted weld settings for the Materials dialog.
    """
    return {
        "value": settings.value,
        "color": _color_payload(settings.color),
        "appearance": _appearance_reference_payload(settings.appearance),
    }


def _material_settings_payload(settings: CableMaterialSettings) -> dict[str, object]:
    """
    Convert resolved material settings for editing and display.
    """
    return {
        "insulationMaterial": settings.insulation_material,
        "mainColor": _color_payload(settings.main_color),
        "appearance": _appearance_reference_payload(settings.appearance),
        "stripes": [_stripe_payload(stripe) for stripe in settings.stripes],
        "conductorMaterial": settings.conductor_material,
        "shielding": settings.shielding,
        "dielectricMaterial": settings.dielectric_material,
        "manufacturer": settings.manufacturer,
        "partNumber": settings.part_number,
        "notes": settings.notes,
        "pullback": _pullback_payload(settings.pullback),
        "weld": _weld_payload(settings.weld),
    }


def _material_overrides_payload(overrides: CableMaterialOverrides) -> dict[str, object]:
    """
    Preserve null inheritance markers at the palette boundary.
    """
    return {
        "insulationMaterial": overrides.insulation_material,
        "mainColor": (
            None if overrides.main_color is None else _color_payload(overrides.main_color)
        ),
        "appearance": _appearance_reference_payload(overrides.appearance),
        "stripes": (
            None
            if overrides.stripes is None
            else [_stripe_payload(stripe) for stripe in overrides.stripes]
        ),
        "conductorMaterial": overrides.conductor_material,
        "shielding": overrides.shielding,
        "dielectricMaterial": overrides.dielectric_material,
        "manufacturer": overrides.manufacturer,
        "partNumber": overrides.part_number,
        "notes": overrides.notes,
        "pullback": (None if overrides.pullback is None else _pullback_payload(overrides.pullback)),
        "weld": None if overrides.weld is None else _weld_payload(overrides.weld),
    }


def _visual_overrides_payload(overrides: CableVisualOverrides) -> dict[str, object]:
    """
    Preserve branch-property inheritance markers at the palette boundary.
    """
    return {
        "diameterMm": overrides.diameter_mm,
        "conductorDiameterMm": overrides.conductor_diameter_mm,
        "insulationMaterial": overrides.insulation_material,
        "conductorMaterial": overrides.conductor_material,
        "shielding": overrides.shielding,
        "dielectricMaterial": overrides.dielectric_material,
        "manufacturer": overrides.manufacturer,
        "partNumber": overrides.part_number,
        "mainColor": (
            None if overrides.main_color is None else _color_payload(overrides.main_color)
        ),
        "appearance": _appearance_reference_payload(overrides.appearance),
        "stripes": (
            None
            if overrides.stripes is None
            else [_stripe_payload(stripe) for stripe in overrides.stripes]
        ),
        "pullback": (None if overrides.pullback is None else _pullback_payload(overrides.pullback)),
        "weld": None if overrides.weld is None else _weld_payload(overrides.weld),
    }
