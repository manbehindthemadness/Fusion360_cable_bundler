"""
Keep normally hidden constraint geometry under individually revealable components.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from time import perf_counter
from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3

from .api import Evidence
from .constraint_geometry import Overlay, Restriction, build
from .graphics import draw_lines, draw_text
from .provenance import mark_loaded
from .solver_details import retain_solver_details


def draw_overlay(component: Any, overlay: Overlay) -> Any:
    """
    Draw one frozen panel with readable labels and witnesses visible over the sheet.
    """
    colors = {
        "limit": (220, 65, 50),
        "actual": (40, 115, 230),
        "target": (20, 160, 80),
        "witness": (210, 90, 20),
    }
    group = component.customGraphicsGroups.add()
    group.name = "Frozen constraint witnesses - " + overlay.key
    for stroke in overlay.strokes:
        if len(stroke.points) >= 2:
            draw_lines(group, stroke.points, colors[stroke.role], overlay.title + " " + stroke.role)
            color = adsk.core.Color.create(*colors[stroke.role], 255)
            effect = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(color, 0.85)
            if effect is None:
                raise RuntimeError("Constraint show-through color is unavailable.")
            group.item(group.count - 1).color = effect
    draw_text(
        group, overlay.title, overlay.anchor.translated(Vector3(0, -1, 0), 2), (25, 25, 25), 2
    )
    for i, note in enumerate(overlay.notes):
        draw_text(
            group, note, overlay.anchor.translated(Vector3(0, -1, 0), 5 + i * 3), (40, 40, 40), 1.7
        )
    for i in range(group.count):
        group.item(i).depthPriority = 50
    return group


def retain_constraints(
    component: Any,
    evidence: Evidence,
    checkpoint: Callable[[], None] = lambda: None,
    *,
    restrictions: tuple[Restriction, ...] = (),
) -> dict[str, Any]:
    """
    Freeze and draw six overlays once without modifying a candidate route.

    Physical helpers use child component eyes; solver details use a sketch directly
    in the experiment and start visible. Both work independently from the sheet
    and native originals. Reusing solver details preserves manual visibility.
    Returned blueprints are the agent's copy of displayed facts.
    This is diagnostic graphics, not native solids or constraint ablation.
    """
    started = perf_counter()
    overlays = build(evidence, restrictions)
    digest = hashlib.sha256(
        json.dumps(
            {"evidence": evidence.fingerprint, "overlays": [asdict(o) for o in overlays]},
            sort_keys=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    handles = {}
    for overlay in overlays:
        checkpoint()
        if overlay.key == "solver_limits":
            handles[overlay.key] = retain_solver_details(component, evidence, overlay, checkpoint)
            continue
        occurrence = component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occurrence.component.name = "Constraint - " + overlay.title
        occurrence.isLightBulbOn = False
        draw_overlay(occurrence.component, overlay)
        handles[overlay.key] = occurrence
    return {
        "constraint_views": handles,
        "constraint_evidence": overlays,
        "constraint_fingerprint": digest,
        "constraint_seconds": perf_counter() - started,
    }


mark_loaded(__file__)
