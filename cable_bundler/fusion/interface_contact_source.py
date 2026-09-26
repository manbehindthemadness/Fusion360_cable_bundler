"""
Identify the live geometry behind a cached Interface contact projection.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from ..domain import AttachmentTargetKind, InterfaceContact
from .attachment_targets import attachment_target_kind, attachment_target_name
from .interface_contact_cache import resolve_contact_entities


def _finite_vector(value: object) -> tuple[float, float, float] | None:
    """
    Read one finite point or direction without retaining a Fusion proxy.
    """
    try:
        coordinates = tuple(float(getattr(value, axis)) for axis in ("x", "y", "z"))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return coordinates if all(math.isfinite(number) for number in coordinates) else None


def _occurrence_transform(entity: object, owner: object) -> list[float] | None:
    """
    Include assembly placement even when the native geometry revision is stable.
    """
    try:
        occurrence = getattr(entity, "assemblyContext", None) or getattr(
            owner, "assemblyContext", None
        )
        if occurrence is None:
            return []
        transform = occurrence.transform2
        values = list(transform.asArray())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    if len(values) != 16 or any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in values
    ):
        return None
    return [float(value) for value in values]


def contact_source_signature(design: Any, contact: InterfaceContact) -> str | None:
    """
    Fingerprint source revision and placement, failing closed if either is unknown.

    Body and sketch revision IDs are host-maintained change markers. Point-like
    targets also include their live position or transform because they have no
    reliable owner revision of their own.
    """
    try:
        entity = next(
            (
                candidate
                for candidate in resolve_contact_entities(design, contact.entity_token)
                if attachment_target_kind(candidate) is contact.kind
            ),
            None,
        )
        if entity is None:
            return None
        kind = contact.kind
        if kind in (AttachmentTargetKind.FACE, AttachmentTargetKind.CIRCULAR_EDGE):
            owner = entity.body
            revision = owner.revisionId
        elif kind in (AttachmentTargetKind.PROFILE, AttachmentTargetKind.SKETCH_POINT):
            owner = entity.parentSketch
            revision = owner.revisionId
        else:
            owner = entity
            revision = None
        placement = _occurrence_transform(entity, owner)
        if placement is None:
            return None
        if kind in (
            AttachmentTargetKind.FACE,
            AttachmentTargetKind.CIRCULAR_EDGE,
            AttachmentTargetKind.PROFILE,
            AttachmentTargetKind.SKETCH_POINT,
        ):
            if not isinstance(revision, str) or not revision:
                return None
        else:
            coordinates = next(
                (
                    value
                    for point in (
                        getattr(entity, "worldGeometry", None),
                        getattr(entity, "geometry", None),
                        getattr(getattr(entity, "transform", None), "translation", None),
                    )
                    if (value := _finite_vector(point)) is not None
                ),
                None,
            )
            if coordinates is None:
                return None
            revision = coordinates
        orientation = None
        if kind is AttachmentTargetKind.JOINT_ORIGIN:
            orientation = (
                _finite_vector(entity.primaryAxisVector),
                _finite_vector(entity.secondaryAxisVector),
            )
            if any(axis is None for axis in orientation):
                return None
        payload = (
            contact.kind.value,
            contact.entity_token,
            revision,
            placement,
            orientation,
            attachment_target_name(entity, kind),
        )
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
