"""
Shared deterministic fixtures for domain tests.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from cable_bundler.domain import (
    SCHEMA_VERSION,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    PathwayDefinition,
    PathwayEndpoint,
    RoutingMode,
    StandaloneEndDefinition,
    CableGroupDefinition,
)

pytest_plugins = ("tests.fusion_ui_support",)


@pytest.fixture
def valid_harness() -> HarnessDefinition:
    """
    Create a deterministic, logically valid one-group harness.
    """
    start_id = UUID("20000000-0000-0000-0000-000000000001")
    end_id = UUID("20000000-0000-0000-0000-000000000002")
    control_id = UUID("30000000-0000-0000-0000-000000000001")
    pathway_id = UUID("35000000-0000-0000-0000-000000000001")
    definition = HarnessDefinition(
        schema_version=SCHEMA_VERSION,
        harness_id=UUID("40000000-0000-0000-0000-000000000001"),
        name="Harness_001",
        routing_mode=RoutingMode.ROUTING_GATES,
        connections=(
            Connection(start_id, "J1 / Pin 1", "fusion-start-token"),
            Connection(end_id, "J2 / Pin 4", "fusion-end-token"),
        ),
        controls=(
            ControlStructure(
                control_id,
                "Routing Gate 01",
                ControlKind.ROUTING_GATE,
                "fusion-gate-token",
            ),
        ),
        pathways=(
            PathwayDefinition(
                pathway_id,
                "Main Pathway",
                RoutingMode.ROUTING_GATES,
                (control_id,),
            ),
        ),
        standalone_ends=(
            StandaloneEndDefinition(start_id, pathway_id, PathwayEndpoint.START),
            StandaloneEndDefinition(end_id, pathway_id, PathwayEndpoint.END),
        ),
        cable_groups=(
            CableGroupDefinition(
                cable_group_id=UUID("50000000-0000-0000-0000-000000000001"),
                connection_ids=(start_id, end_id),
                diameter_mm=1.2,
            ),
        ),
    )
    return definition
