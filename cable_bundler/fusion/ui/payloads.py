"""
Fusion UI services for payloads.
"""

from __future__ import annotations

import json
import math
from typing import Optional, cast
from uuid import UUID

from ...domain import (
    CableAppearanceReference,
    CableColor,
    CableMaterialOverrides,
    CableMaterialSettings,
    CableStripe,
    StripePattern,
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


# noinspection DuplicatedCode
def read_diagram_qa_observation(serialized_data: str) -> dict[str, object]:
    """
    Validate and normalize one bounded relationship-diagram QA observation.
    """
    payload = _read_palette_payload(serialized_data)
    contract_version = payload.get("contractVersion")
    legacy_contract = contract_version in {"4", "8", "9"}
    default_metric = 0 if legacy_contract else None
    status = payload.get("status")
    connector_count = _read_nonnegative_int(payload, "connectorCount", "connector count")
    maximum_gap = payload.get("maximumEndpointGap")
    minimum_trace_gap = payload.get("minimumUnrelatedTraceGap", 32.0 if legacy_contract else None)
    minimum_parallel_gap = payload.get("minimumParallelTraceGap", 10.0 if legacy_contract else None)
    overlapping_trace_pair_count = _read_nonnegative_int(
        {
            **payload,
            "overlappingTracePairCount": payload.get("overlappingTracePairCount", default_metric),
        },
        "overlappingTracePairCount",
        "overlapping trace-pair count",
    )
    obstructed_trace_count = _read_nonnegative_int(
        payload,
        "obstructedTraceCount",
        "obstruction count",
    )
    port_count = _read_nonnegative_int(payload, "portCount", "port count")
    topology_edge_count = _read_nonnegative_int(
        {**payload, "topologyEdgeCount": payload.get("topologyEdgeCount", default_metric)},
        "topologyEdgeCount",
        "topology edge count",
    )
    expected_topology_edge_count = _read_nonnegative_int(
        {
            **payload,
            "expectedTopologyEdgeCount": payload.get("expectedTopologyEdgeCount", default_metric),
        },
        "expectedTopologyEdgeCount",
        "expected topology edge count",
    )
    invalid_trace_group_count = _read_nonnegative_int(
        payload,
        "invalidTraceGroupCount",
        "trace-group count",
    )
    layout = payload.get("layout")
    layout_revision = _read_nonnegative_int(
        {**payload, "layoutRevision": payload.get("layoutRevision", default_metric)},
        "layoutRevision",
        "layout revision",
    )
    layout_error = payload.get("layoutError", False if legacy_contract else None)
    redraw_completed = payload.get("redrawCompleted", False if legacy_contract else None)
    layout_changed = payload.get("layoutChanged", False if legacy_contract else None)
    layout_candidate_count = _read_nonnegative_int(
        {**payload, "layoutCandidateCount": payload.get("layoutCandidateCount", default_metric)},
        "layoutCandidateCount",
        "layout candidate count",
    )
    layout_candidate_index = _read_nonnegative_int(
        {**payload, "layoutCandidateIndex": payload.get("layoutCandidateIndex", default_metric)},
        "layoutCandidateIndex",
        "layout candidate index",
    )
    visual_overlap_count = _read_nonnegative_int(
        {**payload, "visualOverlapCount": payload.get("visualOverlapCount", default_metric)},
        "visualOverlapCount",
        "visual overlap count",
    )
    visible_overflow_count = _read_nonnegative_int(
        {**payload, "visibleOverflowCount": payload.get("visibleOverflowCount", default_metric)},
        "visibleOverflowCount",
        "visible overflow count",
    )
    if status not in {"passed", "failed", "skipped"}:
        raise ValueError("Diagram QA observation has an invalid status.")
    if (
        isinstance(maximum_gap, bool)
        or not isinstance(maximum_gap, (int, float))
        or not math.isfinite(float(maximum_gap))
        or float(maximum_gap) < 0
    ):
        raise ValueError("Diagram QA endpoint gap must be finite and nonnegative.")
    if (
        isinstance(minimum_trace_gap, bool)
        or not isinstance(minimum_trace_gap, (int, float))
        or not math.isfinite(float(minimum_trace_gap))
        or float(minimum_trace_gap) < 0
    ):
        raise ValueError("Diagram QA trace clearance must be finite and nonnegative.")
    if (
        isinstance(minimum_parallel_gap, bool)
        or not isinstance(minimum_parallel_gap, (int, float))
        or not math.isfinite(float(minimum_parallel_gap))
        or float(minimum_parallel_gap) < 0
    ):
        raise ValueError("Diagram QA parallel trace gap must be finite and nonnegative.")
    if not isinstance(layout_error, bool):
        raise ValueError("Diagram QA layout error flag must be boolean.")
    if not isinstance(redraw_completed, bool):
        raise ValueError("Diagram QA redraw completion flag must be boolean.")
    if not isinstance(layout_changed, bool):
        raise ValueError("Diagram QA layout-change flag must be boolean.")
    supported_layouts = {
        "4": "endpoint-junction-forest",
        "8": "route-aware-cardinal-topology",
        "9": "route-aware-cardinal-topology",
        "10": "layered-cardinal-topology",
    }
    expected_layout = (
        supported_layouts.get(contract_version) if isinstance(contract_version, str) else None
    )
    if expected_layout is None:
        raise ValueError("Diagram QA contract version is unsupported.")
    if layout != expected_layout:
        raise ValueError("Diagram QA layout is unsupported.")
    return {
        "status": status,
        "connectorCount": connector_count,
        "maximumEndpointGap": float(maximum_gap),
        "minimumUnrelatedTraceGap": float(minimum_trace_gap),
        "minimumParallelTraceGap": float(minimum_parallel_gap),
        "overlappingTracePairCount": overlapping_trace_pair_count,
        "obstructedTraceCount": obstructed_trace_count,
        "portCount": port_count,
        "topologyEdgeCount": topology_edge_count,
        "expectedTopologyEdgeCount": expected_topology_edge_count,
        "invalidTraceGroupCount": invalid_trace_group_count,
        "layoutRevision": layout_revision,
        "layoutError": layout_error,
        "redrawCompleted": redraw_completed,
        "layoutChanged": layout_changed,
        "layoutCandidateCount": layout_candidate_count,
        "layoutCandidateIndex": layout_candidate_index,
        "visualOverlapCount": visual_overlap_count,
        "visibleOverflowCount": visible_overflow_count,
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


def _read_material_color(raw_value: object) -> CableColor:
    """
    Parse one named RGB color supplied by the local HTML palette.
    """
    if not isinstance(raw_value, dict):
        raise ValueError("Cable color must be an object.")
    name = raw_value.get("name")
    red = raw_value.get("red")
    green = raw_value.get("green")
    blue = raw_value.get("blue")
    if not isinstance(name, str):
        raise ValueError("Cable color requires a name.")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (red, green, blue)):
        raise ValueError("Cable color requires integer red, green, and blue channels.")
    return CableColor(name, cast(int, red), cast(int, green), cast(int, blue))


def _read_appearance_reference(raw_value: object) -> Optional[CableAppearanceReference]:
    """
    Parse an optional Fusion library appearance supplied by the local palette.
    """
    if raw_value is None:
        return None
    if not isinstance(raw_value, dict):
        raise ValueError("Cable appearance must be an object or null.")
    values = []
    for key in ("libraryId", "libraryName", "appearanceId", "appearanceName"):
        value = raw_value.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Cable appearance requires complete library and appearance details.")
        values.append(value)
    return CableAppearanceReference(*values)


def _read_material_stripes(raw_value: object) -> tuple[CableStripe, ...]:
    """
    Parse ordered procedural stripes supplied by the local HTML palette.
    """
    if not isinstance(raw_value, list):
        raise ValueError("Cable stripes must be a list.")
    stripes: list[CableStripe] = []
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
            CableStripe(
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


def _read_material_settings(raw_value: object) -> CableMaterialSettings:
    """
    Parse complete parent material settings supplied by the palette.
    """
    if not isinstance(raw_value, dict):
        raise ValueError("Harness cable-material settings must be an object.")
    return CableMaterialSettings(
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


def _read_harness_properties(raw_value: object) -> tuple[str, str, str, str, str]:
    """
    Parse inheritable construction and catalog properties supplied by the palette.
    """
    if not isinstance(raw_value, dict):
        raise ValueError("Harness properties must be an object.")
    return (
        _read_material_text(raw_value, "insulationMaterial", "Insulation material", required=True),
        _read_material_text(raw_value, "conductorMaterial", "Conductor material", required=True),
        _read_material_text(raw_value, "manufacturer", "Manufacturer", required=False),
        _read_material_text(raw_value, "partNumber", "Part number", required=False),
        _read_material_text(raw_value, "notes", "Notes", required=False),
    )


def _read_material_overrides(raw_value: object) -> CableMaterialOverrides:
    """
    Parse nullable cable overrides; null values retain parent inheritance.
    """
    if not isinstance(raw_value, dict):
        raise ValueError("Cable-material overrides must be an object.")
    values = raw_value

    def optional_text(key: str, label: str, required: bool = False) -> Optional[str]:
        """
        Preserve null inheritance or validate one explicit text override.
        """
        value = values.get(key)
        if value is None:
            return None
        return _read_material_text(values, key, label, required=required)

    return CableMaterialOverrides(
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
