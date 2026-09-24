"""
Deterministic validation for harness definitions before generation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from .model import (
    SCHEMA_VERSION,
    ControlKind,
    HarnessDefinition,
    JunctionDefinition,
    PathwayEndpoint,
    RoutingMode,
)


@dataclass(frozen=True)
class ValidationIssue:
    """
    Describe one actionable harness validation failure.
    """

    code: str
    path: str
    message: str


def validate_harness(definition: HarnessDefinition) -> tuple[ValidationIssue, ...]:
    """
    Return logical-readiness issues in deterministic order without accessing Fusion.
    """
    issues: list[ValidationIssue] = []
    if definition.schema_version != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "unsupported_schema_version",
                "schema_version",
                f"Expected schema version {SCHEMA_VERSION}.",
            )
        )
    if not definition.name.strip():
        issues.append(ValidationIssue("missing_name", "name", "Harness name is required."))
    if (
        isinstance(definition.minimum_clearance_mm, bool)
        or not isinstance(definition.minimum_clearance_mm, (int, float))
        or not math.isfinite(definition.minimum_clearance_mm)
        or definition.minimum_clearance_mm < 0.0
    ):
        issues.append(
            ValidationIssue(
                "invalid_minimum_clearance",
                "minimum_clearance_mm",
                "Minimum member clearance must be finite and nonnegative.",
            )
        )
    if not definition.cable_groups:
        issues.append(
            ValidationIssue(
                "missing_cable_groups",
                "cable_groups",
                "At least one cable group is required.",
            )
        )

    _validate_unique_ids(definition, issues)
    _validate_connections(definition, issues)
    _validate_controls(definition, issues)
    _validate_pathways(definition, issues)
    _validate_junctions(definition, issues)
    _validate_standalone_ends(definition, issues)
    _validate_cable_groups(definition, issues)
    _validate_attachment_associations(definition, issues)
    return tuple(issues)


def _validate_unique_ids(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Require identities to be unique across the complete harness definition.
    """
    seen: dict[UUID, str] = {definition.harness_id: "harness_id"}
    identities = [
        *(
            (connection.connection_id, f"connections[{index}].connection_id")
            for index, connection in enumerate(definition.connections)
        ),
        *(
            (control.control_id, f"controls[{index}].control_id")
            for index, control in enumerate(definition.controls)
        ),
        *(
            (pathway.pathway_id, f"pathways[{index}].pathway_id")
            for index, pathway in enumerate(definition.pathways)
        ),
        *(
            (junction.junction_id, f"junctions[{index}].junction_id")
            for index, junction in enumerate(definition.junctions)
        ),
        *(
            (group.cable_group_id, f"cable_groups[{index}].cable_group_id")
            for index, group in enumerate(definition.cable_groups)
        ),
        *(
            (association.association_id, f"attachment_associations[{index}].association_id")
            for index, association in enumerate(definition.attachment_associations)
        ),
        *(
            (
                attachment.attachment_id,
                f"connections[{connection_index}].attachments[{attachment_index}].attachment_id",
            )
            for connection_index, connection in enumerate(definition.connections)
            for attachment_index, attachment in enumerate(connection.attachments)
        ),
    ]
    for identity, path in identities:
        previous_path = seen.get(identity)
        if previous_path is not None:
            issues.append(
                ValidationIssue(
                    "duplicate_id",
                    path,
                    f"Identity duplicates {previous_path}.",
                )
            )
        else:
            seen[identity] = path


def _validate_connections(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Validate physical connection references.
    """
    for index, connection in enumerate(definition.connections):
        path = f"connections[{index}]"
        if not connection.name.strip():
            issues.append(
                ValidationIssue(
                    "missing_connection_name",
                    f"{path}.name",
                    "Connection name is required.",
                )
            )
        if not connection.entity_token.strip():
            issues.append(
                ValidationIssue(
                    "missing_connection_geometry",
                    f"{path}.entity_token",
                    "Connection must reference Fusion geometry.",
                )
            )


def _validate_controls(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Validate routing-control references.
    """
    for index, control in enumerate(definition.controls):
        path = f"controls[{index}]"
        if not control.name.strip():
            issues.append(
                ValidationIssue("missing_control_name", f"{path}.name", "Control name is required.")
            )
        if control.kind is ControlKind.REFINE and control.refine_geometry is None:
            issues.append(
                ValidationIssue(
                    "missing_refine_geometry",
                    f"{path}.refine_geometry",
                    "Refine point must retain its saved position and orientation.",
                )
            )
        elif control.kind is not ControlKind.REFINE and not control.entity_token.strip():
            issues.append(
                ValidationIssue(
                    "missing_control_geometry",
                    f"{path}.entity_token",
                    "Control must reference Fusion geometry.",
                )
            )


def _validate_pathways(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Validate pathway names, ordered gates, and routing-mode compatibility.
    """
    controls_by_id = {control.control_id: control for control in definition.controls}
    seen_names: dict[str, str] = {}
    for index, pathway in enumerate(definition.pathways):
        path = f"pathways[{index}]"
        normalized_name = pathway.name.strip()
        if not normalized_name:
            issues.append(
                ValidationIssue(
                    "missing_pathway_name",
                    f"{path}.name",
                    "Pathway name is required.",
                )
            )
        else:
            name_key = normalized_name.casefold()
            previous_path = seen_names.get(name_key)
            if previous_path is not None:
                issues.append(
                    ValidationIssue(
                        "duplicate_pathway_name",
                        f"{path}.name",
                        f"Pathway name duplicates {previous_path}.",
                    )
                )
            else:
                seen_names[name_key] = f"{path}.name"

        if not pathway.ordered_control_ids:
            issues.append(
                ValidationIssue(
                    "missing_pathway_controls",
                    f"{path}.ordered_control_ids",
                    "At least one ordered gate is required.",
                )
            )

        expected_kind: ControlKind = (
            ControlKind.ROUTING_GATE
            if pathway.routing_mode is RoutingMode.ROUTING_GATES
            else ControlKind.PROFILE_GATE
        )
        seen_control_ids: set[UUID] = set()
        for control_index, control_id in enumerate(pathway.ordered_control_ids):
            control_path = f"{path}.ordered_control_ids[{control_index}]"
            control = controls_by_id.get(control_id)
            if control is None:
                issues.append(
                    ValidationIssue(
                        "missing_pathway_control_reference",
                        control_path,
                        "Referenced routing control does not exist.",
                    )
                )
            elif control.kind not in {expected_kind, ControlKind.REFINE}:
                issues.append(
                    ValidationIssue(
                        "pathway_control_mode_mismatch",
                        control_path,
                        f"Control kind must be {expected_kind.value} for this pathway.",
                    )
                )
            if control_id in seen_control_ids:
                issues.append(
                    ValidationIssue(
                        "duplicate_pathway_control",
                        control_path,
                        "A gate may appear only once in a pathway.",
                    )
                )
            else:
                seen_control_ids.add(control_id)


def _validate_junctions(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Validate junction controls and endpoint-qualified acyclic relationships.
    """
    controls = {control.control_id: control for control in definition.controls}
    pathway_ids = {pathway.pathway_id for pathway in definition.pathways}
    pathway_control_ids = {
        control_id for pathway in definition.pathways for control_id in pathway.ordered_control_ids
    }
    names: dict[str, str] = {}
    controls_in_use: dict[UUID, str] = {}
    endpoint_owners: dict[tuple[UUID, PathwayEndpoint], str] = {}
    for index, junction in enumerate(definition.junctions):
        path = f"junctions[{index}]"
        normalized_name = junction.name.strip()
        if not normalized_name:
            issues.append(
                ValidationIssue(
                    "missing_junction_name", f"{path}.name", "Junction name is required."
                )
            )
        else:
            key = normalized_name.casefold()
            if key in names:
                issues.append(
                    ValidationIssue(
                        "duplicate_junction_name",
                        f"{path}.name",
                        f"Junction name duplicates {names[key]}.",
                    )
                )
            else:
                names[key] = f"{path}.name"

        control = controls.get(junction.control_id)
        if control is None:
            issues.append(
                ValidationIssue(
                    "missing_junction_control_reference",
                    f"{path}.control_id",
                    "Referenced junction control does not exist.",
                )
            )
        elif junction.control_id in pathway_control_ids:
            issues.append(
                ValidationIssue(
                    "junction_control_in_pathway",
                    f"{path}.control_id",
                    "A junction control must not also belong to a pathway.",
                )
            )
        previous_control_path = controls_in_use.get(junction.control_id)
        if previous_control_path is not None:
            issues.append(
                ValidationIssue(
                    "duplicate_junction_control",
                    f"{path}.control_id",
                    f"Junction control duplicates {previous_control_path}.",
                )
            )
        else:
            controls_in_use[junction.control_id] = f"{path}.control_id"

        seen_relationships: set[tuple[UUID, PathwayEndpoint]] = set()
        for relationship_index, relationship in enumerate(junction.pathway_relationships):
            relationship_path = f"{path}.pathway_relationships[{relationship_index}]"
            key = (relationship.pathway_id, relationship.endpoint)
            if relationship.pathway_id not in pathway_ids:
                issues.append(
                    ValidationIssue(
                        "missing_junction_pathway_reference",
                        f"{relationship_path}.pathway_id",
                        "Referenced junction pathway does not exist.",
                    )
                )
            if key in seen_relationships:
                issues.append(
                    ValidationIssue(
                        "duplicate_junction_pathway_relationship",
                        relationship_path,
                        "A junction may reference a pathway endpoint only once.",
                    )
                )
                continue
            seen_relationships.add(key)
            previous_owner = endpoint_owners.get(key)
            if previous_owner is not None:
                issues.append(
                    ValidationIssue(
                        "claimed_pathway_endpoint",
                        relationship_path,
                        f"Pathway endpoint is already related by {previous_owner}.",
                    )
                )
            else:
                endpoint_owners[key] = path

    _validate_junction_cycles(definition.junctions, issues)


def _validate_junction_cycles(
    junctions: tuple[JunctionDefinition, ...],
    issues: list[ValidationIssue],
) -> None:
    """
    Reject closed loops in the bipartite pathway/junction topology.
    """
    parents: dict[tuple[str, UUID], tuple[str, UUID]] = {}

    def root(node: tuple[str, UUID]) -> tuple[str, UUID]:
        parents.setdefault(node, node)
        while parents[node] != node:
            parents[node] = parents[parents[node]]
            node = parents[node]
        return node

    for junction in junctions:
        junction_node = ("junction", junction.junction_id)
        for relationship in junction.pathway_relationships:
            pathway_node = ("pathway", relationship.pathway_id)
            junction_root = root(junction_node)
            pathway_root = root(pathway_node)
            if junction_root == pathway_root:
                issues.append(
                    ValidationIssue(
                        "cyclic_junction_topology",
                        "junctions",
                        "Junction pathway relationships must form an acyclic forest.",
                    )
                )
                return
            parents[pathway_root] = junction_root


def _validate_standalone_ends(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Validate cable-end placement without requiring a cable assignment.
    """
    connection_ids = {connection.connection_id for connection in definition.connections}
    pathway_ids = {pathway.pathway_id for pathway in definition.pathways}
    controls = {control.control_id: control for control in definition.controls}
    pathway_control_ids = {
        control_id for pathway in definition.pathways for control_id in pathway.ordered_control_ids
    }
    junction_control_ids = {junction.control_id for junction in definition.junctions}
    owned_control_paths: dict[UUID, str] = {}
    for connection_index, connection in enumerate(definition.connections):
        for attachment_index, attachment in enumerate(connection.attachments):
            attachment_path = (
                f"connections[{connection_index}].attachment"
                if attachment_index == 0
                else (
                    f"connections[{connection_index}].additional_attachments"
                    f"[{attachment_index - 1}]"
                )
            )
            if attachment.ordered_control_ids and not attachment.has_target:
                issues.append(
                    ValidationIssue(
                        "unattached_connection_controls",
                        f"{attachment_path}.ordered_control_ids",
                        "A connection requires target geometry before it can own refines.",
                    )
                )
            seen_attachment_controls: set[UUID] = set()
            for control_index, control_id in enumerate(attachment.ordered_control_ids):
                control_path = f"{attachment_path}.ordered_control_ids[{control_index}]"
                control = controls.get(control_id)
                if control is None:
                    issues.append(
                        ValidationIssue(
                            "missing_connection_control_reference",
                            control_path,
                            "Referenced connection refine does not exist.",
                        )
                    )
                elif control.kind is not ControlKind.REFINE:
                    issues.append(
                        ValidationIssue(
                            "connection_control_kind_mismatch",
                            control_path,
                            "Connection-owned controls must be refine points.",
                        )
                    )
                if control_id in pathway_control_ids or control_id in junction_control_ids:
                    issues.append(
                        ValidationIssue(
                            "shared_connection_control",
                            control_path,
                            "A connection-owned refine must not belong to a pathway or junction.",
                        )
                    )
                previous_path = owned_control_paths.get(control_id)
                if control_id in seen_attachment_controls or previous_path is not None:
                    issues.append(
                        ValidationIssue(
                            "duplicate_connection_control",
                            control_path,
                            "A connection refine may appear only once.",
                        )
                    )
                else:
                    seen_attachment_controls.add(control_id)
                    owned_control_paths[control_id] = control_path
    seen_connections: dict[UUID, str] = {}
    for index, end in enumerate(definition.standalone_ends):
        path = f"standalone_ends[{index}]"
        _validate_reference(
            end.connection_id,
            connection_ids,
            "missing_connection_reference",
            f"{path}.connection_id",
            issues,
        )
        _validate_reference(
            end.pathway_id,
            pathway_ids,
            "missing_pathway_reference",
            f"{path}.pathway_id",
            issues,
        )
        previous_path = seen_connections.get(end.connection_id)
        if previous_path is not None:
            issues.append(
                ValidationIssue(
                    "duplicate_endpoint",
                    f"{path}.connection_id",
                    f"Connection is already assigned at {previous_path}.",
                )
            )
        else:
            seen_connections[end.connection_id] = f"{path}.connection_id"
        seen_end_controls: set[UUID] = set()
        for control_index, control_id in enumerate(end.ordered_control_ids):
            control_path = f"{path}.ordered_control_ids[{control_index}]"
            control = controls.get(control_id)
            if control is None:
                issues.append(
                    ValidationIssue(
                        "missing_end_control_reference",
                        control_path,
                        "Referenced end refine does not exist.",
                    )
                )
            elif control.kind is not ControlKind.REFINE:
                issues.append(
                    ValidationIssue(
                        "end_control_kind_mismatch",
                        control_path,
                        "End-owned controls must be refine points.",
                    )
                )
            if control_id in pathway_control_ids or control_id in junction_control_ids:
                issues.append(
                    ValidationIssue(
                        "shared_end_control",
                        control_path,
                        "An end-owned refine must not belong to a pathway or junction.",
                    )
                )
            previous_path = owned_control_paths.get(control_id)
            if control_id in seen_end_controls or previous_path is not None:
                issues.append(
                    ValidationIssue(
                        "duplicate_end_control",
                        control_path,
                        "An end refine may appear only once.",
                    )
                )
            else:
                seen_end_controls.add(control_id)
                owned_control_paths[control_id] = control_path


def _validate_cable_groups(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Validate exclusive group membership across distinct pathway boundaries.
    """
    connections_by_id = {
        connection.connection_id: connection for connection in definition.connections
    }
    connection_ids = set(connections_by_id)
    locations: dict[UUID, tuple[UUID, PathwayEndpoint]] = {
        end.connection_id: (end.pathway_id, end.endpoint) for end in definition.standalone_ends
    }
    memberships: dict[UUID, str] = {}
    for group_index, group in enumerate(definition.cable_groups):
        group_path = f"cable_groups[{group_index}]"
        valid_group_diameter = not (
            isinstance(group.diameter_mm, bool)
            or not isinstance(group.diameter_mm, (int, float))
            or not math.isfinite(group.diameter_mm)
            or group.diameter_mm <= 0
        )
        if not valid_group_diameter:
            issues.append(
                ValidationIssue(
                    "invalid_cable_group_diameter",
                    f"{group_path}.diameter_mm",
                    "Cable-group diameter must be finite and positive.",
                )
            )
        if len(group.connection_ids) < 2:
            issues.append(
                ValidationIssue(
                    "undersized_cable_group",
                    f"{group_path}.connection_ids",
                    "A cable group must contain at least two ends.",
                )
            )
        boundaries: dict[tuple[UUID, PathwayEndpoint], str] = {}
        for member_index, connection_id in enumerate(group.connection_ids):
            member_path = f"{group_path}.connection_ids[{member_index}]"
            _validate_reference(
                connection_id,
                connection_ids,
                "missing_connection_reference",
                member_path,
                issues,
            )
            connection = connections_by_id.get(connection_id)
            if connection is not None and valid_group_diameter:
                parent_ids = tuple(
                    dict.fromkeys(item.parent_attachment_id for item in connection.attachments)
                )
                for parent_attachment_id in parent_ids:
                    children = connection.attachment_children(parent_attachment_id)
                    if len(children) <= 1:
                        continue
                    parent_diameter_mm = (
                        group.diameter_mm
                        if parent_attachment_id is None
                        else definition.cable_end_attachment_diameter(
                            group, connection_id, parent_attachment_id
                        )
                    )
                    combined_diameter_mm = sum(
                        definition.cable_end_attachment_diameter(
                            group, connection_id, child.attachment_id
                        )
                        for child in children
                    )
                    if combined_diameter_mm > parent_diameter_mm + 1e-9:
                        issues.append(
                            ValidationIssue(
                                "connection_diameter_budget_exceeded",
                                f"{member_path}.connection_diameters",
                                "Connection diameters cannot collectively exceed the parent "
                                "cable diameter.",
                            )
                        )
            previous_membership = memberships.get(connection_id)
            if previous_membership is not None:
                issues.append(
                    ValidationIssue(
                        "duplicate_cable_group_member",
                        member_path,
                        f"Cable end is already grouped at {previous_membership}.",
                    )
                )
            else:
                memberships[connection_id] = member_path
            location = locations.get(connection_id)
            if location is None:
                issues.append(
                    ValidationIssue(
                        "unlocated_cable_group_member",
                        member_path,
                        "A grouped cable end must be assigned to a pathway boundary.",
                    )
                )
                continue
            previous_boundary = boundaries.get(location)
            if previous_boundary is not None:
                issues.append(
                    ValidationIssue(
                        "duplicate_cable_group_boundary",
                        member_path,
                        f"Cable group already contains an end from {previous_boundary}.",
                    )
                )
            else:
                boundaries[location] = member_path


def _validate_attachment_associations(
    definition: HarnessDefinition,
    issues: list[ValidationIssue],
) -> None:
    """
    Require each association to reference two distinct, exclusively grouped nodes.
    """
    attachment_ids = {
        attachment.attachment_id
        for connection in definition.connections
        for attachment in connection.attachments
    }
    memberships: dict[UUID, str] = {}
    for association_index, association in enumerate(definition.attachment_associations):
        path = f"attachment_associations[{association_index}]"
        for member_index, attachment_id in enumerate(association.attachment_ids):
            member_path = f"{path}.attachment_ids[{member_index}]"
            _validate_reference(
                attachment_id,
                attachment_ids,
                "missing_attachment_association_reference",
                member_path,
                issues,
            )
            previous_path = memberships.get(attachment_id)
            if previous_path is not None:
                issues.append(
                    ValidationIssue(
                        "duplicate_attachment_association_member",
                        member_path,
                        f"Attachment node is already associated at {previous_path}.",
                    )
                )
            else:
                memberships[attachment_id] = member_path


def _validate_reference(
    reference_id: UUID,
    available_ids: set[UUID],
    code: str,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    """
    Validate that an identity references an available domain object.
    """
    if reference_id not in available_ids:
        issues.append(ValidationIssue(code, path, "Referenced identity does not exist."))
