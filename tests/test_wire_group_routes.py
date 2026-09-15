"""
Tests for topology-derived wire-group preview planning.
"""

from dataclasses import replace
from uuid import UUID

import pytest

from wire_bundler.application import WireGroupControlStep, plan_wire_group_routes
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
    WireGroupDefinition,
)


def test_plans_one_deterministic_leg_for_two_grouped_ends(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Traverse one pathway exactly once regardless of group member insertion order.
    """
    wire = valid_harness.wires[0]
    group_id = UUID("60000000-0000-0000-0000-000000000001")
    forward = replace(
        valid_harness,
        wire_groups=(
            WireGroupDefinition(group_id, (wire.start_connection_id, wire.end_connection_id)),
        ),
    )
    reverse = replace(
        forward,
        wire_groups=(
            WireGroupDefinition(group_id, (wire.end_connection_id, wire.start_connection_id)),
        ),
    )

    forward_leg = plan_wire_group_routes(forward)[0]
    reverse_leg = plan_wire_group_routes(reverse)[0]

    assert forward_leg.pathway_ids == wire.ordered_pathway_ids
    assert [step.control_id for step in forward_leg.control_steps] == list(wire.ordered_control_ids)
    expected_reverse = forward_leg.start_connection_id == wire.end_connection_id
    assert all(step.reversed is expected_reverse for step in forward_leg.control_steps)
    assert reverse_leg == forward_leg


def test_plans_y_legs_once_through_a_junction(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Split a three-ended group at its hub without repeating any pathway.
    """
    definition, connection_ids, pathway_ids, junction_control_id = _y_harness(valid_harness)

    legs = plan_wire_group_routes(definition)

    assert len(legs) == 3
    assert sorted(pathway_id for leg in legs for pathway_id in leg.pathway_ids) == sorted(
        pathway_ids
    )
    assert {
        connection_id
        for leg in legs
        for connection_id in (
            leg.start_connection_id,
            leg.end_connection_id,
        )
        if connection_id is not None
    } == set(connection_ids)
    assert all(
        sum(step.control_id == junction_control_id for step in leg.control_steps) == 1
        for leg in legs
    )
    assert all((leg.start_connection_id is None) != (leg.end_connection_id is None) for leg in legs)


@pytest.mark.parametrize(
    ("pathway_index", "endpoint", "control_index", "expected_reversed"),
    (
        (1, PathwayEndpoint.START, 0, False),
        (0, PathwayEndpoint.END, -1, True),
    ),
)
def test_plans_terminal_lead_from_internal_pathway_boundary(
    valid_harness: HarnessDefinition,
    pathway_index: int,
    endpoint: PathwayEndpoint,
    control_index: int,
    expected_reversed: bool,
) -> None:
    """
    Attach an internal end to the group body without duplicating a pathway span.
    """
    definition, connection_ids, pathway_ids, _junction_control_id = _y_harness(valid_harness)
    attached, connection_id = _with_internal_end(definition, pathway_index, endpoint)

    legs = plan_wire_group_routes(attached)

    lead = next(leg for leg in legs if leg.start_connection_id == connection_id)
    expected_control_id = attached.pathways[pathway_index].ordered_control_ids[control_index]
    represented_connections = [
        identity
        for leg in legs
        for identity in (leg.start_connection_id, leg.end_connection_id)
        if identity is not None
    ]
    assert len(legs) == 4
    assert lead.end_connection_id is None
    assert lead.pathway_ids == ()
    assert lead.control_steps == (WireGroupControlStep(expected_control_id, expected_reversed),)
    assert sorted(pathway_id for leg in legs for pathway_id in leg.pathway_ids) == sorted(
        pathway_ids
    )
    assert sorted(represented_connections, key=str) == sorted(
        (*connection_ids, connection_id), key=str
    )
    assert (
        sum(expected_control_id in {step.control_id for step in leg.control_steps} for leg in legs)
        == 2
    )


def test_rejects_terminal_lead_without_a_pathway_control(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Report when an internal pathway boundary has no body crossing to join.
    """
    definition, _connection_ids, _pathway_ids, _junction_control_id = _y_harness(valid_harness)
    attached, _connection_id = _with_internal_end(
        definition,
        1,
        PathwayEndpoint.START,
    )
    pathways = list(attached.pathways)
    pathways[1] = replace(pathways[1], ordered_control_ids=())

    with pytest.raises(ValueError, match="internal end.*without a routing control"):
        plan_wire_group_routes(replace(attached, pathways=tuple(pathways)))


def test_rejects_multi_end_branching_at_a_terminal_boundary(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep unexpected linear three-terminal metadata from inventing a hub.
    """
    definition, connection_ids, _pathway_ids, _junction_control_id = _y_harness(valid_harness)
    first_pathway = definition.pathways[0]
    second_pathway = definition.pathways[1]
    linear = replace(
        definition,
        junctions=(
            replace(
                definition.junctions[0],
                pathway_relationships=(
                    JunctionPathwayRelationship(first_pathway.pathway_id, PathwayEndpoint.END),
                    JunctionPathwayRelationship(second_pathway.pathway_id, PathwayEndpoint.START),
                ),
            ),
        ),
        standalone_ends=(
            StandaloneEndDefinition(
                connection_ids[0], first_pathway.pathway_id, PathwayEndpoint.START
            ),
            StandaloneEndDefinition(
                connection_ids[1], first_pathway.pathway_id, PathwayEndpoint.END
            ),
            StandaloneEndDefinition(
                connection_ids[2], second_pathway.pathway_id, PathwayEndpoint.END
            ),
        ),
    )

    with pytest.raises(ValueError, match="junction-centered branching"):
        plan_wire_group_routes(linear)


def _with_internal_end(
    definition: HarnessDefinition,
    pathway_index: int,
    endpoint: PathwayEndpoint,
) -> tuple[HarnessDefinition, UUID]:
    """
    Add one grouped end at a pathway boundary already traversed by the group tree.
    """
    connection_id = UUID(int=980 + pathway_index)
    connection = Connection(connection_id, "Internal End", "internal-end")
    group = definition.wire_groups[0]
    updated = replace(
        definition,
        connections=(*definition.connections, connection),
        standalone_ends=(
            *definition.standalone_ends,
            StandaloneEndDefinition(
                connection_id,
                definition.pathways[pathway_index].pathway_id,
                endpoint,
            ),
        ),
        wire_groups=(replace(group, connection_ids=(*group.connection_ids, connection_id)),),
    )
    return updated, connection_id


def _y_harness(
    valid_harness: HarnessDefinition,
) -> tuple[HarnessDefinition, tuple[UUID, ...], tuple[UUID, ...], UUID]:
    """
    Return three terminal pathways meeting at one routing-gate junction.
    """
    connection_ids = tuple(UUID(int=700 + index) for index in range(3))
    pathway_ids = tuple(UUID(int=800 + index) for index in range(3))
    pathway_control_ids = tuple(UUID(int=900 + index) for index in range(3))
    junction_control_id = UUID(int=950)
    connections = tuple(
        Connection(connection_id, f"End {index + 1}", f"end-{index + 1}")
        for index, connection_id in enumerate(connection_ids)
    )
    controls = tuple(
        ControlStructure(
            control_id,
            f"Pathway Gate {index + 1}",
            ControlKind.ROUTING_GATE,
            f"gate-{index + 1}",
        )
        for index, control_id in enumerate(pathway_control_ids)
    ) + (
        ControlStructure(
            junction_control_id,
            "Junction Gate",
            ControlKind.ROUTING_GATE,
            "junction-gate",
        ),
    )
    pathways = tuple(
        PathwayDefinition(
            pathway_id,
            f"Pathway {index + 1}",
            RoutingMode.ROUTING_GATES,
            (pathway_control_ids[index],),
        )
        for index, pathway_id in enumerate(pathway_ids)
    )
    relationships = (
        JunctionPathwayRelationship(pathway_ids[0], PathwayEndpoint.END),
        JunctionPathwayRelationship(pathway_ids[1], PathwayEndpoint.START),
        JunctionPathwayRelationship(pathway_ids[2], PathwayEndpoint.START),
    )
    standalone_ends = (
        StandaloneEndDefinition(connection_ids[0], pathway_ids[0], PathwayEndpoint.START),
        StandaloneEndDefinition(connection_ids[1], pathway_ids[1], PathwayEndpoint.END),
        StandaloneEndDefinition(connection_ids[2], pathway_ids[2], PathwayEndpoint.END),
    )
    definition = replace(
        valid_harness,
        connections=connections,
        controls=controls,
        pathways=pathways,
        wires=(),
        junctions=(
            JunctionDefinition(UUID(int=960), "Junction", junction_control_id, relationships),
        ),
        standalone_ends=standalone_ends,
        wire_groups=(WireGroupDefinition(UUID(int=970), connection_ids),),
    )
    return definition, connection_ids, pathway_ids, junction_control_id
