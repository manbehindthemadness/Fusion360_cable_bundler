"""
Resolve persistent Interface targets against the active Fusion design.
"""

from __future__ import annotations

from typing import Callable, Optional

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..domain import InterfaceTarget, InterfaceTargetKind


def resolve_interface_target(
    design: adsk.fusion.Design,
    target: InterfaceTarget,
    *,
    find_entities: Optional[Callable[[str], tuple[object, ...]]] = None,
) -> Optional[object]:
    """
    Resolve one saved token only when its entity still has the expected kind.
    """
    entity_type = {
        InterfaceTargetKind.BODY: adsk.fusion.BRepBody,
        InterfaceTargetKind.SKETCH: adsk.fusion.Sketch,
        InterfaceTargetKind.OCCURRENCE: adsk.fusion.Occurrence,
    }[target.kind]
    return next(
        (
            entity
            for entity in (
                find_entities(target.entity_token)
                if find_entities is not None
                else design.findEntityByToken(target.entity_token) or ()
            )
            if entity_type.cast(entity) is not None
        ),
        None,
    )
