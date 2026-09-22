"""
Tests for pure harness definition validation.
"""

from dataclasses import replace
from uuid import UUID

from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableGroupDefinition,
    CableVisualOverrides,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    PathwayDefinition,
    PathwayEndpoint,
    StandaloneEndDefinition,
    validate_harness,
)


def test_accepts_complete_harness(valid_harness: HarnessDefinition) -> None:
    """
    Accept a complete logical route without consulting Fusion geometry.
    """
    issues = validate_harness(valid_harness)

    assert issues == ()


def test_rejects_an_empty_cable_group_system(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require at least one generation-ready cable group.
    """
    empty = replace(valid_harness, cable_groups=())
    issues = validate_harness(empty)

    assert any(
        issue.code == "missing_cable_groups"
        and issue.message == "At least one cable group is required."
        for issue in issues
    )


def test_validates_standalone_end_references_and_connection_ownership(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require valid placement and prevent duplicate standalone-end ownership.
    """
    standalone = StandaloneEndDefinition(
        valid_harness.connections[0].connection_id,
        valid_harness.pathways[0].pathway_id,
        PathwayEndpoint.START,
    )
    definition = replace(
        valid_harness,
        standalone_ends=(*valid_harness.standalone_ends, standalone),
    )

    issues = validate_harness(definition)

    assert any(issue.code == "duplicate_endpoint" for issue in issues)


def test_validates_cable_group_membership_and_pathway_boundaries(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require two located members and forbid repeated membership or boundaries.
    """
    first = CableGroupDefinition(
        UUID("60000000-0000-0000-0000-000000000001"),
        (valid_harness.connections[0].connection_id,),
    )
    repeated = CableGroupDefinition(
        UUID("60000000-0000-0000-0000-000000000002"),
        (
            valid_harness.connections[0].connection_id,
            valid_harness.connections[1].connection_id,
        ),
    )
    issues = validate_harness(replace(valid_harness, cable_groups=(first, repeated)))

    assert any(issue.code == "undersized_cable_group" for issue in issues)
    assert any(issue.code == "duplicate_cable_group_member" for issue in issues)


def test_rejects_nonpositive_cable_group_diameter(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require connected-cable construction diameters to remain physically usable.
    """
    group = CableGroupDefinition(
        UUID("60000000-0000-0000-0000-000000000010"),
        tuple(connection.connection_id for connection in valid_harness.connections),
        0.0,
    )

    issues = validate_harness(replace(valid_harness, cable_groups=(group,)))

    assert any(issue.code == "invalid_cable_group_diameter" for issue in issues)


def test_rejects_connection_diameters_above_parent_cable(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Bound the sum of resolved divided-branch diameters by the parent diameter.
    """
    connection = replace(
        valid_harness.connections[0],
        attachment=CableEndAttachment(
            None,
            attachment_id=UUID(int=801),
            visual_overrides=CableVisualOverrides(diameter_mm=1.0),
        ),
        additional_attachments=(CableEndAttachment(None, attachment_id=UUID(int=802)),),
    )
    definition = replace(
        valid_harness,
        connections=(connection, *valid_harness.connections[1:]),
    )

    issues = validate_harness(definition)

    assert any(issue.code == "connection_diameter_budget_exceeded" for issue in issues)


def test_rejects_nested_connection_diameters_above_immediate_parent(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Apply the diameter budget independently at every connection-tree branch.
    """
    root_id = UUID(int=811)
    root = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "root-profile",
        "Root",
        attachment_id=root_id,
        visual_overrides=CableVisualOverrides(diameter_mm=0.7),
    )
    connection = replace(
        valid_harness.connections[0],
        attachment=root,
        additional_attachments=(
            CableEndAttachment(None, attachment_id=UUID(int=812)),
            CableEndAttachment(
                None,
                attachment_id=UUID(int=813),
                parent_attachment_id=root_id,
                visual_overrides=CableVisualOverrides(diameter_mm=0.5),
            ),
            CableEndAttachment(
                None,
                attachment_id=UUID(int=814),
                parent_attachment_id=root_id,
            ),
        ),
    )
    definition = replace(
        valid_harness,
        connections=(connection, *valid_harness.connections[1:]),
    )

    issues = validate_harness(definition)

    assert any(issue.code == "connection_diameter_budget_exceeded" for issue in issues)


def test_rejects_distinct_group_members_at_the_same_pathway_end(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep one cable group from containing two physical ends on one boundary.
    """
    first_id = UUID("63000000-0000-0000-0000-000000000001")
    second_id = UUID("63000000-0000-0000-0000-000000000002")
    pathway_id = valid_harness.pathways[0].pathway_id
    definition = replace(
        valid_harness,
        connections=(
            *valid_harness.connections,
            Connection(first_id, "First", "first-token"),
            Connection(second_id, "Second", "second-token"),
        ),
        standalone_ends=(
            StandaloneEndDefinition(first_id, pathway_id, PathwayEndpoint.START),
            StandaloneEndDefinition(second_id, pathway_id, PathwayEndpoint.START),
        ),
        cable_groups=(
            CableGroupDefinition(
                UUID("60000000-0000-0000-0000-000000000003"),
                (first_id, second_id),
            ),
        ),
    )

    issues = validate_harness(definition)

    assert any(issue.code == "duplicate_cable_group_boundary" for issue in issues)


def test_accepts_isolated_and_single_ended_junctions(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Allow zero or one endpoint relationship during incremental construction.
    """
    control = ControlStructure(
        UUID("37000000-0000-0000-0000-000000000001"),
        "Routing Gate 02",
        ControlKind.ROUTING_GATE,
        "isolated-profile-token",
    )
    junction = JunctionDefinition(
        UUID("37000000-0000-0000-0000-000000000002"),
        "Junction 01",
        control.control_id,
    )
    isolated = replace(
        valid_harness,
        controls=(*valid_harness.controls, control),
        junctions=(junction,),
    )
    assert validate_harness(isolated) == ()

    partial = replace(
        isolated,
        junctions=(
            replace(
                junction,
                pathway_relationships=(
                    JunctionPathwayRelationship(
                        valid_harness.pathways[0].pathway_id,
                        PathwayEndpoint.END,
                    ),
                ),
            ),
        ),
    )
    assert validate_harness(partial) == ()


def test_rejects_claimed_endpoints_and_closed_topology(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep endpoint ownership exclusive and junction topology acyclic.
    """
    first = valid_harness.pathways[0]
    second_id = UUID("35000000-0000-0000-0000-000000000002")
    second = PathwayDefinition(
        second_id,
        "Branch",
        first.routing_mode,
        first.ordered_control_ids,
    )
    controls = tuple(
        ControlStructure(
            UUID(f"37000000-0000-0000-0000-00000000000{index}"),
            f"Junction Gate {index}",
            ControlKind.ROUTING_GATE,
            f"junction-{index}",
        )
        for index in (1, 2)
    )
    first_junction = JunctionDefinition(
        UUID("38000000-0000-0000-0000-000000000001"),
        "Junction 01",
        controls[0].control_id,
        (
            JunctionPathwayRelationship(first.pathway_id, PathwayEndpoint.END),
            JunctionPathwayRelationship(second_id, PathwayEndpoint.START),
        ),
    )
    second_junction = JunctionDefinition(
        UUID("38000000-0000-0000-0000-000000000002"),
        "Junction 02",
        controls[1].control_id,
        (
            JunctionPathwayRelationship(first.pathway_id, PathwayEndpoint.END),
            JunctionPathwayRelationship(second_id, PathwayEndpoint.END),
            JunctionPathwayRelationship(first.pathway_id, PathwayEndpoint.START),
        ),
    )
    definition = replace(
        valid_harness,
        controls=(*valid_harness.controls, *controls),
        pathways=(first, second),
        junctions=(first_junction, second_junction),
    )

    issue_codes = {issue.code for issue in validate_harness(definition)}

    assert "claimed_pathway_endpoint" in issue_codes
    assert "cyclic_junction_topology" in issue_codes
