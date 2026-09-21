"""
Immutable domain objects for a versioned harness definition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID, uuid5

SCHEMA_VERSION = 15
DEFAULT_CABLE_DIAMETER_MM = 1.5
Metadata = tuple[tuple[str, str], ...]


def _validate_metadata(entries: Metadata, label: str) -> None:
    """
    Require ordered, uniquely named text metadata fields.
    """
    if not isinstance(entries, tuple):
        raise ValueError(f"{label} must be an ordered tuple.")
    keys: set[str] = set()
    for entry in entries:
        if (
            not isinstance(entry, tuple)
            or len(entry) != 2
            or not all(isinstance(item, str) for item in entry)
        ):
            raise ValueError(f"{label} entries must contain a text key and value.")
        key, _value = entry
        normalized_key = key.strip().casefold()
        if not normalized_key:
            raise ValueError(f"{label} keys must not be empty.")
        if normalized_key in keys:
            raise ValueError(f"{label} keys must be unique ignoring case.")
        keys.add(normalized_key)


class RoutingMode(str, Enum):
    """
    Identify the primary routing-control strategy for a harness.
    """

    ROUTING_GATES = "routing_gates"
    PROFILE_GATES = "profile_gates"


class ControlKind(str, Enum):
    """
    Identify a routing control's geometric role.
    """

    ROUTING_GATE = "routing_gate"
    PROFILE_GATE = "profile_gate"
    REFINE = "refine"


class PathwayEndpoint(str, Enum):
    """
    Identify one ordered boundary of a reusable pathway.
    """

    START = "start"
    END = "end"


class AutoTransitionPreset(str, Enum):
    """
    Select the preferred span share used by automatic interpolation distances.
    """

    TIGHT = "tight"
    COMPACT = "compact"
    BALANCED = "balanced"
    RELAXED = "relaxed"
    LOOSE = "loose"

    @property
    def span_fraction(self) -> float:
        """
        Return the per-side share of a route span requested before safety limiting.
        """
        return {
            AutoTransitionPreset.TIGHT: 0.25,
            AutoTransitionPreset.COMPACT: 0.3125,
            AutoTransitionPreset.BALANCED: 0.375,
            AutoTransitionPreset.RELAXED: 0.4375,
            AutoTransitionPreset.LOOSE: 0.5,
        }[self]


class StripePattern(str, Enum):
    """
    Describe how an insulation-identification stripe repeats along a cable.
    """

    LONGITUDINAL = "longitudinal"
    DASHED = "dashed"
    HELICAL = "helical"


@dataclass(frozen=True)
class CableColor:
    """
    Store a portable named RGB color independently of Fusion appearances.
    """

    name: str
    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        """
        Require a name and three byte-sized color channels.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Cable color name must not be empty.")
        for channel in (self.red, self.green, self.blue):
            if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 255:
                raise ValueError("Cable color channels must be integers from 0 through 255.")

    @property
    def hex_rgb(self) -> str:
        """
        Return the color in HTML-compatible hexadecimal form.
        """
        return f"#{self.red:02X}{self.green:02X}{self.blue:02X}"


DEFAULT_CABLE_COLOR = CableColor("Black", 32, 32, 32)


@dataclass(frozen=True)
class CableAppearanceReference:
    """
    Identify an appearance in one of Fusion's installed material libraries.

    Names are retained for display and diagnostics while the stable library and
    appearance IDs drive host lookup.
    """

    library_id: str
    library_name: str
    appearance_id: str
    appearance_name: str

    def __post_init__(self) -> None:
        """
        Require complete lookup and display information.
        """
        for value in (
            self.library_id,
            self.library_name,
            self.appearance_id,
            self.appearance_name,
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Fusion appearance references require nonempty IDs and names.")


@dataclass(frozen=True)
class CableStripe:
    """
    Define one ordered procedural stripe on the insulation surface.

    ``repeat_mm`` is required for dashed and helical patterns and unused by a
    continuous longitudinal stripe. ``angle_deg`` locates the stripe around the
    cable circumference at its starting section.
    """

    color: CableColor
    width_mm: float
    pattern: StripePattern = StripePattern.LONGITUDINAL
    angle_deg: float = 0.0
    repeat_mm: Optional[float] = None

    def __post_init__(self) -> None:
        """
        Reject stripe dimensions that cannot drive procedural geometry.
        """
        if not isinstance(self.color, CableColor):
            raise ValueError("Stripe color must be a cable color.")
        if not isinstance(self.pattern, StripePattern):
            raise ValueError("Stripe pattern is not supported.")
        if (
            isinstance(self.width_mm, bool)
            or not isinstance(self.width_mm, (int, float))
            or not math.isfinite(self.width_mm)
            or self.width_mm <= 0
        ):
            raise ValueError("Stripe width must be a finite positive value in millimeters.")
        if (
            isinstance(self.angle_deg, bool)
            or not isinstance(self.angle_deg, (int, float))
            or not math.isfinite(self.angle_deg)
        ):
            raise ValueError("Stripe angle must be finite degrees.")
        if self.repeat_mm is not None and (
            isinstance(self.repeat_mm, bool)
            or not isinstance(self.repeat_mm, (int, float))
            or not math.isfinite(self.repeat_mm)
            or self.repeat_mm <= 0
        ):
            raise ValueError("Stripe repeat must be a finite positive value in millimeters.")
        if self.pattern is not StripePattern.LONGITUDINAL and self.repeat_mm is None:
            raise ValueError("Dashed and helical stripes require a positive repeat length.")


@dataclass(frozen=True)
class CableMaterialSettings:
    """
    Store resolved harness-level defaults for cable construction and identification.
    """

    insulation_material: str = "PVC"
    main_color: CableColor = DEFAULT_CABLE_COLOR
    appearance: Optional[CableAppearanceReference] = None
    stripes: tuple[CableStripe, ...] = ()
    conductor_material: str = "Copper"
    manufacturer: str = ""
    part_number: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        """
        Require usable material labels while permitting optional catalog metadata.
        """
        if not isinstance(self.insulation_material, str) or not self.insulation_material.strip():
            raise ValueError("Insulation material must not be empty.")
        if not isinstance(self.conductor_material, str) or not self.conductor_material.strip():
            raise ValueError("Conductor material must not be empty.")
        if not isinstance(self.main_color, CableColor):
            raise ValueError("Main insulation color must be a cable color.")
        if self.appearance is not None and not isinstance(
            self.appearance, CableAppearanceReference
        ):
            raise ValueError("Main insulation appearance must reference a Fusion appearance.")
        if not isinstance(self.stripes, tuple) or not all(
            isinstance(stripe, CableStripe) for stripe in self.stripes
        ):
            raise ValueError("Cable stripes must be an ordered tuple of stripe definitions.")
        for value in (self.manufacturer, self.part_number, self.notes):
            if not isinstance(value, str):
                raise ValueError("Cable catalog metadata must be text.")


@dataclass(frozen=True)
class CableMaterialOverrides:
    """
    Override selected harness material defaults for one persistent cable group.

    A null stripes value inherits the harness stripe collection. An explicit
    empty tuple suppresses every inherited stripe.
    """

    insulation_material: Optional[str] = None
    main_color: Optional[CableColor] = None
    appearance: Optional[CableAppearanceReference] = None
    stripes: Optional[tuple[CableStripe, ...]] = None
    conductor_material: Optional[str] = None
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        """
        Validate explicit overrides while preserving null inheritance markers.
        """
        for value, label in (
            (self.insulation_material, "Insulation material"),
            (self.conductor_material, "Conductor material"),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{label} override must not be empty.")
        if self.main_color is not None and not isinstance(self.main_color, CableColor):
            raise ValueError("Main color override must be a cable color.")
        if self.appearance is not None and not isinstance(
            self.appearance, CableAppearanceReference
        ):
            raise ValueError("Main appearance override must reference a Fusion appearance.")
        if self.main_color is None and self.appearance is not None:
            raise ValueError("A main appearance override requires a main color override.")
        if self.stripes is not None and (
            not isinstance(self.stripes, tuple)
            or not all(isinstance(stripe, CableStripe) for stripe in self.stripes)
        ):
            raise ValueError("Stripe override must be an ordered tuple of stripe definitions.")
        for value in (self.manufacturer, self.part_number, self.notes):
            if value is not None and not isinstance(value, str):
                raise ValueError("Cable catalog metadata overrides must be text.")

    def resolve(self, parent: CableMaterialSettings) -> CableMaterialSettings:
        """
        Merge these field-level overrides over harness defaults.
        """
        return CableMaterialSettings(
            insulation_material=(
                parent.insulation_material
                if self.insulation_material is None
                else self.insulation_material
            ),
            main_color=parent.main_color if self.main_color is None else self.main_color,
            appearance=(parent.appearance if self.main_color is None else self.appearance),
            stripes=parent.stripes if self.stripes is None else self.stripes,
            conductor_material=(
                parent.conductor_material
                if self.conductor_material is None
                else self.conductor_material
            ),
            manufacturer=parent.manufacturer if self.manufacturer is None else self.manufacturer,
            part_number=parent.part_number if self.part_number is None else self.part_number,
            notes=parent.notes if self.notes is None else self.notes,
        )


@dataclass(frozen=True)
class InterpolationSettings:
    """
    Bound each profile's orientation influence; None selects a quarter-span length.

    End sections interpret approach/departure in terminal-to-pathway stack order.
    """

    approach_mm: Optional[float] = None
    departure_mm: Optional[float] = None

    def __post_init__(self) -> None:
        """
        Reject malformed or non-finite distances at the domain boundary.
        """
        for value in (self.approach_mm, self.departure_mm):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(
                    "Transition distances must be finite nonnegative millimeters or Auto."
                )


@dataclass(frozen=True)
class RefineGeometry:
    """
    Store an unconstrained oriented pathway point independently of Fusion.

    The two unit directions span the marker plane. Their cross product is the
    route tangent; the display radius affects only the persistent marker.
    """

    origin_mm: tuple[float, float, float]
    u_direction: tuple[float, float, float]
    v_direction: tuple[float, float, float]
    display_radius_mm: float

    def __post_init__(self) -> None:
        """
        Require a finite origin, orthonormal frame, and positive marker radius.
        """
        vectors = (self.origin_mm, self.u_direction, self.v_direction)
        if any(not isinstance(vector, tuple) or len(vector) != 3 for vector in vectors):
            raise ValueError("Refine geometry requires three-dimensional vectors.")
        values = (*self.origin_mm, *self.u_direction, *self.v_direction)
        if not all(
            not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
            for value in values
        ):
            raise ValueError("Refine geometry requires finite vectors.")
        u_length = math.sqrt(sum(value * value for value in self.u_direction))
        v_length = math.sqrt(sum(value * value for value in self.v_direction))
        frame_dot = sum(left * right for left, right in zip(self.u_direction, self.v_direction))
        if not math.isclose(u_length, 1.0, abs_tol=1e-6):
            raise ValueError("Refine U direction must be a unit vector.")
        if not math.isclose(v_length, 1.0, abs_tol=1e-6):
            raise ValueError("Refine V direction must be a unit vector.")
        if not math.isclose(frame_dot, 0.0, abs_tol=1e-6):
            raise ValueError("Refine directions must be orthogonal.")
        if (
            isinstance(self.display_radius_mm, bool)
            or not isinstance(self.display_radius_mm, (int, float))
            or not math.isfinite(self.display_radius_mm)
            or self.display_radius_mm <= 0.0
        ):
            raise ValueError("Refine display radius must be finite and positive.")


@dataclass(frozen=True)
class Connection:
    """
    Reference a physical connection profile in a Fusion design.

    Member identities and interpolation settings align with the full token sequence.
    """

    connection_id: UUID
    name: str
    entity_token: str
    additional_entity_tokens: tuple[str, ...] = ()
    member_ids: tuple[UUID, ...] = ()
    interpolation: InterpolationSettings = InterpolationSettings()
    member_interpolations: tuple[Optional[InterpolationSettings], ...] = ()
    metadata: Metadata = ()

    def __post_init__(self) -> None:
        """
        Require unambiguous searchable cable-end metadata.
        """
        _validate_metadata(self.metadata, "Cable-end metadata")

    @property
    def member_settings(self) -> tuple[InterpolationSettings, ...]:
        """
        Resolve per-member settings, retaining legacy section-wide values as fallback.
        """
        return tuple(
            item if item is not None else self.interpolation for item in self.member_interpolations
        ) or (self.interpolation,) * len(self.member_tokens)

    @property
    def member_identities(self) -> tuple[UUID, ...]:
        """
        Return saved member identities or deterministic identities for legacy data.
        """
        return self.member_ids or tuple(
            uuid5(self.connection_id, f"member:{index}") for index in range(len(self.member_tokens))
        )

    @property
    def member_tokens(self) -> tuple[str, ...]:
        """
        Return the primary profile followed by the remaining connection members.
        """
        tokens = (self.entity_token, *self.additional_entity_tokens)
        return tokens


@dataclass(frozen=True)
class ControlStructure:
    """
    Reference a routing or profile gate in a Fusion design.
    """

    control_id: UUID
    name: str
    kind: ControlKind
    entity_token: str
    interpolation: InterpolationSettings = InterpolationSettings()
    interpolation_is_override: bool = False
    refine_geometry: Optional[RefineGeometry] = None


@dataclass(frozen=True)
class PathwayDefinition:
    """
    Group an ordered sequence of routing controls into a reusable pathway.
    """

    pathway_id: UUID
    name: str
    routing_mode: RoutingMode
    ordered_control_ids: tuple[UUID, ...]
    start_name: str = ""
    end_name: str = ""
    metadata: Metadata = ()
    start_metadata: Metadata = ()
    end_metadata: Metadata = ()

    def __post_init__(self) -> None:
        """
        Require unambiguous searchable pathway metadata.
        """
        _validate_metadata(self.metadata, "Pathway metadata")
        _validate_metadata(self.start_metadata, "Pathway start metadata")
        _validate_metadata(self.end_metadata, "Pathway end metadata")

    def endpoint_metadata(self, endpoint: PathwayEndpoint) -> Metadata:
        """
        Return searchable metadata owned by one pathway boundary.
        """
        return self.start_metadata if endpoint is PathwayEndpoint.START else self.end_metadata


@dataclass(frozen=True)
class JunctionPathwayRelationship:
    """
    Attach one pathway endpoint to a junction.
    """

    pathway_id: UUID
    endpoint: PathwayEndpoint


@dataclass(frozen=True)
class JunctionDefinition:
    """
    Represent a routing control shared by zero or more pathway endpoints.
    """

    junction_id: UUID
    name: str
    control_id: UUID
    pathway_relationships: tuple[JunctionPathwayRelationship, ...] = ()
    metadata: Metadata = ()

    def __post_init__(self) -> None:
        """
        Require unambiguous searchable junction metadata.
        """
        _validate_metadata(self.metadata, "Junction metadata")


@dataclass(frozen=True)
class StandaloneEndDefinition:
    """
    Attach one disconnected physical end to a pathway boundary.

    The referenced connection owns ordered guide profiles. End-owned controls
    extend that guide stack to the pathway without modifying the pathway.
    """

    connection_id: UUID
    pathway_id: UUID
    endpoint: PathwayEndpoint
    ordered_control_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class CableGroupDefinition:
    """
    Connect two or more physical ends as one routed conductor group.

    Member order is stable metadata order and has no electrical precedence.
    """

    cable_group_id: UUID
    connection_ids: tuple[UUID, ...]
    diameter_mm: float = DEFAULT_CABLE_DIAMETER_MM
    material_overrides: CableMaterialOverrides = CableMaterialOverrides()
    metadata_overrides: Metadata = ()

    def __post_init__(self) -> None:
        """
        Require unambiguous searchable metadata overrides.
        """
        _validate_metadata(self.metadata_overrides, "Cable metadata overrides")


@dataclass(frozen=True)
class HarnessDefinition:
    """
    Store the complete logical definition independently of Fusion geometry.

    Gate and end defaults are presets copied into newly created members.
    """

    schema_version: int
    harness_id: UUID
    name: str
    routing_mode: RoutingMode
    connections: tuple[Connection, ...]
    controls: tuple[ControlStructure, ...]
    pathways: tuple[PathwayDefinition, ...]
    junctions: tuple[JunctionDefinition, ...] = ()
    standalone_ends: tuple[StandaloneEndDefinition, ...] = ()
    cable_groups: tuple[CableGroupDefinition, ...] = ()
    gate_defaults: InterpolationSettings = InterpolationSettings()
    end_defaults: InterpolationSettings = InterpolationSettings()
    material_defaults: CableMaterialSettings = CableMaterialSettings()
    minimum_clearance_mm: float = 0.0
    auto_transition_preset: AutoTransitionPreset = AutoTransitionPreset.TIGHT
    metadata: Metadata = ()

    def __post_init__(self) -> None:
        """
        Require valid harness-wide generation preferences.
        """
        if (
            isinstance(self.minimum_clearance_mm, bool)
            or not isinstance(self.minimum_clearance_mm, (int, float))
            or not math.isfinite(self.minimum_clearance_mm)
            or self.minimum_clearance_mm < 0.0
        ):
            raise ValueError("Minimum member clearance must be finite and nonnegative.")
        if not isinstance(self.auto_transition_preset, AutoTransitionPreset):
            raise ValueError("Auto transition preset must be a supported preset.")
        _validate_metadata(self.metadata, "Harness metadata")

    def cable_group_materials(self, group: CableGroupDefinition) -> CableMaterialSettings:
        """
        Resolve one connected cable group's material settings from parent defaults.
        """
        return group.material_overrides.resolve(self.material_defaults)

    def cable_group_metadata(self, group: CableGroupDefinition) -> Metadata:
        """
        Merge one cable's explicit values over harness metadata by key.
        """
        overrides = {key.casefold(): (key, value) for key, value in group.metadata_overrides}
        resolved: list[tuple[str, str]] = []
        inherited_keys: set[str] = set()
        for key, value in self.metadata:
            normalized_key = key.casefold()
            inherited_keys.add(normalized_key)
            resolved.append(overrides.get(normalized_key, (key, value)))
        resolved.extend(
            entry for entry in group.metadata_overrides if entry[0].casefold() not in inherited_keys
        )
        return tuple(resolved)
