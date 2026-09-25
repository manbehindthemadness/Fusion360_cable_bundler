"""
Declarative definitions for Harness Builder Fusion commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# noinspection PyUnresolvedReferences
import adsk.core

from .commands.attachments import AttachCableEndCreatedHandler
from .commands.ends import AddStandaloneEndCreatedHandler
from .commands.harness import CreateHarnessCreatedHandler
from .commands.interfaces import AddInterfaceCreatedHandler
from .commands.junctions import (
    AddJunctionCreatedHandler,
    AddJunctionRelationshipCreatedHandler,
)
from .commands.pathways import (
    AddPathwayCreatedHandler,
    AppendGatesCreatedHandler,
    SegmentCreatedHandler,
)
from .commands.refines import EditRefineCreatedHandler, RefineCreatedHandler
from .constants import (
    ADD_END_COMMAND_ID,
    ADD_END_COMMAND_NAME,
    ADD_END_RESOURCE_FOLDER,
    ADD_INTERFACE_COMMAND_ID,
    ADD_INTERFACE_COMMAND_NAME,
    ADD_JUNCTION_COMMAND_ID,
    ADD_JUNCTION_COMMAND_NAME,
    ADD_JUNCTION_RELATIONSHIP_COMMAND_ID,
    ADD_JUNCTION_RELATIONSHIP_COMMAND_NAME,
    ADD_PATHWAY_COMMAND_ID,
    ADD_PATHWAY_COMMAND_NAME,
    ADD_PATHWAY_RESOURCE_FOLDER,
    ADD_REFINE_COMMAND_ID,
    ADD_REFINE_COMMAND_NAME,
    APPEND_GATES_COMMAND_ID,
    APPEND_GATES_COMMAND_NAME,
    ATTACH_CABLE_END_COMMAND_ID,
    ATTACH_CABLE_END_COMMAND_NAME,
    COMMAND_DESCRIPTION,
    COMMAND_ID,
    COMMAND_NAME,
    COMMAND_RESOURCE_FOLDER,
    CREATE_COMMAND_ID,
    CREATE_COMMAND_NAME,
    EDIT_REFINE_COMMAND_ID,
    EDIT_REFINE_COMMAND_NAME,
    SEGMENT_PATHWAY_COMMAND_ID,
    SEGMENT_PATHWAY_COMMAND_NAME,
)
from .palette import ShowPaletteCreatedHandler


@dataclass(frozen=True)
class CommandSpec:
    """
    Describe one registered Fusion command and its command-created handler factory.
    """

    command_id: str
    name: str
    description: str
    resource_folder: str
    handler_factory: Callable[[], adsk.core.CommandCreatedEventHandler]


COMMAND_SPECS = (
    CommandSpec(
        COMMAND_ID,
        COMMAND_NAME,
        COMMAND_DESCRIPTION,
        COMMAND_RESOURCE_FOLDER,
        ShowPaletteCreatedHandler,
    ),
    CommandSpec(
        CREATE_COMMAND_ID,
        CREATE_COMMAND_NAME,
        "Create an empty procedural harness definition.",
        COMMAND_RESOURCE_FOLDER,
        CreateHarnessCreatedHandler,
    ),
    CommandSpec(
        ADD_PATHWAY_COMMAND_ID,
        ADD_PATHWAY_COMMAND_NAME,
        "Create a reusable pathway from ordered sketch profiles.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        AddPathwayCreatedHandler,
    ),
    CommandSpec(
        ADD_JUNCTION_COMMAND_ID,
        ADD_JUNCTION_COMMAND_NAME,
        "Create an unconnected junction from an unused sketch profile.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        AddJunctionCreatedHandler,
    ),
    CommandSpec(
        ADD_INTERFACE_COMMAND_ID,
        ADD_INTERFACE_COMMAND_NAME,
        "Reference selected bodies, sketches, or one component occurrence.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        AddInterfaceCreatedHandler,
    ),
    CommandSpec(
        ADD_JUNCTION_RELATIONSHIP_COMMAND_ID,
        ADD_JUNCTION_RELATIONSHIP_COMMAND_NAME,
        "Attach a junction to selected pathway-ending geometry.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        AddJunctionRelationshipCreatedHandler,
    ),
    CommandSpec(
        ADD_END_COMMAND_ID,
        ADD_END_COMMAND_NAME,
        "Create an unassigned end at an existing pathway boundary.",
        ADD_END_RESOURCE_FOLDER,
        AddStandaloneEndCreatedHandler,
    ),
    CommandSpec(
        ATTACH_CABLE_END_COMMAND_ID,
        ATTACH_CABLE_END_COMMAND_NAME,
        "Attach a cable end to external Fusion geometry.",
        ADD_END_RESOURCE_FOLDER,
        AttachCableEndCreatedHandler,
    ),
    CommandSpec(
        APPEND_GATES_COMMAND_ID,
        APPEND_GATES_COMMAND_NAME,
        "Append ordered sketch profiles to an existing pathway.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        AppendGatesCreatedHandler,
    ),
    CommandSpec(
        ADD_REFINE_COMMAND_ID,
        ADD_REFINE_COMMAND_NAME,
        "Insert an unconstrained routing point on a pathway spine.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        RefineCreatedHandler,
    ),
    CommandSpec(
        SEGMENT_PATHWAY_COMMAND_ID,
        SEGMENT_PATHWAY_COMMAND_NAME,
        "Split a pathway at an interior routing control.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        SegmentCreatedHandler,
    ),
    CommandSpec(
        EDIT_REFINE_COMMAND_ID,
        EDIT_REFINE_COMMAND_NAME,
        "Move, rotate, or resize an existing refine point.",
        ADD_PATHWAY_RESOURCE_FOLDER,
        EditRefineCreatedHandler,
    ),
)


def register_commands(
    user_interface: adsk.core.UserInterface,
) -> dict[str, adsk.core.CommandDefinition]:
    """
    Register all native commands and retain their creation handlers.

    Raises:
        RuntimeError: If Fusion rejects a definition or handler.
    """
    from .runtime import runtime

    definitions: dict[str, adsk.core.CommandDefinition] = {}
    for spec in COMMAND_SPECS:
        definition = user_interface.commandDefinitions.addButtonDefinition(
            spec.command_id,
            spec.name,
            spec.description,
            spec.resource_folder,
        )
        if definition is None:
            raise RuntimeError(f"Fusion did not create the {spec.name} command definition.")
        handler = spec.handler_factory()
        if not definition.commandCreated.add(handler):
            raise RuntimeError(f"Fusion did not register the {spec.name} command handler.")
        runtime.handler_registry.retain(handler)
        definitions[spec.command_id] = definition
    return definitions
