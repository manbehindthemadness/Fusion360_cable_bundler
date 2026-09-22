"""Resolve the supported Fusion targets used by cable-end attachments."""

from __future__ import annotations

from typing import Optional, Union

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..domain import AttachmentTargetKind, CableEndAttachment, CableEndTarget


def _cast(entity_type: object, entity: object) -> Optional[object]:
    """
    Cast an entity through one Fusion type without assuming a live host in tests.
    """
    cast = getattr(entity_type, "cast", None)
    return cast(entity) if callable(cast) else None


def attachment_target_kind(entity: object) -> Optional[AttachmentTargetKind]:
    """
    Classify one Fusion selection into the supported attachment target set.
    """
    candidates = (
        (adsk.fusion.Profile, AttachmentTargetKind.PROFILE),
        (adsk.fusion.BRepFace, AttachmentTargetKind.FACE),
        (adsk.fusion.JointOrigin, AttachmentTargetKind.JOINT_ORIGIN),
        (adsk.fusion.BRepEdge, AttachmentTargetKind.CIRCULAR_EDGE),
        (adsk.fusion.ConstructionPoint, AttachmentTargetKind.CONSTRUCTION_POINT),
        (adsk.fusion.SketchPoint, AttachmentTargetKind.SKETCH_POINT),
    )
    return next((kind for entity_type, kind in candidates if _cast(entity_type, entity)), None)


def attachment_target_name(entity: object, kind: AttachmentTargetKind) -> str:
    """
    Return the closest user-controlled Fusion name for one attachment target.
    """
    if kind in {AttachmentTargetKind.JOINT_ORIGIN, AttachmentTargetKind.CONSTRUCTION_POINT}:
        name = getattr(entity, "name", "")
    elif kind in {AttachmentTargetKind.PROFILE, AttachmentTargetKind.SKETCH_POINT}:
        name = getattr(getattr(entity, "parentSketch", None), "name", "")
    else:
        body = getattr(entity, "body", None)
        name = getattr(body, "name", "")
    if isinstance(name, str) and name.strip():
        return name.strip()
    labels = {
        AttachmentTargetKind.PROFILE: "Socket profile",
        AttachmentTargetKind.FACE: "Body face",
        AttachmentTargetKind.JOINT_ORIGIN: "Joint origin",
        AttachmentTargetKind.CIRCULAR_EDGE: "Circular edge",
        AttachmentTargetKind.CONSTRUCTION_POINT: "Construction point",
        AttachmentTargetKind.SKETCH_POINT: "Sketch point",
    }
    return labels[kind]


def resolve_attachment_target(
    design: adsk.fusion.Design,
    attachment: Union[CableEndAttachment, CableEndTarget],
) -> Optional[object]:
    """
    Resolve the saved token only when it still identifies the expected entity kind.
    """
    if not attachment.has_target:
        return None
    entities = design.findEntityByToken(attachment.entity_token) or ()
    return next(
        (entity for entity in entities if attachment_target_kind(entity) is attachment.target_kind),
        None,
    )


def attachment_display_name(
    design: Optional[adsk.fusion.Design],
    attachment: Union[CableEndAttachment, CableEndTarget],
) -> str:
    """
    Resolve a live inherited name while retaining the saved fallback when disconnected.
    """
    if attachment.name.strip():
        return attachment.name.strip()
    entity = resolve_attachment_target(design, attachment) if design is not None else None
    return (
        attachment_target_name(entity, attachment.target_kind)
        if entity is not None and attachment.target_kind is not None
        else attachment.display_name
    )
