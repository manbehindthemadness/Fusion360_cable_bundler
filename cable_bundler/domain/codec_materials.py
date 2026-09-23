"""
Serialize and parse cable material, appearance, pullback, weld, and stripe values.
"""

from __future__ import annotations

from typing import Optional

from .codec_support import DefinitionParseError
from .codec_support import optional_float as _optional_float
from .codec_support import optional_str as _optional_str
from .codec_support import require_enum as _require_enum
from .codec_support import require_float as _require_float
from .codec_support import require_int as _require_int
from .codec_support import require_mapping as _require_mapping
from .codec_support import require_str as _require_str
from .materials import (
    CableAppearanceReference,
    CableColor,
    CableMaterialOverrides,
    CableMaterialSettings,
    CablePullbackSettings,
    CableStripe,
    CableVisualOverrides,
    CableWeldSettings,
    PullbackMode,
    StripePattern,
)


def _visual_overrides_to_dict(overrides: CableVisualOverrides) -> dict[str, object]:
    """
    Convert branch overrides while preserving null inheritance.
    """
    return {
        "diameter_mm": overrides.diameter_mm,
        "conductor_diameter_mm": overrides.conductor_diameter_mm,
        "insulation_material": overrides.insulation_material,
        "conductor_material": overrides.conductor_material,
        "shielding": overrides.shielding,
        "dielectric_material": overrides.dielectric_material,
        "manufacturer": overrides.manufacturer,
        "part_number": overrides.part_number,
        "main_color": None
        if overrides.main_color is None
        else _color_to_dict(overrides.main_color),
        "appearance": _appearance_to_dict(overrides.appearance),
        "stripes": (
            None
            if overrides.stripes is None
            else [_stripe_to_dict(item) for item in overrides.stripes]
        ),
        "pullback": (None if overrides.pullback is None else _pullback_to_dict(overrides.pullback)),
        "weld": None if overrides.weld is None else _weld_to_dict(overrides.weld),
    }


def _color_to_dict(color: CableColor) -> dict[str, object]:
    """
    Convert one portable cable color to JSON-compatible values.
    """
    return {
        "name": color.name,
        "red": color.red,
        "green": color.green,
        "blue": color.blue,
    }


def _stripe_to_dict(stripe: CableStripe) -> dict[str, object]:
    """
    Convert one procedural stripe to JSON-compatible values.
    """
    return {
        "color": _color_to_dict(stripe.color),
        "width_mm": stripe.width_mm,
        "pattern": stripe.pattern.value,
        "angle_deg": stripe.angle_deg,
        "repeat_mm": stripe.repeat_mm,
    }


def _materials_to_dict(settings: CableMaterialSettings) -> dict[str, object]:
    """
    Convert resolved cable material settings to JSON-compatible values.
    """
    return {
        "insulation_material": settings.insulation_material,
        "main_color": _color_to_dict(settings.main_color),
        "appearance": _appearance_to_dict(settings.appearance),
        "stripes": [_stripe_to_dict(stripe) for stripe in settings.stripes],
        "conductor_material": settings.conductor_material,
        "shielding": settings.shielding,
        "dielectric_material": settings.dielectric_material,
        "manufacturer": settings.manufacturer,
        "part_number": settings.part_number,
        "notes": settings.notes,
        "pullback": _pullback_to_dict(settings.pullback),
        "weld": _weld_to_dict(settings.weld),
    }


def _material_overrides_to_dict(overrides: CableMaterialOverrides) -> dict[str, object]:
    """
    Preserve null inheritance markers while serializing per-group overrides.
    """
    return {
        "insulation_material": overrides.insulation_material,
        "main_color": (
            None if overrides.main_color is None else _color_to_dict(overrides.main_color)
        ),
        "appearance": _appearance_to_dict(overrides.appearance),
        "stripes": (
            None
            if overrides.stripes is None
            else [_stripe_to_dict(stripe) for stripe in overrides.stripes]
        ),
        "conductor_material": overrides.conductor_material,
        "shielding": overrides.shielding,
        "dielectric_material": overrides.dielectric_material,
        "manufacturer": overrides.manufacturer,
        "part_number": overrides.part_number,
        "notes": overrides.notes,
        "pullback": (None if overrides.pullback is None else _pullback_to_dict(overrides.pullback)),
        "weld": None if overrides.weld is None else _weld_to_dict(overrides.weld),
    }


def _pullback_to_dict(settings: CablePullbackSettings) -> dict[str, object]:
    """
    Convert pullback settings to portable JSON-compatible values.
    """
    return {
        "mode": settings.mode.value,
        "value": settings.value,
        "color": _color_to_dict(settings.color),
        "appearance": _appearance_to_dict(settings.appearance),
    }


def _weld_to_dict(settings: CableWeldSettings) -> dict[str, object]:
    """
    Convert weld settings to portable JSON-compatible values.
    """
    return {
        "value": settings.value,
        "color": _color_to_dict(settings.color),
        "appearance": _appearance_to_dict(settings.appearance),
    }


def _parse_color(raw_value: object, path: str) -> CableColor:
    """
    Parse one named RGB color at an external-data boundary.
    """
    value = _require_mapping(raw_value, path)
    try:
        return CableColor(
            name=_require_str(value, "name", f"{path}.name"),
            red=_require_int(value, "red", f"{path}.red"),
            green=_require_int(value, "green", f"{path}.green"),
            blue=_require_int(value, "blue", f"{path}.blue"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _appearance_to_dict(
    appearance: Optional[CableAppearanceReference],
) -> Optional[dict[str, str]]:
    """
    Convert an optional Fusion library appearance reference to portable values.
    """
    if appearance is None:
        return None
    return {
        "library_id": appearance.library_id,
        "library_name": appearance.library_name,
        "appearance_id": appearance.appearance_id,
        "appearance_name": appearance.appearance_name,
    }


def _parse_appearance(raw_value: object, path: str) -> Optional[CableAppearanceReference]:
    """
    Parse an optional Fusion library appearance reference.
    """
    if raw_value is None:
        return None
    value = _require_mapping(raw_value, path)
    try:
        return CableAppearanceReference(
            library_id=_require_str(value, "library_id", f"{path}.library_id"),
            library_name=_require_str(value, "library_name", f"{path}.library_name"),
            appearance_id=_require_str(value, "appearance_id", f"{path}.appearance_id"),
            appearance_name=_require_str(value, "appearance_name", f"{path}.appearance_name"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_stripes(raw_value: object, path: str) -> tuple[CableStripe, ...]:
    """
    Parse an ordered procedural stripe collection.
    """
    if not isinstance(raw_value, list):
        raise DefinitionParseError(path, "expected a list")
    stripes: list[CableStripe] = []
    for index, raw_stripe in enumerate(raw_value):
        stripe_path = f"{path}[{index}]"
        value = _require_mapping(raw_stripe, stripe_path)
        try:
            stripes.append(
                CableStripe(
                    color=_parse_color(value.get("color"), f"{stripe_path}.color"),
                    width_mm=_require_float(value, "width_mm", f"{stripe_path}.width_mm"),
                    pattern=_require_enum(
                        StripePattern, value, "pattern", f"{stripe_path}.pattern"
                    ),
                    angle_deg=_require_float(
                        {"angle_deg": 0.0, **value}, "angle_deg", f"{stripe_path}.angle_deg"
                    ),
                    repeat_mm=_optional_float(value.get("repeat_mm"), f"{stripe_path}.repeat_mm"),
                )
            )
        except ValueError as error:
            raise DefinitionParseError(stripe_path, str(error)) from error
    return tuple(stripes)


def parse_material_settings(raw_value: object, path: str) -> CableMaterialSettings:
    """
    Parse complete harness-level cable material defaults.
    """
    value = _require_mapping(raw_value, path)
    try:
        return CableMaterialSettings(
            insulation_material=_require_str(
                value, "insulation_material", f"{path}.insulation_material"
            ),
            main_color=_parse_color(value.get("main_color"), f"{path}.main_color"),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
            stripes=_parse_stripes(value.get("stripes"), f"{path}.stripes"),
            conductor_material=_require_str(
                value, "conductor_material", f"{path}.conductor_material"
            ),
            shielding=_require_str({"shielding": "", **value}, "shielding", f"{path}.shielding"),
            dielectric_material=_require_str(
                {"dielectric_material": "", **value},
                "dielectric_material",
                f"{path}.dielectric_material",
            ),
            manufacturer=_require_str(value, "manufacturer", f"{path}.manufacturer"),
            part_number=_require_str(value, "part_number", f"{path}.part_number"),
            notes=_require_str(value, "notes", f"{path}.notes"),
            pullback=_parse_pullback(value.get("pullback", {}), f"{path}.pullback"),
            weld=_parse_weld(value.get("weld", {}), f"{path}.weld"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def parse_material_overrides(raw_value: object, path: str) -> CableMaterialOverrides:
    """
    Parse nullable field-level material overrides for one cable.
    """
    value = _require_mapping(raw_value, path)
    try:
        return CableMaterialOverrides(
            insulation_material=_optional_str(
                value.get("insulation_material"), f"{path}.insulation_material"
            ),
            main_color=(
                None
                if value.get("main_color") is None
                else _parse_color(value.get("main_color"), f"{path}.main_color")
            ),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
            stripes=(
                None
                if value.get("stripes") is None
                else _parse_stripes(value.get("stripes"), f"{path}.stripes")
            ),
            conductor_material=_optional_str(
                value.get("conductor_material"), f"{path}.conductor_material"
            ),
            shielding=_optional_str(value.get("shielding"), f"{path}.shielding"),
            dielectric_material=_optional_str(
                value.get("dielectric_material"), f"{path}.dielectric_material"
            ),
            manufacturer=_optional_str(value.get("manufacturer"), f"{path}.manufacturer"),
            part_number=_optional_str(value.get("part_number"), f"{path}.part_number"),
            notes=_optional_str(value.get("notes"), f"{path}.notes"),
            pullback=(
                None
                if value.get("pullback") is None
                else _parse_pullback(value.get("pullback"), f"{path}.pullback")
            ),
            weld=(
                None
                if value.get("weld") is None
                else _parse_weld(value.get("weld"), f"{path}.weld")
            ),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_visual_overrides(raw_value: object, path: str) -> CableVisualOverrides:
    """
    Parse optional branch overrides from current or migrated data.
    """
    value = _require_mapping(raw_value, path)
    raw_color = value.get("main_color")
    raw_stripes = value.get("stripes")
    try:
        return CableVisualOverrides(
            diameter_mm=_optional_float(value.get("diameter_mm"), f"{path}.diameter_mm"),
            conductor_diameter_mm=_optional_float(
                value.get("conductor_diameter_mm"), f"{path}.conductor_diameter_mm"
            ),
            insulation_material=_optional_str(
                value.get("insulation_material"), f"{path}.insulation_material"
            ),
            conductor_material=_optional_str(
                value.get("conductor_material"), f"{path}.conductor_material"
            ),
            shielding=_optional_str(value.get("shielding"), f"{path}.shielding"),
            dielectric_material=_optional_str(
                value.get("dielectric_material"), f"{path}.dielectric_material"
            ),
            manufacturer=_optional_str(value.get("manufacturer"), f"{path}.manufacturer"),
            part_number=_optional_str(value.get("part_number"), f"{path}.part_number"),
            main_color=None if raw_color is None else _parse_color(raw_color, f"{path}.main_color"),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
            stripes=(
                None if raw_stripes is None else _parse_stripes(raw_stripes, f"{path}.stripes")
            ),
            pullback=(
                None
                if value.get("pullback") is None
                else _parse_pullback(value.get("pullback"), f"{path}.pullback")
            ),
            weld=(
                None
                if value.get("weld") is None
                else _parse_weld(value.get("weld"), f"{path}.weld")
            ),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_pullback(raw_value: object, path: str) -> CablePullbackSettings:
    """
    Parse current pullback settings or supply defaults for migrated data.
    """
    value = _require_mapping(raw_value, path)
    defaults = CablePullbackSettings()
    try:
        return CablePullbackSettings(
            mode=(
                _require_enum(PullbackMode, value, "mode", f"{path}.mode")
                if "mode" in value
                else defaults.mode
            ),
            value=(
                _require_float(value, "value", f"{path}.value")
                if "value" in value
                else defaults.value
            ),
            color=(
                _parse_color(value.get("color"), f"{path}.color")
                if "color" in value
                else defaults.color
            ),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_weld(raw_value: object, path: str) -> CableWeldSettings:
    """
    Parse current weld settings or supply defaults for migrated data.
    """
    value = _require_mapping(raw_value, path)
    defaults = CableWeldSettings()
    try:
        return CableWeldSettings(
            value=(
                _require_float(value, "value", f"{path}.value")
                if "value" in value
                else defaults.value
            ),
            color=(
                _parse_color(value.get("color"), f"{path}.color")
                if "color" in value
                else defaults.color
            ),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error
