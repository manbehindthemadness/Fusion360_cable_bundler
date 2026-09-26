"""
Stable Fusion command, input, and packaged-resource identifiers.
"""

from __future__ import annotations

from pathlib import Path

from ...domain import RoutingMode

COMMAND_ID = "kev0_cable_bundler_harness_builder"
CREATE_COMMAND_ID = "kev0_cable_bundler_create_harness"
ADD_PATHWAY_COMMAND_ID = "kev0_cable_bundler_add_pathway"
ADD_JUNCTION_COMMAND_ID = "kev0_cable_bundler_add_junction"
ADD_INTERFACE_COMMAND_ID = "kev0_cable_bundler_add_interface"
SELECT_INTERFACE_CONTACTS_COMMAND_ID = "kev0_cable_bundler_select_interface_contacts"
ADD_JUNCTION_RELATIONSHIP_COMMAND_ID = "kev0_cable_bundler_add_junction_relationship"
ADD_END_COMMAND_ID = "kev0_cable_bundler_add_end"
ATTACH_CABLE_END_COMMAND_ID = "kev0_cable_bundler_attach_cable_end"
APPEND_GATES_COMMAND_ID = "kev0_cable_bundler_append_pathway_gates"
ADD_REFINE_COMMAND_ID = "kev0_cable_bundler_add_pathway_refine"
SEGMENT_PATHWAY_COMMAND_ID = "kev0_cable_bundler_segment_pathway"
EDIT_REFINE_COMMAND_ID = "kev0_cable_bundler_edit_pathway_refine"

COMMAND_NAME = "Harness Builder"
COMMAND_DESCRIPTION = "Create and edit cable, ribbon, and harness assemblies."
CREATE_COMMAND_NAME = "Create Harness"
ADD_PATHWAY_COMMAND_NAME = "Add Pathway"
ADD_JUNCTION_COMMAND_NAME = "Add Junction"
ADD_INTERFACE_COMMAND_NAME = "Add Interface"
SELECT_INTERFACE_CONTACTS_COMMAND_NAME = "Select Interface Contacts"
ADD_JUNCTION_RELATIONSHIP_COMMAND_NAME = "Add Junction Relationship"
ADD_END_COMMAND_NAME = "Add End"
ATTACH_CABLE_END_COMMAND_NAME = "Connect Cable End"
APPEND_GATES_COMMAND_NAME = "Add Gates"
ADD_REFINE_COMMAND_NAME = "Add Refine Point"
SEGMENT_PATHWAY_COMMAND_NAME = "Segment Pathway"
EDIT_REFINE_COMMAND_NAME = "Edit Refine Point"

PALETTE_ID = "kev0_cable_bundler_harness_builder_palette"
PALETTE_HTML_URL = "palette.html"
PALETTE_INITIAL_WIDTH = 840
PALETTE_INITIAL_HEIGHT = 760
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_IDS = ("SolidScriptsAddinsPanel", "InsertAssemblePanel")

HARNESS_NAME_INPUT_ID = "harness_name"
PATHWAY_NAME_INPUT_ID = "pathway_name"
PATHWAY_GATES_INPUT_ID = "pathway_gates"
JUNCTION_NAME_INPUT_ID = "junction_name"
JUNCTION_PROFILE_INPUT_ID = "junction_profile"
INTERFACE_NAME_INPUT_ID = "interface_name"
INTERFACE_TARGETS_INPUT_ID = "interface_targets"
INTERFACE_CONTACTS_INPUT_ID = "interface_contacts"
JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID = "junction_relationship_geometry"
JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID = "junction_relationship_choice"
STANDALONE_END_GUIDES_INPUT_ID = "standalone_end_guides"
STANDALONE_END_BOUNDARY_INPUT_ID = "standalone_end_boundary"
STANDALONE_END_CHOICE_INPUT_ID = "standalone_end_choice"
CABLE_END_ATTACHMENT_TARGET_INPUT_ID = "cable_end_attachment_target"
CABLE_END_ATTACHMENT_NAME_INPUT_ID = "cable_end_attachment_name"
REFINE_SPINE_INPUT_ID = "refine_spine"
REFINE_RADIUS_INPUT_ID = "refine_radius"
REFINE_TRANSFORM_INPUT_ID = "refine_transform"
SEGMENT_CONTROL_INPUT_ID = "segment_control"
SEGMENT_PATHWAY_NAME_INPUT_ID = "segment_pathway_name"
ROUTING_MODE_INPUT_ID = "routing_mode"
DEFAULT_HARNESS_NAME = "Harness_001"

ADDIN_ROOT = Path(__file__).resolve().parents[3]
COMMAND_RESOURCE_FOLDER = str(ADDIN_ROOT / "resources" / "open_harness_builder")
ADD_PATHWAY_RESOURCE_FOLDER = str(ADDIN_ROOT / "resources" / "add_routing_gate")
ADD_END_RESOURCE_FOLDER = str(ADDIN_ROOT / "resources" / "add_harness_cable")
PALETTE_HTML_FILE = ADDIN_ROOT / "palette.html"
PALETTE_RESOURCE_FILES = (
    PALETTE_HTML_FILE,
    ADDIN_ROOT / "palette" / "styles" / "base.css",
    ADDIN_ROOT / "palette" / "styles" / "materials.css",
    ADDIN_ROOT / "palette" / "styles" / "editor.css",
    ADDIN_ROOT / "palette" / "styles" / "diagram-workspace.css",
    ADDIN_ROOT / "palette" / "styles" / "create-cables.css",
    ADDIN_ROOT / "palette" / "styles" / "interface-contacts.css",
    ADDIN_ROOT / "palette" / "styles" / "diagram-components.css",
    ADDIN_ROOT / "palette" / "styles" / "utilities.css",
    ADDIN_ROOT / "palette" / "foundation" / "theme.js",
    ADDIN_ROOT / "palette" / "foundation" / "state.js",
    ADDIN_ROOT / "palette" / "foundation" / "components.js",
    ADDIN_ROOT / "palette" / "foundation" / "pathways.js",
    ADDIN_ROOT / "palette" / "pathway-editors.js",
    ADDIN_ROOT / "palette" / "materials.js",
    ADDIN_ROOT / "palette" / "connection-materials.js",
    ADDIN_ROOT / "palette" / "material-options.js",
    ADDIN_ROOT / "palette" / "diagrams" / "workspace.js",
    ADDIN_ROOT / "palette" / "diagrams" / "trace-contrast.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-model.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-layout" / "ports.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-layout" / "routing.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-layout" / "rendering.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-layout" / "node-metrics.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-layout" / "layouts.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-layout" / "controller.js",
    ADDIN_ROOT / "palette" / "diagrams" / "cable-group-details-ordering.js",
    ADDIN_ROOT / "palette" / "cable-group-details-topology.js",
    ADDIN_ROOT / "palette" / "cable-group-details.js",
    ADDIN_ROOT / "palette" / "cable-group-details-dialog.js",
    ADDIN_ROOT / "palette" / "diagrams" / "create-cables" / "model.js",
    ADDIN_ROOT / "palette" / "diagrams" / "create-cables" / "view.js",
    ADDIN_ROOT / "palette" / "diagrams" / "create-cables" / "controller.js",
    ADDIN_ROOT / "palette" / "connection-association-selection.js",
    ADDIN_ROOT / "palette" / "connection-associations.js",
    ADDIN_ROOT / "palette" / "diagrams" / "interface-contact-labels.js",
    ADDIN_ROOT / "palette" / "diagrams" / "interface-contact-auto-pin.js",
    ADDIN_ROOT / "palette" / "diagrams" / "interface-contact-cache.js",
    ADDIN_ROOT / "palette" / "diagrams" / "interface-contact-projection.js",
    ADDIN_ROOT / "palette" / "diagrams" / "interface-contacts.js",
    ADDIN_ROOT / "palette" / "diagrams" / "interface-contact-naming.js",
    ADDIN_ROOT / "palette" / "diagrams" / "interface-contact-selection.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-junction-popup.js",
    ADDIN_ROOT / "palette" / "diagrams" / "master-components.js",
    ADDIN_ROOT / "palette" / "master-graphic.js",
    ADDIN_ROOT / "palette" / "editor.js",
    ADDIN_ROOT / "palette" / "qa" / "diagram-observation.js",
    ADDIN_ROOT / "palette" / "host.js",
)

ROUTING_MODE_LABELS = {
    RoutingMode.ROUTING_GATES: "Routing Gates",
    RoutingMode.PROFILE_GATES: "Profile Gates",
}

PALETTE_EDIT_NAMES = {
    "add_cable_end_connection": "Add Cable End Connection",
    "disconnect_cable_end_relationship": "Disconnect Cable End Relationship",
    "delete_damaged_harness": "Delete Damaged Harness",
    "move_pathway_gate": "Reorder Pathway Gates",
    "update_junction_relationships": "Edit Junction Relationships",
    "remove_junction_relationship": "Remove Junction Relationship",
    "remove_junction": "Delete Junction",
    "remove_interface": "Delete Interface",
    "remove_interface_contacts": "Delete Interface Contacts",
    "remove_pathway": "Delete Pathway",
    "remove_pathway_gate": "Remove Pathway Gate",
    "remove_end_control": "Remove Cable End Control",
    "remove_end_guide": "Remove Cable End Guide",
    "remove_standalone_end": "Delete Standalone End",
    "remove_cable_end_attachment": "Delete Cable End Connection",
    "save_cable_editor": "Save Route Editor",
    "save_attachment_associations": "Save Connection Associations",
    "rename_cable_group": "Rename Connected Cable",
    "rename_harness": "Rename Harness",
    "rename_junction": "Rename Junction",
    "rename_interface": "Rename Interface",
    "pos_import_interface_contacts": "Import Interface Contact Positions",
    "geo_import_interface_contacts": "Import Interface Contact Geometry Names",
    "load_brd_interface_contacts": "Load Interface Board",
    "set_interface_contact_name": "Name Interface Contact",
    "set_interface_contact_details": "Edit Interface Contact",
    "auto_pin_interface_contacts": "Auto Pin Interface Contacts",
    "clear_interface_contact_pins": "Clear Interface Contact Pins",
    "rename_standalone_end": "Rename Standalone End",
    "rename_cable_end_attachment": "Rename Cable End Connection",
    "switch_standalone_end": "Switch Standalone End",
    "rename_pathway": "Rename Pathway",
    "set_cable_end_attachment_properties": "Change Cable End Connection Properties",
    "set_cable_end_attachment_shielding": "Change Cable End Connection Shielding",
    "set_cable_end_attachment_visual_overrides": "Change Cable End Connection Materials",
    "set_cable_end_properties": "Change Cable End Properties",
    "set_cable_group_properties": "Change Connected Cable Properties",
    "set_cable_group_material_overrides": "Change Connected Cable Materials",
    "set_harness_material_defaults": "Change Harness Cable Materials",
    "set_harness_properties": "Change Harness Properties",
    "set_junction_properties": "Change Junction Properties",
    "set_pathway_end_properties": "Change Pathway End Properties",
    "set_pathway_properties": "Change Pathway Properties",
    "set_interpolation": "Change Interpolation Options",
    "preview_routes": "Preview Cable Routes",
    "generate_solids": "Generate Cable Solids",
    "finalize_solids": "Finalize Cable Geometry",
    "clear_solids": "Clear Cable Solids",
}
