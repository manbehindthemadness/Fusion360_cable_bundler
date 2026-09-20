"""
Focused transactional edits for persisted harness definitions.
"""

from .ends import (
    add_end_refine,
    append_end_guides,
    remove_standalone_end,
    rename_standalone_end,
    switch_standalone_end,
)
from .junctions import (
    add_junction,
    add_junction_relationship,
    remove_junction,
    remove_junction_relationship,
    rename_junction,
    suggest_junction_name,
    update_junction_relationships,
)
from .pathways import (
    add_pathway_refine,
    append_pathway_gates,
    move_pathway_gate,
    remove_pathway,
    remove_pathway_gate,
    rename_pathway,
    segment_pathway,
    suggest_pathway_extension_name,
    update_pathway_refine,
)
from .properties import (
    set_harness_material_defaults,
    set_harness_properties,
    set_interpolation,
)
from .types import HarnessEditError, HarnessEditGateway, PathwaySegmentResult

__all__ = [
    "HarnessEditError",
    "HarnessEditGateway",
    "PathwaySegmentResult",
    "add_end_refine",
    "add_junction",
    "add_junction_relationship",
    "add_pathway_refine",
    "append_end_guides",
    "append_pathway_gates",
    "move_pathway_gate",
    "remove_junction",
    "remove_junction_relationship",
    "remove_pathway",
    "remove_pathway_gate",
    "remove_standalone_end",
    "rename_junction",
    "rename_pathway",
    "rename_standalone_end",
    "segment_pathway",
    "set_harness_material_defaults",
    "set_harness_properties",
    "set_interpolation",
    "suggest_junction_name",
    "suggest_pathway_extension_name",
    "switch_standalone_end",
    "update_junction_relationships",
    "update_pathway_refine",
]
