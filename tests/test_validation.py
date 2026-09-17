"""
Tests for pure harness definition validation.
"""

from dataclasses import replace
from uuid import UUID

from wire_bundler.domain import (
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    PathwayDefinition,
    PathwayEndpoint,
    RoutingMode,
    StandaloneEndDefinition,
    WireDefinition,
    WireGroupDefinition,
    validate_harness,
)


def test_accepts_complete_harness(valid_harness: HarnessDefinition) -> None:
    """
    Accept a complete logical route without consulting Fusion geometry.
    """
    issues = validate_harness(valid_harness)

    assert issues == ()


def test_accepts_group_only_harness_and_rejects_an_empty_wire_system(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Treat connected wire groups as generation-ready without legacy wire records.
    """
    wire = valid_harness.wires[0]
    pathway_id = valid_harness.pathways[0].pathway_id
    grouped = replace(
        valid_harness,
        wires=(),
        standalone_ends=(
            StandaloneEndDefinition(
                wire.start_connection_id,
                pathway_id,
                PathwayEndpoint.START,
            ),
            StandaloneEndDefinition(
                wire.end_connection_id,
                pathway_id,
                PathwayEndpoint.END,
            ),
        ),
        wire_groups=(
            WireGroupDefinition(
                UUID("60000000-0000-0000-0000-000000000020"),
                (wire.start_connection_id, wire.end_connection_id),
            ),
        ),
    )

    assert validate_harness(grouped) == ()

    empty = replace(grouped, wire_groups=())
    issues = validate_harness(empty)

    assert any(
        issue.code == "missing_wires"
        and issue.message == "At least one wire or wire group is required."
        for issue in issues
    )


def test_validates_standalone_end_references_and_connection_ownership(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require valid placement and prevent reuse of a wire-owned connection.
    """
    standalone = StandaloneEndDefinition(
        valid_harness.connections[0].connection_id,
        valid_harness.pathways[0].pathway_id,
        PathwayEndpoint.START,
    )
    definition = replace(valid_harness, standalone_ends=(standalone,))

    issues = validate_harness(definition)

    assert any(issue.code == "duplicate_endpoint" for issue in issues)


def test_validates_wire_group_membership_and_pathway_boundaries(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require two located members and forbid repeated membership or boundaries.
    """
    first = WireGroupDefinition(
        UUID("60000000-0000-0000-0000-000000000001"),
        (valid_harness.connections[0].connection_id,),
    )
    repeated = WireGroupDefinition(
        UUID("60000000-0000-0000-0000-000000000002"),
        (
            valid_harness.connections[0].connection_id,
            valid_harness.connections[1].connection_id,
        ),
    )
    issues = validate_harness(replace(valid_harness, wire_groups=(first, repeated)))

    assert any(issue.code == "undersized_wire_group" for issue in issues)
    assert any(issue.code == "duplicate_wire_group_member" for issue in issues)


def test_rejects_nonpositive_wire_group_diameter(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require connected-wire construction diameters to remain physically usable.
    """
    group = WireGroupDefinition(
        UUID("60000000-0000-0000-0000-000000000010"),
        tuple(connection.connection_id for connection in valid_harness.connections),
        0.0,
    )

    issues = validate_harness(replace(valid_harness, wire_groups=(group,)))

    assert any(issue.code == "invalid_wire_group_diameter" for issue in issues)


def test_rejects_distinct_group_members_at_the_same_pathway_end(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep one wire group from containing two physical ends on one boundary.
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
        wire_groups=(
            WireGroupDefinition(
                UUID("60000000-0000-0000-0000-000000000003"),
                (first_id, second_id),
            ),
        ),
    )

    issues = validate_harness(definition)

    assert any(issue.code == "duplicate_wire_group_boundary" for issue in issues)


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
        wires=(),
    )

    issue_codes = {issue.code for issue in validate_harness(definition)}

    assert "claimed_pathway_endpoint" in issue_codes
    assert "cyclic_junction_topology" in issue_codes


def test_reports_missing_references(valid_harness: HarnessDefinition) -> None:
    """
    Report missing profile, connection, and control identities.
    """
    missing_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    invalid_wire = replace(
        valid_harness.wires[0],
        start_connection_id=missing_id,
        profile_id=missing_id,
        ordered_control_ids=(missing_id,),
    )
    definition = replace(valid_harness, wires=(invalid_wire,))

    issue_codes = {issue.code for issue in validate_harness(definition)}

    assert issue_codes == {
        "missing_connection_reference",
        "missing_control_reference",
        "missing_profile_reference",
    }


def test_reports_duplicate_wire_identity_number_and_endpoints(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reject duplicate identities, visible numbers, and physical endpoint use.
    """
    first_wire = valid_harness.wires[0]
    duplicate_wire = WireDefinition(
        wire_id=first_wire.wire_id,
        wire_number=first_wire.wire_number,
        start_connection_id=first_wire.start_connection_id,
        end_connection_id=first_wire.end_connection_id,
        profile_id=first_wire.profile_id,
        ordered_pathway_ids=first_wire.ordered_pathway_ids,
        ordered_control_ids=first_wire.ordered_control_ids,
    )
    definition = replace(valid_harness, wires=(first_wire, duplicate_wire))

    issue_codes = [issue.code for issue in validate_harness(definition)]

    assert "duplicate_id" in issue_codes
    assert "duplicate_wire_number" in issue_codes
    assert issue_codes.count("duplicate_endpoint") == 2


def test_reports_profile_and_route_failures(valid_harness: HarnessDefinition) -> None:
    """
    Reject invalid dimensions, incompatible controls, and incomplete routes.
    """
    profile = replace(valid_harness.profiles[0], diameter_mm=float("nan"))
    control = replace(valid_harness.controls[0], kind=ControlKind.PROFILE_GATE)
    wire = replace(valid_harness.wires[0], wire_number="wire-one", ordered_control_ids=())
    pathway = replace(valid_harness.pathways[0], routing_mode=RoutingMode.ROUTING_GATES)
    definition = replace(
        valid_harness,
        profiles=(profile,),
        controls=(control,),
        pathways=(pathway,),
        wires=(wire,),
    )

    issue_codes = {issue.code for issue in validate_harness(definition)}

    assert issue_codes == {
        "pathway_control_mode_mismatch",
        "invalid_profile_diameter",
        "invalid_wire_number",
        "missing_wire_controls",
    }


def test_reports_invalid_pathway_relationships(valid_harness: HarnessDefinition) -> None:
    """
    Reject empty names, duplicate gates, and missing pathway references.
    """
    missing_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    control_id = valid_harness.controls[0].control_id
    pathway = replace(
        valid_harness.pathways[0],
        name=" ",
        ordered_control_ids=(control_id, control_id, missing_id),
    )
    definition = replace(valid_harness, pathways=(pathway,))

    issue_codes = {issue.code for issue in validate_harness(definition)}

    assert issue_codes == {
        "duplicate_pathway_control",
        "missing_pathway_control_reference",
        "missing_pathway_name",
        "wire_pathway_controls_mismatch",
    }


def test_reports_invalid_wire_pathway_relationships(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reject missing pathway references and route controls that disagree with a pathway.
    """
    missing_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    missing_pathway_wire = replace(
        valid_harness.wires[0],
        ordered_pathway_ids=(missing_id,),
    )
    definition = replace(valid_harness, wires=(missing_pathway_wire,))

    issue_codes = {issue.code for issue in validate_harness(definition)}

    assert issue_codes == {"missing_pathway_reference"}


def test_reports_wire_controls_that_disagree_with_pathway(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Require a wire's flattened control order to match its selected pathways.
    """
    control_id = valid_harness.controls[0].control_id
    mismatched_wire = replace(
        valid_harness.wires[0],
        ordered_control_ids=(control_id, control_id),
    )
    definition = replace(valid_harness, wires=(mismatched_wire,))

    issue_codes = {issue.code for issue in validate_harness(definition)}

    assert issue_codes == {"duplicate_wire_control", "wire_pathway_controls_mismatch"}
