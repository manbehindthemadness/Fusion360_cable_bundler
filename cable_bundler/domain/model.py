"""
Immutable domain objects for a versioned harness definition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional
from uuid import UUID, uuid5

SCHEMA_VERSION = 23
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


class AttachmentTargetKind(str, Enum):
    """
    Identify the supported Fusion entity backing one cable-end attachment.
    """

    PROFILE = "profile"
    FACE = "face"
    JOINT_ORIGIN = "joint_origin"
    CIRCULAR_EDGE = "circular_edge"
    CONSTRUCTION_POINT = "construction_point"
    SKETCH_POINT = "sketch_point"


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


def _validate_visual_overrides(
    main_color: Optional[CableColor],
    appearance: Optional[CableAppearanceReference],
    stripes: Optional[tuple[CableStripe, ...]],
) -> None:
    """
    Validate the shared appearance and stripe inheritance contract.
    """
    if main_color is not None and not isinstance(main_color, CableColor):
        raise ValueError("Main color override must be a cable color.")
    if appearance is not None and not isinstance(appearance, CableAppearanceReference):
        raise ValueError("Main appearance override must reference a Fusion appearance.")
    if main_color is None and appearance is not None:
        raise ValueError("A main appearance override requires a main color override.")
    if stripes is not None and (
        not isinstance(stripes, tuple)
        or not all(isinstance(stripe, CableStripe) for stripe in stripes)
    ):
        raise ValueError("Stripe override must be an ordered tuple of stripe definitions.")


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
    shielding: str = ""
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
        for value in (self.shielding, self.manufacturer, self.part_number, self.notes):
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
    shielding: Optional[str] = None
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
        _validate_visual_overrides(self.main_color, self.appearance, self.stripes)
        for value in (self.shielding, self.manufacturer, self.part_number, self.notes):
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
            shielding=parent.shielding if self.shielding is None else self.shielding,
            manufacturer=parent.manufacturer if self.manufacturer is None else self.manufacturer,
            part_number=parent.part_number if self.part_number is None else self.part_number,
            notes=parent.notes if self.notes is None else self.notes,
        )


@dataclass(frozen=True)
class CableVisualOverrides:
    """
    Override one divided connection branch's construction and visual properties.

    A null diameter selects the cable end's equal share of its parent cable.
    Material and visual nulls inherit from the connected cable group, while an
    empty stripe tuple suppresses inherited stripes.
    """

    main_color: Optional[CableColor] = None
    appearance: Optional[CableAppearanceReference] = None
    stripes: Optional[tuple[CableStripe, ...]] = None
    diameter_mm: Optional[float] = None
    insulation_material: Optional[str] = None
    conductor_material: Optional[str] = None
    shielding: Optional[str] = None
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None

    def __post_init__(self) -> None:
        """
        Validate explicit branch overrides while retaining inheritance markers.
        """
        if self.diameter_mm is not None and (
            isinstance(self.diameter_mm, bool)
            or not isinstance(self.diameter_mm, (int, float))
            or not math.isfinite(self.diameter_mm)
            or self.diameter_mm <= 0.0
        ):
            raise ValueError("Connection diameter override must be finite and positive.")
        for value, label in (
            (self.insulation_material, "Insulation material"),
            (self.conductor_material, "Conductor material"),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{label} override must not be empty.")
        for value in (self.shielding, self.manufacturer, self.part_number):
            if value is not None and not isinstance(value, str):
                raise ValueError("Connection catalog metadata overrides must be text.")
        _validate_visual_overrides(self.main_color, self.appearance, self.stripes)

    def resolve(self, parent: CableMaterialSettings) -> CableMaterialSettings:
        """
        Merge branch material and visual overrides over resolved group materials.
        """
        return CableMaterialSettings(
            insulation_material=(
                parent.insulation_material
                if self.insulation_material is None
                else self.insulation_material
            ),
            main_color=parent.main_color if self.main_color is None else self.main_color,
            appearance=parent.appearance if self.main_color is None else self.appearance,
            stripes=parent.stripes if self.stripes is None else self.stripes,
            conductor_material=(
                parent.conductor_material
                if self.conductor_material is None
                else self.conductor_material
            ),
            shielding=parent.shielding if self.shielding is None else self.shielding,
            manufacturer=parent.manufacturer if self.manufacturer is None else self.manufacturer,
            part_number=parent.part_number if self.part_number is None else self.part_number,
            notes=parent.notes,
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
class CableEndTarget:
    """
    Retain one named external Fusion target used by a cable-end relationship.
    """

    target_kind: AttachmentTargetKind
    entity_token: str
    inherited_name: str
    name: str = ""
    parameters: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        """
        Require complete persistent identity and target-specific parameters.
        """
        if not isinstance(self.target_kind, AttachmentTargetKind):
            raise ValueError("Cable-end target kind is invalid.")
        if not isinstance(self.entity_token, str) or not self.entity_token.strip():
            raise ValueError("Cable-end target entity token must not be empty.")
        if not isinstance(self.inherited_name, str) or not self.inherited_name.strip():
            raise ValueError("Cable-end target inherited name must not be empty.")
        if not isinstance(self.name, str):
            raise ValueError("Cable-end target name must be text.")
        if not isinstance(self.parameters, tuple) or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in self.parameters
        ):
            raise ValueError("Cable-end target parameters must be finite numbers.")
        expected_count = 2 if self.target_kind is AttachmentTargetKind.FACE else 0
        if len(self.parameters) != expected_count:
            raise ValueError(
                "Face targets require two surface parameters; other targets require none."
            )

    @property
    def display_name(self) -> str:
        """
        Return the explicit alias or saved inherited target name.
        """
        return self.name.strip() or self.inherited_name.strip()

    @property
    def has_target(self) -> bool:
        """
        Report that this value always represents a complete target.
        """
        return True


@dataclass(frozen=True)
class CableEndAttachment:
    """
    Retain one external connection node and its optional Fusion target.

    A node with no target persists for later connection. Once connected, a blank
    name inherits the live target name and retains its saved fallback.
    """

    target_kind: Optional[AttachmentTargetKind]
    entity_token: str = ""
    inherited_name: str = ""
    name: str = ""
    parameters: tuple[float, ...] = ()
    metadata: Metadata = ()
    attachment_id: UUID = UUID(int=0)
    ordered_control_ids: tuple[UUID, ...] = ()
    visual_overrides: CableVisualOverrides = CableVisualOverrides()
    parent_attachment_id: Optional[UUID] = None
    shielding_target: Optional[CableEndTarget] = None

    def __post_init__(self) -> None:
        """
        Require either an empty target or a complete identity with finite parameters.
        """
        if self.target_kind is not None and not isinstance(self.target_kind, AttachmentTargetKind):
            raise ValueError("Cable-end attachment target kind is invalid.")
        if not isinstance(self.entity_token, str):
            raise ValueError("Cable-end attachment entity token must be text.")
        if not isinstance(self.inherited_name, str):
            raise ValueError("Cable-end attachment inherited name must be text.")
        if not isinstance(self.name, str):
            raise ValueError("Cable-end attachment name must be text.")
        if not isinstance(self.parameters, tuple) or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in self.parameters
        ):
            raise ValueError("Cable-end attachment parameters must be finite numbers.")
        if self.target_kind is None and (
            self.entity_token.strip() or self.inherited_name.strip() or self.parameters
        ):
            raise ValueError("An unattached cable-end connection cannot retain target data.")
        if self.target_kind is not None and (
            not self.entity_token.strip() or not self.inherited_name.strip()
        ):
            raise ValueError("A connected cable-end attachment requires target identity.")
        expected_count = 2 if self.target_kind is AttachmentTargetKind.FACE else 0
        if len(self.parameters) != expected_count:
            raise ValueError(
                "Face attachments require two surface parameters; other targets require none."
            )
        _validate_metadata(self.metadata, "Cable-end connection metadata")
        if not isinstance(self.attachment_id, UUID):
            raise ValueError("Cable-end connection identity is invalid.")
        if self.parent_attachment_id is not None and not isinstance(
            self.parent_attachment_id, UUID
        ):
            raise ValueError("Cable-end connection parent identity is invalid.")
        if self.parent_attachment_id == self.attachment_id:
            raise ValueError("A cable-end connection cannot parent itself.")
        if not isinstance(self.ordered_control_ids, tuple) or any(
            not isinstance(control_id, UUID) for control_id in self.ordered_control_ids
        ):
            raise ValueError("Cable-end connection controls must be an ordered UUID tuple.")
        if len(set(self.ordered_control_ids)) != len(self.ordered_control_ids):
            raise ValueError("Cable-end connection controls must be unique.")
        if self.ordered_control_ids and not self.has_target:
            raise ValueError("A cable-end connection requires a target before it can own controls.")
        if not isinstance(self.visual_overrides, CableVisualOverrides):
            raise ValueError("Cable-end connection visual overrides are invalid.")
        if self.shielding_target is not None and not isinstance(
            self.shielding_target, CableEndTarget
        ):
            raise ValueError("Cable-end shielding target is invalid.")

    @property
    def display_name(self) -> str:
        """
        Return the explicit alias or the saved inherited target name.
        """
        return self.name.strip() or self.inherited_name.strip() or "Connection"

    @property
    def has_target(self) -> bool:
        """
        Return whether this saved connection node owns a Fusion target.
        """
        return self.target_kind is not None


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
    attachment: Optional[CableEndAttachment] = None
    additional_attachments: tuple[CableEndAttachment, ...] = ()

    def __post_init__(self) -> None:
        """
        Require unambiguous searchable cable-end metadata.
        """
        _validate_metadata(self.metadata, "Cable-end metadata")
        if not isinstance(self.additional_attachments, tuple) or any(
            not isinstance(item, CableEndAttachment) for item in self.additional_attachments
        ):
            raise ValueError("Additional cable-end connections must be an ordered tuple.")
        if self.attachment is None and self.additional_attachments:
            raise ValueError("Additional cable-end connections require a primary connection.")
        attachment_ids = tuple(item.attachment_id for item in self.attachments)
        if len(set(attachment_ids)) != len(attachment_ids):
            raise ValueError("Cable-end connection identities must be unique.")
        target_tokens = tuple(item.entity_token for item in self.attachments if item.has_target)
        if len(set(target_tokens)) != len(target_tokens):
            raise ValueError("Cable-end connection targets must be unique.")
        attachments_by_id = {item.attachment_id: item for item in self.attachments}
        for item in self.attachments:
            parent_id = item.parent_attachment_id
            if parent_id is None:
                continue
            parent = attachments_by_id.get(parent_id)
            if parent is None:
                raise ValueError("Cable-end connection parent does not exist.")
            if parent.target_kind is not AttachmentTargetKind.PROFILE:
                raise ValueError("Child connections require a sketch-profile parent.")
        for item in self.attachments:
            visited: set[UUID] = set()
            ancestor = item
            while ancestor.parent_attachment_id is not None:
                if ancestor.attachment_id in visited:
                    raise ValueError("Cable-end connection ancestry must not contain a cycle.")
                visited.add(ancestor.attachment_id)
                ancestor = attachments_by_id[ancestor.parent_attachment_id]

    @property
    def attachments(self) -> tuple[CableEndAttachment, ...]:
        """
        Return every external connection node in stable display order.
        """
        return (
            (self.attachment,) if self.attachment is not None else ()
        ) + self.additional_attachments

    def attachment_children(
        self, parent_attachment_id: Optional[UUID]
    ) -> tuple[CableEndAttachment, ...]:
        """
        Return direct children of the cable end or one connection node in stable order.
        """
        return tuple(
            item for item in self.attachments if item.parent_attachment_id == parent_attachment_id
        )

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
    Attach one physical end to a pathway boundary before or after cable assignment.

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
    name: str = ""

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

    def cable_end_attachment_materials(
        self,
        group: CableGroupDefinition,
        connection_id: UUID,
        attachment_id: UUID,
    ) -> CableMaterialSettings:
        """
        Resolve branch visuals and connector-level shielding inheritance.
        """
        connection, attachment = self._cable_end_attachment_context(
            group, connection_id, attachment_id
        )
        siblings = connection.attachment_children(attachment.parent_attachment_id)
        parent = (
            self.cable_group_materials(group)
            if attachment.parent_attachment_id is None
            else self.cable_end_attachment_materials(
                group, connection_id, attachment.parent_attachment_id
            )
        )
        if len(siblings) > 1:
            return attachment.visual_overrides.resolve(parent)
        shielding = attachment.visual_overrides.shielding
        return parent if shielding is None else replace(parent, shielding=shielding)

    def cable_end_attachment_diameter(
        self,
        group: CableGroupDefinition,
        connection_id: UUID,
        attachment_id: UUID,
    ) -> float:
        """
        Resolve one connection branch diameter from its parent cable group.
        """
        connection, attachment = self._cable_end_attachment_context(
            group, connection_id, attachment_id
        )
        siblings = connection.attachment_children(attachment.parent_attachment_id)
        parent_diameter_mm = (
            group.diameter_mm
            if attachment.parent_attachment_id is None
            else self.cable_end_attachment_diameter(
                group, connection_id, attachment.parent_attachment_id
            )
        )
        if len(siblings) <= 1:
            return parent_diameter_mm
        diameter_mm = attachment.visual_overrides.diameter_mm
        return parent_diameter_mm / len(siblings) if diameter_mm is None else diameter_mm

    def _cable_end_attachment_context(
        self,
        group: CableGroupDefinition,
        connection_id: UUID,
        attachment_id: UUID,
    ) -> tuple[Connection, CableEndAttachment]:
        """
        Resolve one attachment and its owning cable end within a cable group.
        """
        if connection_id not in group.connection_ids:
            raise ValueError("Cable-end connection does not belong to the cable group.")
        connection = next(
            (item for item in self.connections if item.connection_id == connection_id),
            None,
        )
        if connection is None:
            raise ValueError("Cable-end connection references a missing cable end.")
        attachment = next(
            (item for item in connection.attachments if item.attachment_id == attachment_id),
            None,
        )
        if attachment is None:
            raise ValueError("Cable-end connection does not exist.")
        return connection, attachment

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
