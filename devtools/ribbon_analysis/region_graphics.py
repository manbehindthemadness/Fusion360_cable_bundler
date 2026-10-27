"""
Render a diagnostic material sheet, interval witnesses and measurement graphs.

The sheet is deliberately allowed to overlap where a map folds; it is neither
a conductor sweep nor a physical solid. Reference splines remain unchanged.
"""

from __future__ import annotations

from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3

from .api import Candidate, Evidence, freeze
from .constraint_geometry import Restriction
from .constraint_views import retain_constraints
from .contracts import RibbonPath as DirectorPath
from .contracts import TargetPose as EndpointCase
from .failure_markers import retain_failure_marker
from .graphics import (
    AMBER,
    BLUE,
    GREEN,
    RED,
    coordinates,
    draw_lines,
    draw_text,
    draw_trace,
    set_color,
)
from .original_guides import retain_guides
from .provenance import mark_loaded
from .regions import Region, Series

DARK = (40, 40, 40)


def _trace_name(number: int) -> str:
    """
    Distinguish material boundaries and center from actual numbered conductors.
    """
    return {-1: "A edge", -2: "B edge", 0: "Center"}.get(number, f"Trace{number:02}")


def _rank(name: str) -> int:
    """
    Order display severity without treating unavailable measurements as passes.
    """
    return {"blue": 0, "unmeasured": 0, "amber": 1, "red": 2}[name]


def _sheet(group: Any, series: tuple[Series, ...]) -> dict[str, int]:
    """
    Color disjoint material cells from the same sample classifications as regions.

    A cell takes its worst corner classification, so colored boundaries include
    crossing brackets rather than claiming substation location precision.
    """
    center = series[0]
    lanes = sorted((s for s in series if s.kind == "material J"), key=lambda s: s.offset_mm)
    bend = {s.trace: s for s in series if s.kind == "lane curvature x 3D"}
    points = tuple(s.samples[i].point for i in range(len(center.samples)) for s in lanes)
    mesh_coordinates = coordinates(points)
    indices: list[list[int]] = [[], [], []]
    width = len(lanes)
    for i in range(len(center.samples) - 1):
        for j in range(width - 1):
            rank = max(
                _rank(row.severity(station))
                for station in (i, i + 1)
                for row in (
                    center,
                    lanes[j],
                    lanes[j + 1],
                    bend[lanes[j].trace],
                    bend[lanes[j + 1].trace],
                )
            )
            a, b, c, d = (
                i * width + j,
                i * width + j + 1,
                (i + 1) * width + j,
                (i + 1) * width + j + 1,
            )
            indices[rank].extend((a, b, c, b, d, c))
    for faces, rgb, name in zip(
        indices,
        (BLUE, AMBER, RED),
        ("below displayed thresholds", "near limit", "sampled violation"),
    ):
        if faces:
            mesh = group.addMesh(mesh_coordinates, faces, [], [])
            mesh.name = "Diagnostic material sheet: " + name
            mesh.depthPriority = {
                "below displayed thresholds": 0,
                "near limit": 1,
                "sampled violation": 2,
            }[name]
            mesh.cullMode = adsk.fusion.CustomGraphicsCullModes.CustomGraphicsCullNone
            set_color(mesh, rgb)
    return {
        "sheet_vertices": len(points),
        "blue_triangles": len(indices[0]) // 3,
        "amber_triangles": len(indices[1]) // 3,
        "red_triangles": len(indices[2]) // 3,
    }


def _witnesses(group: Any, series: tuple[Series, ...], findings: tuple[Region, ...]) -> None:
    """
    Show full sampled intervals plus distinct entry and worst-point markers.
    """
    lookup = {(s.kind, s.trace): s for s in series}
    for region in findings:
        rgb = RED if region.severity == "red" else AMBER
        row = lookup[region.kind, region.trace]
        start = max(0, region.first_index - 1)
        finish = min(len(row.samples) - 1, region.last_index + 1)
        line = row.samples[start : finish + 1]
        if len(line) > 1:
            draw_lines(
                group,
                tuple(s.point for s in line),
                rgb,
                f"{region.kind} T{region.trace} u={region.first_u:.5f}..{region.last_u:.5f}",
            )
        for point, name, size in (
            (row.samples[region.first_index].point, "entry", 0.45),
            (region.worst_point, "worst", 0.8),
        ):
            draw_lines(
                group,
                (
                    point.translated(Vector3(0, 1, 0), -size),
                    point.translated(Vector3(0, 1, 0), size),
                ),
                rgb,
                f"{name}: {region.kind} T{region.trace}",
            )
    for i in range(group.count):
        group.item(i).depthPriority = 10


def _graph(group: Any, row: Series) -> None:
    """
    Plot the governing measured series with its actual limit and material fraction.
    """
    values = [s.value for s in row.samples if s.value is not None]
    if not values:
        return
    lo, hi = min(min(values), row.limit), max(max(values), row.limit)
    span = max(hi - lo, 0.2)
    lo -= span * 0.1
    span *= 1.2
    points = tuple(
        Vector3(35 * s.u, -30 + 9 * ((s.value - lo) / span), 0)
        for s in row.samples
        if s.value is not None
    )
    draw_lines(group, points, (40, 40, 40), f"Graph {row.kind} T{row.trace}")
    level = -30 + 9 * (row.limit - lo) / span
    draw_lines(group, (Vector3(0, level, 0), Vector3(35, level, 0)), RED, "Hard threshold")
    draw_text(
        group,
        f"{row.kind} {_trace_name(row.trace)}: {min(values):.4g}..{max(values):.4g}; limit {row.limit:g}",
        Vector3(0, -33, 0),
        DARK,
        1.3,
    )
    draw_text(group, "u=0 -------------------------- u=1", Vector3(0, -36, 0), DARK, 1.2)


def draw_evidence(
    component: Any,
    evidence: Evidence,
    checkpoint: Callable[[], None] = lambda: None,
    *,
    restrictions: tuple[Restriction, ...] = (),
    failure_reason: str | None = None,
) -> dict[str, Any]:
    """
    Render frozen evidence and retain hidden native originals for every result.

    Native guide sketches preserve the same cubics and failed endpoints shown in
    the graphics. Caller checkpoints bound guide creation; no sweeps are built.
    Explicit unsuccessful outcomes and sampled red violations get failure circles.
    """
    if failure_reason is not None and (
        not isinstance(failure_reason, str) or not failure_reason.strip()
    ):
        raise ValueError("An explicit failure reason must be nonempty text.")
    number, case = evidence.identifier, evidence.targets
    originals = retain_guides(component, evidence, checkpoint)
    constraints = retain_constraints(component, evidence, checkpoint, restrictions=restrictions)
    series, findings, primary = evidence.series, evidence.regions, evidence.primary
    groups = {
        name: component.customGraphicsGroups.add()
        for name in ("sheet", "paths", "regions", "graph", "legend", "rulings")
    }
    for name, group in groups.items():
        group.name = name
    stats = _sheet(groups["sheet"], series)
    material = [row for row in series if row.kind == "material J"]
    low, high = (
        min(material, key=lambda row: row.offset_mm),
        max(material, key=lambda row: row.offset_mm),
    )
    half = high.offset_mm
    for guide, rgb in zip(evidence.guides, ((160, 90, 0), (30, 30, 30), (150, 50, 190))):
        draw_trace(groups["paths"], guide, rgb)
    for i in range(17):
        station = i * (len(low.samples) - 1) // 16
        u = low.samples[station].u
        draw_lines(
            groups["rulings"],
            (low.samples[station].point, high.samples[station].point),
            (100, 100, 100),
            f"Material ruling u={u:.4f}",
        )
    for point, width in ((case.start, case.start_width), (case.end, case.end_width)):
        draw_lines(
            groups["paths"],
            (point.translated(width, -half), point.translated(width, half)),
            GREEN,
            "Frozen target",
        )
    _witnesses(groups["regions"], series, findings)
    candidates = [s for s in series if s.kind == primary]
    selected = (
        min(candidates, key=lambda s: min(p.value for p in s.samples if p.value is not None))
        if primary == "material J"
        else candidates[0]
    )
    _graph(groups["graph"], selected)
    draw_text(
        groups["legend"], f"{number} | {primary} | diagnostic sheet", Vector3(-3, -12, 0), DARK, 2
    )
    red = [r for r in findings if r.severity == "red"]
    amber = [r for r in findings if r.severity == "amber"]
    draw_text(
        groups["legend"],
        f"Red regions {len(red)} | Amber regions {len(amber)} | sampled, no native audit",
        Vector3(-3, -16, 0),
        DARK,
        1.2,
    )
    matching = [r for r in red + amber if r.kind == primary and r.trace == selected.trace]
    if matching:
        pool = [r for r in matching if r.severity == "red"] or matching
        region = (
            min(pool, key=lambda r: r.worst_value)
            if selected.direction == "lower"
            else max(pool, key=lambda r: r.worst_value)
        )
        draw_text(
            groups["legend"],
            f"{_trace_name(region.trace)}: u {region.first_u:.4f}..{region.last_u:.4f}; worst {region.worst_value:.5g} at {region.worst_u:.4f}",
            Vector3(-3, -19, 0),
            RED if region.severity == "red" else AMBER,
            1.1,
        )
    explanation = (
        "k*reach > .8: bend concentrated along the run"
        if primary == "center macaroni"
        else "J=1+q eta_s: stations bunch, then reverse at J<=0"
    )
    investigation = (
        "Investigate spreading bend; retain fixed targets"
        if primary == "center macaroni"
        else "Investigate ruling gradient/run length; no frame flip"
    )
    draw_text(groups["legend"], explanation, Vector3(0, -45, 0), DARK, 1.2)
    draw_text(groups["legend"], investigation, Vector3(0, -49, 0), DARK, 1.2)
    if failure_reason is not None or red:
        groups["failure"] = retain_failure_marker(
            component, evidence, failure_reason or "Sampled physical-rule violation"
        )
    return {"groups": groups, **stats, **originals, **constraints}


def draw(
    component: Any,
    number: str,
    path: DirectorPath,
    case: EndpointCase,
    series: tuple[Series, ...],
    findings: tuple[Region, ...],
    primary: str,
) -> dict[str, Any]:
    """
    Adapt historical experiment render calls to the frozen shared evidence view.
    """
    evidence = freeze(
        Candidate(number, path, case, "historical renderer adapter", primary), series, findings
    )
    return draw_evidence(component, evidence)


mark_loaded(__file__)
