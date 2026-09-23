"""
Harness material, construction, and interpolation edits.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Optional
from uuid import UUID

from ...domain import (
    AutoTransitionPreset,
    CableMaterialSettings,
    Metadata,
)
from ...domain.model import InterpolationSettings
from .support import persist_definition, read_definition
from .types import HarnessEditGateway


def rename_harness(
    harness_id: UUID,
    name: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace the persisted display name without changing harness identity.
    """
    if not isinstance(name, str):
        raise ValueError("Harness name must be a string.")
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Harness name must not be empty.")
    original, definition = read_definition(harness_id, gateway)
    persist_definition(
        harness_id,
        original,
        replace(definition, name=normalized_name),
        gateway,
    )


def set_harness_material_defaults(
    harness_id: UUID,
    settings: CableMaterialSettings,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace the parent material settings inherited by cable groups without overrides.
    """
    if not isinstance(settings, CableMaterialSettings):
        raise ValueError("Harness material defaults are invalid.")
    original, definition = read_definition(harness_id, gateway)
    persist_definition(
        harness_id,
        original,
        replace(definition, material_defaults=settings),
        gateway,
    )


def set_harness_properties(
    harness_id: UUID,
    insulation_material: str,
    conductor_material: str,
    shielding: str,
    dielectric_material: str,
    manufacturer: str,
    part_number: str,
    metadata: Metadata,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace inheritable construction, catalog, and searchable metadata properties.
    """
    original, definition = read_definition(harness_id, gateway)
    updated_defaults = replace(
        definition.material_defaults,
        insulation_material=insulation_material,
        conductor_material=conductor_material,
        shielding=shielding,
        dielectric_material=dielectric_material,
        manufacturer=manufacturer,
        part_number=part_number,
    )
    persist_definition(
        harness_id,
        original,
        replace(definition, material_defaults=updated_defaults, metadata=metadata),
        gateway,
    )


def set_interpolation(
    harness_id: UUID,
    target: str,
    settings: InterpolationSettings,
    gateway: HarnessEditGateway,
    target_id: Optional[UUID] = None,
    end_defaults: Optional[InterpolationSettings] = None,
    apply_existing: bool = False,
    member_id: Optional[UUID] = None,
    use_defaults: bool = False,
    minimum_clearance_mm: Optional[float] = None,
    auto_transition_preset: Optional[AutoTransitionPreset] = None,
) -> None:
    """
    Save section controls or creation defaults in one reversible metadata edit.

    Optionally apply both presets to existing sections in the same transaction.
    """
    original, definition = read_definition(harness_id, gateway)
    if target == "defaults":
        if end_defaults is None:
            raise ValueError("Both gate and end defaults are required.")
        clearance = (
            definition.minimum_clearance_mm
            if minimum_clearance_mm is None
            else minimum_clearance_mm
        )
        if (
            isinstance(clearance, bool)
            or not isinstance(clearance, (int, float))
            or not math.isfinite(clearance)
            or clearance < 0.0
        ):
            raise ValueError("Minimum member clearance must be finite and nonnegative.")
        updated = replace(
            definition,
            gate_defaults=settings,
            end_defaults=end_defaults,
            minimum_clearance_mm=float(clearance),
            auto_transition_preset=(
                definition.auto_transition_preset
                if auto_transition_preset is None
                else auto_transition_preset
            ),
        )
        if apply_existing:
            updated = replace(
                updated,
                controls=tuple(
                    replace(item, interpolation=settings)
                    if not item.interpolation_is_override
                    else item
                    for item in definition.controls
                ),
                connections=tuple(
                    replace(item, interpolation=end_defaults) for item in definition.connections
                ),
            )
    elif target == "gate":
        if not any(item.control_id == target_id for item in definition.controls):
            raise ValueError("Selected gate no longer exists.")
        updated = replace(
            definition,
            controls=tuple(
                replace(
                    item,
                    interpolation=definition.gate_defaults if use_defaults else settings,
                    interpolation_is_override=not use_defaults,
                )
                if item.control_id == target_id
                else item
                for item in definition.controls
            ),
        )
    elif target == "end":
        connection = next(
            (item for item in definition.connections if item.connection_id == target_id), None
        )
        if connection is None:
            raise ValueError("Selected end section no longer exists.")
        if member_id is None:
            edited = replace(connection, interpolation=settings, member_interpolations=())
        else:
            if member_id not in connection.member_identities:
                raise ValueError("Selected end member no longer exists.")
            edited = replace(
                connection,
                interpolation=definition.end_defaults if use_defaults else connection.interpolation,
                member_interpolations=tuple(
                    (None if use_defaults else settings) if identity == member_id else previous
                    for identity, previous in zip(
                        connection.member_identities,
                        connection.member_interpolations or (None,) * len(connection.member_tokens),
                    )
                ),
            )
        updated = replace(
            definition,
            connections=tuple(
                edited if item.connection_id == target_id else item
                for item in definition.connections
            ),
        )
    else:
        raise ValueError("Unsupported interpolation target.")
    persist_definition(harness_id, original, updated, gateway)
