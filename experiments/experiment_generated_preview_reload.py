"""
Reload the active add-in and verify generated output suppresses route previews.

Run in Fusion with the add-in and local MCP server active, a default Select command,
and an open test design containing generated Cable Bundler output. The test design
is left open and is not saved. Reloading closes the Harness Builder palette; it can
be reopened from its toolbar command.
"""

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import Fusion360_cable_bundler as entrypoint


def _visible_preview_count(design: adsk.fusion.Design) -> int:
    """
    Count root-level route-preview graphics currently drawn in the viewport.
    """
    groups = design.rootComponent.customGraphicsGroups
    return sum(
        1
        for index in range(groups.count)
        if (group := groups.item(index)) is not None
        and group.id.startswith("kev0.cable_bundler.route_preview")
        and group.isVisible
    )


def run(_context: str) -> None:
    """
    Reload current source and exercise both preview-refresh visibility policies.
    """
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("An active Fusion design is required.")
    document = application.activeDocument
    document_name = document.name
    before_count = _visible_preview_count(design)

    entrypoint.stop(None)
    entrypoint.run(None)

    from cable_bundler.application import load_harnesses
    from cable_bundler.fusion.cable_solids import generated_cable_group_occurrences
    from cable_bundler.fusion.ui.support import _create_harness_gateway
    from cable_bundler.fusion.ui.viewport import _refresh_active_preview

    results = load_harnesses(_create_harness_gateway(application))
    generated = tuple(
        result
        for result in results
        if result.definition is not None
        and result.component_handle is not None
        and generated_cable_group_occurrences(result.component_handle)
    )
    if not generated:
        raise RuntimeError("The active design has no generated cable-group output.")
    after_reload_count = _visible_preview_count(design)
    for result in generated:
        _refresh_active_preview(application, result.definition.harness_id, ensure_visible=True)
        _refresh_active_preview(application, result.definition.harness_id, ensure_visible=False)
    after_refresh_count = _visible_preview_count(design)
    if after_reload_count or after_refresh_count:
        raise RuntimeError("A route-preview group remained visible over generated output.")
    if application.activeDocument != document:
        raise RuntimeError("Reload switched away from the source document.")
    print(
        "GENERATED_PREVIEW_RELOAD="
        f"{{'document': {document_name!r}, 'generated_harnesses': {len(generated)}, "
        f"'visible_before': {before_count}, 'visible_after_reload': {after_reload_count}, "
        f"'visible_after_refresh': {after_refresh_count}}}"
    )
