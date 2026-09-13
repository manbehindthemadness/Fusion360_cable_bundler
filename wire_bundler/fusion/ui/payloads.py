"""
Fusion UI services for payloads.
"""

from __future__ import annotations

import json
import math
from typing import Optional, cast
from uuid import UUID

from ...domain import (
    StripePattern,
    WireAppearanceReference,
    WireColor,
    WireMaterialOverrides,
    WireMaterialSettings,
    WireStripe,
)


def _read_nonnegative_int(
    payload: dict[str, object],
    key: str,
    label: str,
) -> int:
    """
    Read a nonnegative integer metric without accepting booleans.
    """
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Diagram QA {label} must be nonnegative.")
    return value


def read_diagram_qa_observation(serialized_data: str) -> dict[str, object]:
    """
    Validate and normalize one bounded relationship-diagram QA observation.
    """
    payload = _read_palette_payload(serialized_data)
    status = payload.get("status")
    connector_count = _read_nonnegative_int(payload, "connectorCount", "connector count")
    maximum_gap = payload.get("maximumEndpointGap")
    obstructed_trace_count = _read_nonnegative_int(
        payload,
        "obstructedTraceCount",
        "obstruction count",
    )
    port_count = _read_nonnegative_int(payload, "portCount", "port count")
    invalid_trace_group_count = _read_nonnegative_int(
        payload,
        "invalidTraceGroupCount",
        "trace-group count",
    )
    contract_version = payload.get("contractVersion")
    layout = payload.get("layout")
    if status not in {"passed", "failed", "skipped"}:
        raise ValueError("Diagram QA observation has an invalid status.")
    if (
        isinstance(maximum_gap, bool)
        or not isinstance(maximum_gap, (int, float))
        or not math.isfinite(float(maximum_gap))
        or float(maximum_gap) < 0
    ):
        raise ValueError("Diagram QA endpoint gap must be finite and nonnegative.")
    if contract_version != "4":
        raise ValueError("Diagram QA contract version is unsupported.")
    if layout != "endpoint-junction-forest":
        raise ValueError("Diagram QA layout is unsupported.")
    return {
        "status": status,
        "connectorCount": connector_count,
        "maximumEndpointGap": float(maximum_gap),
        "obstructedTraceCount": obstructed_trace_count,
        "portCount": port_count,
        "invalidTraceGroupCount": invalid_trace_group_count,
        "contractVersion": contract_version,
        "layout": layout,
    }


def _read_palette_payload(serialized_data: str) -> dict[str, object]:
    """
    Parse a palette payload and require a JSON object.
    """
    payload = json.loads(serialized_data)
    if not isinstance(payload, dict):
        raise ValueError("Harness Builder request must be a JSON object.")
    return payload


def _read_payload_uuid(payload: dict[str, object], key: str, label: str) -> UUID:
    """
    Read one required stable identity from a palette payload.
    """
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Harness Builder request is missing a {label} identity.")
    return UUID(value)


def _read_payload_offset(payload: dict[str, object]) -> int:
    """
    Read a required single-position movement from a palette payload.
    """
    value = payload.get("offset")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Harness Builder move request is missing an integer offset.")
    return value


def _read_material_color(raw_value: object) -> WireColor:
    """
    Parse one named RGB color supplied by the local HTML palette.
    """
    if not isinstance(raw_value, dict):
        raise ValueError("Wire color must be an object.")
    name = raw_value.get("name")
    red = raw_value.get("red")
    green = raw_value.get("green")
    blue = raw_value.get("blue")
    if not isinstance(name, str):
        raise ValueError("Wire color requires a name.")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (red, green, blue)):
        raise ValueError("Wire color requires integer red, green, and blue channels.")
    return WireColor(name, cast(int, red), cast(int, green), cast(int, blue))


def _read_appearance_reference(raw_value: object) -> Optional[WireAppearanceReference]:
    """
    Parse an optional Fusion library appearance supplied by the local palette.
    """
    if raw_value is None:
        return None
    if not isinstance(raw_value, dict):
        raise ValueError("Wire appearance must be an object or null.")
    values = []
    for key in ("libraryId", "libraryName", "appearanceId", "appearanceName"):
        value = raw_value.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Wire appearance requires complete library and appearance details.")
        values.append(value)
    return WireAppearanceReference(*values)


def _read_material_stripes(raw_value: object) -> tuple[WireStripe, ...]:
    """
    Parse ordered procedural stripes supplied by the local HTML palette.
    """
    if not isinstance(raw_value, list):
        raise ValueError("Wire stripes must be a list.")
    stripes: list[WireStripe] = []
    for index, raw_stripe in enumerate(raw_value):
        if not isinstance(raw_stripe, dict):
            raise ValueError(f"Stripe {index + 1} must be an object.")
        width = raw_stripe.get("widthMm")
        angle = raw_stripe.get("angleDeg", 0.0)
        repeat = raw_stripe.get("repeatMm")
        pattern = raw_stripe.get("pattern")
        if (
            isinstance(width, bool)
            or not isinstance(width, (int, float))
            or isinstance(angle, bool)
            or not isinstance(angle, (int, float))
            or (
                repeat is not None
                and (isinstance(repeat, bool) or not isinstance(repeat, (int, float)))
            )
            or not isinstance(pattern, str)
        ):
            raise ValueError(f"Stripe {index + 1} has invalid dimensions or pattern.")
        stripes.append(
            WireStripe(
                color=_read_material_color(raw_stripe.get("color")),
                width_mm=float(width),
                pattern=StripePattern(pattern),
                angle_deg=float(angle),
                repeat_mm=None if repeat is None else float(repeat),
            )
        )
    return tuple(stripes)


def _read_material_text(
    values: dict[str, object],
    key: str,
    label: str,
    *,
    required: bool,
) -> str:
    """
    Read a material text field and optionally require non-whitespace content.
    """
    value = values.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    if required and not value.strip():
        raise ValueError(f"{label} must not be empty.")
    return value


def _read_material_settings(raw_value: object) -> WireMaterialSettings:
    """
    Parse complete parent material settings supplied by the palette.
    """
    if not isinstance(raw_value, dict):
        raise ValueError("Harness wire-material settings must be an object.")
    return WireMaterialSettings(
        insulation_material=_read_material_text(
            raw_value, "insulationMaterial", "Insulation material", required=True
        ),
        main_color=_read_material_color(raw_value.get("mainColor")),
        appearance=_read_appearance_reference(raw_value.get("appearance")),
        stripes=_read_material_stripes(raw_value.get("stripes")),
        conductor_material=_read_material_text(
            raw_value, "conductorMaterial", "Conductor material", required=True
        ),
        manufacturer=_read_material_text(raw_value, "manufacturer", "Manufacturer", required=False),
        part_number=_read_material_text(raw_value, "partNumber", "Part number", required=False),
        notes=_read_material_text(raw_value, "notes", "Notes", required=False),
    )


def _read_material_overrides(raw_value: object) -> WireMaterialOverrides:
    """
    Parse nullable wire overrides; null values retain parent inheritance.
    """
    if not isinstance(raw_value, dict):
        raise ValueError("Wire-material overrides must be an object.")
    values = raw_value

    def optional_text(key: str, label: str, required: bool = False) -> Optional[str]:
        """
        Preserve null inheritance or validate one explicit text override.
        """
        value = values.get(key)
        if value is None:
            return None
        return _read_material_text(values, key, label, required=required)

    return WireMaterialOverrides(
        insulation_material=optional_text(
            "insulationMaterial", "Insulation material", required=True
        ),
        main_color=(
            None
            if values.get("mainColor") is None
            else _read_material_color(values.get("mainColor"))
        ),
        appearance=_read_appearance_reference(values.get("appearance")),
        stripes=(
            None if values.get("stripes") is None else _read_material_stripes(values.get("stripes"))
        ),
        conductor_material=optional_text("conductorMaterial", "Conductor material", required=True),
        manufacturer=optional_text("manufacturer", "Manufacturer"),
        part_number=optional_text("partNumber", "Part number"),
        notes=optional_text("notes", "Notes"),
    )
