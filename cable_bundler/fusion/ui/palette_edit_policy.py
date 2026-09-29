"""
Describe viewport work required after palette edits.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import PALETTE_EDIT_NAMES as _PALETTE_EDIT_NAMES


@dataclass(frozen=True)
class PaletteEditPolicy:
    """
    Describe post-transaction viewport work for one palette edit.
    """

    reconcile_refines: bool = False
    apply_generated_materials: bool = False
    ensure_preview_visible: bool = False
    refresh_connection_geometry: bool = False
    refresh_preview: bool = True


_DEFAULT_EDIT_POLICY = PaletteEditPolicy()
_PALETTE_EDIT_POLICIES = {action: _DEFAULT_EDIT_POLICY for action in _PALETTE_EDIT_NAMES}
_NAME_ONLY_EDIT_POLICY = PaletteEditPolicy(refresh_preview=False)
for _action in (
    "rename_cable_end_attachment",
    "rename_cable_group",
    "rename_harness",
    "rename_interface",
    "rename_junction",
    "rename_pathway",
    "rename_standalone_end",
):
    _PALETTE_EDIT_POLICIES[_action] = _NAME_ONLY_EDIT_POLICY
_PALETTE_EDIT_POLICIES["remove_pathway_gate"] = PaletteEditPolicy(reconcile_refines=True)
_PALETTE_EDIT_POLICIES["remove_end_control"] = PaletteEditPolicy(reconcile_refines=True)
_CONNECTION_GEOMETRY_EDIT_POLICY = PaletteEditPolicy(refresh_connection_geometry=True)
_PALETTE_EDIT_POLICIES["add_cable_end_connection"] = _CONNECTION_GEOMETRY_EDIT_POLICY
_PALETTE_EDIT_POLICIES["disconnect_cable_end_relationship"] = PaletteEditPolicy(
    reconcile_refines=True,
    refresh_connection_geometry=True,
)
_PALETTE_EDIT_POLICIES["set_cable_end_attachment_properties"] = _CONNECTION_GEOMETRY_EDIT_POLICY
_PALETTE_EDIT_POLICIES["remove_cable_end_attachment"] = PaletteEditPolicy(
    reconcile_refines=True,
    refresh_connection_geometry=True,
)
_PALETTE_EDIT_POLICIES["remove_pathway"] = PaletteEditPolicy(reconcile_refines=True)
_PALETTE_EDIT_POLICIES["remove_junction"] = PaletteEditPolicy(reconcile_refines=True)
_MATERIAL_EDIT_POLICY = PaletteEditPolicy(
    apply_generated_materials=True,
    ensure_preview_visible=True,
)
_PALETTE_EDIT_POLICIES["set_harness_material_defaults"] = _MATERIAL_EDIT_POLICY
_GROUP_APPEARANCE_EDIT_POLICY = PaletteEditPolicy(ensure_preview_visible=True)
_PALETTE_EDIT_POLICIES["set_cable_group_properties"] = _GROUP_APPEARANCE_EDIT_POLICY
_PALETTE_EDIT_POLICIES["set_cable_group_material_overrides"] = _MATERIAL_EDIT_POLICY
_PALETTE_EDIT_POLICIES["set_cable_end_attachment_visual_overrides"] = _MATERIAL_EDIT_POLICY
