"""
Keep unchanged joined end-cap profiles ready for manual sweep experiments.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5

from .contracts import TargetPose, Targets
from .provenance import mark_loaded

_GROUP = "RibbonAnalysisEndProfiles"
_BUILDER = (
    Path(__file__).resolve().parents[2] / "cable_bundler/fusion/cable_solid_parts/ribbon_builder.py"
)
_ROLES = ("start", "end")


def checkpoint_interrupted(component: Any) -> bool:
    """
    Recognize a retained prefix stopped before the next native profile operation.

    A checkpoint marker is distinct from failed native authoring. Validate every
    retained cap before allowing a new explicit test run to archive the prefix.
    Missing, altered or completed records are not recoverable interruptions.
    """
    source = component.attributes.itemByName(_GROUP, "source")
    marker = component.attributes.itemByName(_GROUP, "checkpoint_interrupted")
    complete = component.attributes.itemByName(_GROUP, "complete")
    if source is None or marker is None or complete is not None:
        return False
    expected = next(
        (
            _ROLES[:index]
            for index, role in enumerate(_ROLES)
            if marker.value == source.value + ":" + role
        ),
        None,
    )
    if expected is None:
        return False
    roles = []
    for sketch in component.sketches:
        role = sketch.attributes.itemByName(_GROUP, "role")
        if role is None or sketch.profiles.count != 1:
            return False
        roles.append(role.value)
    return tuple(roles) == expected


def _author(component: Any, targets: Targets, role: str) -> Any:
    """
    Delegate the exact target-plane contour to the existing profile builder.

    An explicit guide plane bypasses its route-plane branch, so no path or native
    sweep is needed. The flat target cap remains authoritative for failed routes.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    from cable_bundler.domain import CableGroupDefinition, CableGroupType
    from cable_bundler.fusion.cable_solid_parts import ribbon_builder
    from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
    from cable_bundler.routing import RibbonFrame
    from cable_bundler.routing.geometry import cross

    origin = getattr(targets, role)
    tangent = getattr(targets, role + "_tangent")
    width = getattr(targets, role + "_width")
    frame = RibbonFrame(origin, tangent, width, cross(tangent, width))
    group = CableGroupDefinition(
        uuid5(NAMESPACE_URL, targets.name),
        (),
        diameter_mm=targets.diameter_mm,
        group_type=CableGroupType.RIBBON,
        ribbon_lines=targets.lines,
    )
    # The supplied target guide plane makes route_curve unused in this builder.
    # noinspection PyProtectedMember
    sketch, plane = ribbon_builder._add_section(
        component,
        None,
        frame,
        group,
        adsk.core.Matrix3D.create(),
        guide_plane=RibbonGuidePlane(origin, tangent),
    )
    plane.isLightBulbOn = False
    return sketch


def retain_end_profiles(
    component: Any,
    source: TargetPose,
    checkpoint: Callable[[], None] = lambda: None,
) -> dict[str, Any]:
    """
    Retain one closed joined profile at each fixed target, initially hidden.

    Reuse a complete matching pair without changing manual visibility. Changed
    targets need another owned layout component. Preserve incomplete work and
    refuse automatic retries after native failure. Record checkpoint interruptions
    separately so a later explicit test run can archive unattempted work without
    treating native authoring errors as recoverable. No route or solid is created.
    """
    targets = Targets.capture(source)
    payload = json.dumps(asdict(targets), sort_keys=True, separators=(",", ":"))
    builder_digest = hashlib.sha256(_BUILDER.read_bytes()).hexdigest()
    fingerprint = hashlib.sha256((payload + builder_digest).encode()).hexdigest()
    previous = component.attributes.itemByName(_GROUP, "source")
    if previous is not None:
        if previous.value != fingerprint:
            raise RuntimeError("Changed end profiles require a separate layout component.")
        complete = component.attributes.itemByName(_GROUP, "complete")
        if complete is None or complete.value != fingerprint:
            raise RuntimeError("Incomplete end profiles require review before retrying.")
        retained = {}
        for role in _ROLES:
            matches = [
                sketch
                for sketch in component.sketches
                if (stamp := sketch.attributes.itemByName(_GROUP, "role")) is not None
                and stamp.value == role
            ]
            if len(matches) != 1 or matches[0].profiles.count != 1:
                raise RuntimeError("Retained end profiles are missing, duplicated or invalid.")
            retained[role] = matches[0]
        return retained
    component.attributes.add(_GROUP, "source", fingerprint)
    retained = {}
    for role in _ROLES:
        try:
            checkpoint()
        except (RuntimeError, OSError):
            component.attributes.add(_GROUP, "checkpoint_interrupted", fingerprint + ":" + role)
            raise
        sketch = _author(component, targets, role)
        sketch.name = f"Sweep profile - {role.title()} cap"
        sketch.isLightBulbOn = False
        sketch.attributes.add(_GROUP, "role", role)
        if sketch.profiles.count != 1:
            raise RuntimeError("Sweep input must have one closed joined profile per cap.")
        retained[role] = sketch
    component.attributes.add(_GROUP, "complete", fingerprint)
    return retained


mark_loaded(__file__)
