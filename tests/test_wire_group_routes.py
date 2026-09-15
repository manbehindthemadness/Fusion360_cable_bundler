"""
Tests for topology-derived wire-group preview planning.
"""

from dataclasses import replace
from uuid import UUID

import pytest

from wire_bundler.application import plan_wire_group_routes
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
