"""
Freeze solver panels, numerical plots and physical witnesses from recorded geometry.
"""

from __future__ import annotations

import hashlib
import math
import textwrap
from dataclasses import dataclass
from typing import Any

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit

from ..constraint_geometry import Overlay, Stroke, circle
from ..contracts import Targets
from ..traces import TracePath
from .archive import canonical, snapshot_payload
from .bends import inspect
from .geometry import PathSnapshot


@dataclass(frozen=True)
class PanelSource:
    """
    Identify the exact frozen metadata shared by native and Custom Graphics panels.
    """

    identifier: str
    fingerprint: str


def _notes(lines: list[str]) -> tuple[str, ...]:
    """
    Keep full readable captions in bounded-width lines beside small diagnostic routes.
    """
    return tuple(part for line in lines for part in textwrap.wrap(line, 76))


def build(state: dict[str, Any], snapshot: PathSnapshot) -> tuple[PanelSource, Overlay, Overlay]:
    """
    Describe current solver values and sampled bending without guessing probe coordinates.
    """
    method = next(item for item in state["solvers"] if item["id"] == state["solver"])
    points = [point for guide in snapshot.guides for point in guide.controls]
    diameter = snapshot.diameter_mm
    anchor = Vector3(
        max(point.x for point in points) + 4 * diameter, max(point.y for point in points), 0
    )
    proposal = state["proposal_info"]
    metrics = method["metrics"]
    coordinates = (
        proposal.get("coordinates") if proposal is not None else metrics.get("coordinates")
    )
    score = proposal.get("score") if proposal is not None else metrics.get("score")
    notes = [
        method["label"],
        "Case: " + state["case"],
        f"{method['status']} | "
        + (
            f"proposal {state['proposal'] + 1}/{method['history_count']} | {proposal['stage']}"
            if proposal is not None
            else f"recorded result | {method['history_count']} stored paths"
        ),
        "Disabled in this recorded search: " + (", ".join(method["disabled_rules"]) or "none"),
        "Independent measurements remain active; no physical acceptance.",
    ]
    if method.get("detail"):
        notes.append(method["detail"])
    if score is not None:
        notes.append(f"Recorded objective score: {score:.6g}")
    if method["settings"]:
        notes.append(
            "Settings: " + ", ".join(f"{key}={value}" for key, value in method["settings"].items())
        )
    if coordinates is not None:
        for index in range(0, len(coordinates), 4):
            notes.append(
                "Coordinates: "
                + ", ".join(
                    f"c{i}={coordinates[i]:.5g}"
                    for i in range(index, min(index + 4, len(coordinates)))
                )
            )
    elif proposal is not None:
        notes.append(
            "Coordinates were not recorded for this transport; final coefficients are not substituted."
        )
    notes.extend(
        f"{rule['name']} [{rule['status']}]: {rule['value']:.6g}"
        + (f" / {rule['limit']:.6g}" if rule["limit"] is not None else "")
        for rule in state["rules"]
        if rule["value"] is not None
    )
    comparison = state["comparison"]
    if comparison is not None:
        notes.append(
            "Comparison role: " + comparison["role"] + "; grey guides = recorded matched baseline"
        )
    data = {
        "geometry": snapshot_payload(snapshot)["sha256"],
        "method": method,
        "proposal": proposal,
        "rules": state["rules"],
    }
    source = PanelSource(snapshot.identifier, hashlib.sha256(canonical(data).encode()).hexdigest())
    summary = Overlay(
        "solver_limits",
        "Selected solver / frozen numerical evidence",
        (),
        (),
        _notes(notes),
        anchor,
    )
    bends = inspect(snapshot, state["section"])
    plot_origin = anchor.translated(Vector3(1, 0, 0), 28 * diameter)
    width, height = 24 * diameter, 10 * diameter
    maximum = max(
        1.2, *(value for sample in bends["samples"] for value in sample["utilization"].values())
    )
    strokes = [
        Stroke(
            "limit",
            (
                plot_origin.translated(Vector3(0, 1, 0), height / maximum),
                plot_origin.translated(Vector3(1, 0, 0), width).translated(
                    Vector3(0, 1, 0), height / maximum
                ),
            ),
        )
    ]
    for key, role in (("centre", "actual"), ("edge_a", "witness"), ("edge_b", "edge_b")):
        if key != "centre" and not bends["has_edges"]:
            continue
        strokes.append(
            Stroke(
                role,
                tuple(
                    plot_origin.translated(Vector3(1, 0, 0), point["u"] * width).translated(
                        Vector3(0, 1, 0), point["utilization"][key] / maximum * height
                    )
                    for point in bends["samples"]
                ),
            )
        )
    chart = Overlay(
        "curvature_plot",
        "Current recorded path: curvature x 3D",
        (),
        tuple(strokes),
        (
            "Blue centre / orange A / purple B / red 3D reference",
            "Sampled frozen cubics; allowable wide-ribbon radius ratio/flex unresolved.",
        ),
        plot_origin.translated(Vector3(0, -1, 0), 2 * diameter),
    )
    return source, summary, chart


def bend_witness(guide: TracePath, minimum: float, title: str) -> Overlay:
    """
    Place actual and declared minimum-radius circles at the worst sampled curvature.
    """
    best: tuple[float, Vector3, Vector3, Vector3] | None = None
    for curve in guide.curves:
        for fraction in (0.0, 1 / 3, 2 / 3, 1.0):
            velocity = curve.derivative(fraction)
            speed = magnitude(velocity)
            if speed < 1e-12:
                continue
            tangent = unit(velocity)
            acceleration = curve.second_derivative(fraction)
            normal = acceleration.translated(tangent, -dot(acceleration, tangent))
            curvature = magnitude(normal) / speed**2
            if curvature > 1e-12 and (best is None or curvature > best[0]):
                best = (curvature, curve.point(fraction), tangent, unit(normal))
    if best is None:
        return Overlay(
            "bend_witness",
            title,
            (),
            (),
            ("Straight or undefined curvature; no osculating-circle witness.",),
            guide.controls[0],
        )
    curvature, point, tangent, normal = best
    actual_radius = 1 / curvature
    strokes = [circle(point, tangent, normal, minimum)]
    notes = [
        f"Actual R={actual_radius:.5g}mm; declared search reference R={minimum:.5g}mm",
        "Circle glyphs are sampled guides, not a physical certificate.",
    ]
    if actual_radius <= 8 * minimum:
        actual = circle(point, tangent, normal, actual_radius)
        strokes.append(Stroke("actual", actual.points))
    else:
        notes.append("Actual circle exceeds eight reference radii; omitted to preserve path scale.")
    return Overlay(
        "bend_witness",
        title,
        (("actual_radius_mm", actual_radius), ("reference_radius_mm", minimum)),
        tuple(strokes),
        tuple(notes),
        point,
    )


def witnesses(snapshot: PathSnapshot, targets: Targets) -> tuple[Overlay, ...]:
    """
    Share path-attached bend circles and the fixed-end gap between both renderers.

    Each bend pair touches its guide's worst sampled point in the actual bend
    plane. Red marks the historical minimum-radius search reference, blue the
    measured radius. These references do not implement the missing physical policy.
    """
    half = targets.lines * snapshot.diameter_mm / 2 + snapshot.diameter_mm * 0.1
    reach = math.hypot(half, snapshot.diameter_mm / 2)
    overlays = [
        bend_witness(
            guide,
            reach / 0.78 if guide.number == 0 else 3.1 * snapshot.diameter_mm,
            "Macaroni / centre reach reference"
            if guide.number == 0
            else f"Macaroni / edge {guide.number} radius reference",
        )
        for guide in snapshot.guides
    ]
    center = next(guide for guide in snapshot.guides if guide.number == 0)
    end = center.controls[-1]
    gap = magnitude(difference(end, targets.end))
    overlays.append(
        Overlay(
            "target_gap",
            "Fixed end position",
            (("gap_mm", gap),),
            (Stroke("target", (end, targets.end)),) if gap > 1e-12 else (),
            ("Green joins the recorded end to the unchanged target.",),
            end,
        )
    )
    return tuple(overlays)
