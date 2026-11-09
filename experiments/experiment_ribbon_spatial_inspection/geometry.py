"""
Share feature-focused material sections, actual contact witnesses and fixed terminal proxies.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.inspection.geometry import local_frame
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import ProbeOrder, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import (
    FoldRoute,
    PlacedPiece,
    Pose,
    pose_error,
)
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_terminal_hardware.check import inspect as inspect_hardware
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware


def xyz(vector: Vector3) -> list[float]:
    """
    Preserve millimeter world coordinates without fitting or display transforms.
    """
    return [vector.x, vector.y, vector.z]


def physical(piece: PlacedPiece, u: float, q: float, b: float) -> Vector3:
    """
    Evaluate the joined material profile on its exact isometric map, including thickness.
    """
    point, forward, across, _ = piece.surface(u, q)
    return point.translated(unit(cross(forward, across)), b)


def stations(route: FoldRoute) -> list[tuple[int, float, str]]:
    """
    Include piece joins and brackets around actual diagonal-fold entry/exit on both outer edges.

    These are constant material-coordinate sections, which can curve through an
    oblique fold. They are not assumed rigid planes. At most512are permitted.
    """
    output = []
    for index, piece in enumerate(route.pieces):
        values = {0.0: "start", 0.25: "quarter", 0.5: "middle", 0.75: "three-quarter", 1.0: "end"}
        geometry = piece.geometry
        if isinstance(geometry, CylindricalFold):
            length = geometry.material_length_mm
            for q, label in (
                (-route.half_width_mm, "B"),
                (0.0, "center"),
                (route.half_width_mm, "A"),
            ):
                for edge, along in (
                    ("entry", 0.0),
                    ("exit", geometry.radius_mm * abs(geometry.angle_radians)),
                ):
                    value = (
                        geometry.before_mm
                        + along / math.cos(geometry.bank_radians)
                        - q * math.tan(geometry.bank_radians)
                    ) / length
                    for offset, bracket in ((-1e-4, "before"), (0.0, "at"), (1e-4, "after")):
                        if 0 <= value + offset <= 1:
                            values[value + offset] = f"{label} {edge} {bracket}"
        output.extend((index, value, label) for value, label in sorted(values.items()))
    if len(output) > 512:
        raise ValueError("Inspection exceeds512feature sections")
    return output


def capture(route: FoldRoute, checkpoint: Callable[[], None]) -> dict[str, Any]:
    """
    Measure and render the same frozen route without invoking an endpoint solver or native builder.

    Lobed contours use exact rational profile samples on the exact material map.
    Connecting display chords remain approximations; contact has its own bounded
    analytic result, and full physical/native compliance remains unmeasured.
    """
    checkpoint()
    target = route.targets
    profile = material_profile(target.lines, target.diameter_mm)
    perimeter = [arc.point(i / 4) for arc in profile for i in range(4)]
    perimeter.append(perimeter[0])
    sections = []
    for piece_index, u, label in stations(route):
        checkpoint()
        piece = route.pieces[piece_index]
        point, forward, across, _ = piece.surface(u, 0.0)
        frame = local_frame(point, forward, across)
        sections.append(
            {
                "id": len(sections),
                "piece": piece_index,
                "u": u,
                "label": label,
                "frame": {
                    "origin": xyz(frame.origin),
                    "x": xyz(frame.x),
                    "y": xyz(frame.y),
                    "z": xyz(frame.z),
                },
                "outline": [xyz(physical(piece, u, q, b)) for q, b in perimeter],
            }
        )
    traces = []
    offsets = [
        ("A outer edge", route.half_width_mm),
        ("center", 0.0),
        ("B outer edge", -route.half_width_mm),
    ]
    offsets += [
        (f"conductor {i + 1}", (i + 0.5 - target.lines / 2) * target.diameter_mm)
        for i in range(target.lines)
    ]
    for name, q in offsets:
        traces.append(
            {
                "name": name,
                "q_mm": q,
                "points": [
                    xyz(piece.surface(i / 32, q)[0]) for piece in route.pieces for i in range(33)
                ],
            }
        )
    hardware = Hardware.create(target, Dimensions.scaled(target))
    contact = inspect_contact(
        route,
        maximum_pairs=2048,
        checkpoint=checkpoint,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        witness_probe=FlatProbe(),
        probe_order=ProbeOrder.MATERIAL_CELLS,
    )
    hardware_report = inspect_hardware(route, hardware, maximum_cells=512, checkpoint=checkpoint)
    witnesses = []
    if contact.witness is not None:
        w = contact.witness
        witnesses.append(
            {
                "kind": "self contact",
                "point": xyz(w.point),
                "members": [
                    {"piece": index, "material": list(material)}
                    for index, material in zip(w.pieces, (w.first, w.second))
                ],
            }
        )
    if hardware_report.witness is not None:
        w = hardware_report.witness
        witnesses.append(
            {
                "kind": "hardware " + w.terminal,
                "point": xyz(w.point),
                "members": [{"piece": w.piece, "material": list(w.material)}],
            }
        )
    for witness in witnesses:
        for member in witness["members"]:
            index = member["piece"]
            u, q, _ = member["material"]
            _, forward, across, _ = route.pieces[index].surface(u, q)
            member["normal"] = xyz(unit(cross(forward, across)))
            for offset, label in ((-1e-4, "before"), (0.0, "at"), (1e-4, "after")):
                value = u + offset
                if not 0 <= value <= 1:
                    continue
                if len(sections) >= 512:
                    raise ValueError("Inspection exceeds512feature/witness sections")
                piece = route.pieces[index]
                point, forward, across, _ = piece.surface(value, 0.0)
                frame = local_frame(point, forward, across)
                sections.append(
                    {
                        "id": len(sections),
                        "piece": index,
                        "u": value,
                        "label": witness["kind"] + " " + label,
                        "frame": {
                            "origin": xyz(frame.origin),
                            "x": xyz(frame.x),
                            "y": xyz(frame.y),
                            "z": xyz(frame.z),
                        },
                        "outline": [xyz(physical(piece, value, q, b)) for q, b in perimeter],
                    }
                )
    model = MovableBends(route)
    coordinates = []
    for index, full_index in enumerate(model.indices):
        kind = full_index % 4
        factor = model.scale if kind == 0 else 180 / math.pi
        coordinates.append(
            {
                "index": index,
                "name": f"slot {full_index // 4 + 1} "
                + ("straight" if kind == 0 else "angle" if kind == 1 else "bank"),
                "value": model.initial[index] * factor,
                "unit": "mm" if kind == 0 else "degrees",
                "maximum_delta": min(target.diameter_mm * 0.1, model.scale * 0.001)
                if kind == 0
                else 0.25,
            }
        )
    start = Pose(target.start, target.start_tangent, target.start_width)
    end = Pose(target.end, target.end_tangent, target.end_width)
    cap_errors = pose_error(route.pieces[0].pose, start) + pose_error(
        route.pieces[-1].end_pose(), end
    )
    all_points = [point for trace in traces for point in trace["points"]]
    return {
        "schema": "ribbon-spatial-inspection-v1",
        "route": snapshot(route),
        "sections": sections,
        "traces": traces,
        "coordinates": coordinates,
        "hardware": [
            {"terminal": box.terminal.value, "corners": [xyz(p) for p in box.corners()]}
            for box in hardware.boxes
        ],
        "targets": asdict(target),
        "witnesses": witnesses,
        "measurements": {
            "length_mm": route.material_length_mm,
            "cap_position_error_mm": max(cap_errors[0], cap_errors[2]),
            "cap_frame_vector_error": max(cap_errors[1], cap_errors[3]),
            "contact": asdict(contact),
            "hardware": asdict(hardware_report),
            "sampled_center_bounds_mm": [
                [min(p[i] for p in all_points), max(p[i] for p in all_points)] for i in range(3)
            ],
        },
        "scope": "Exact material-map samples and joined-profile contours; display chords approximate. Proxy hardware, not actual connectors. Clearance is separately bounded analytic evidence. Native/full physical audit unmeasured.",
    }
