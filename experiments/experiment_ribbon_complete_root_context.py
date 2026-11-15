"""
Inspect unchanged split-root geometry with matching root-context distance arguments.

Requires live Fusion/adsk and the independently frozen resume3232 scope. The3231
component-local measurement API stop remains immutable. No CAD, reload, new root
geometry, source tolerance change or solver operation is performed here.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from artifacts.verification.resume3202 import runtime
from artifacts.verification.resume3227 import manifest, memory
from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from experiments.experiment_ribbon_c2_native_qualification import write
from experiments.experiment_ribbon_c2_native_qualification_renewal import read_free
from experiments.experiment_ribbon_complete.native_distance import trimmed_distance_mm
from experiments.experiment_ribbon_complete.root_profiles import (
    CapFrame,
    RootProfile,
    bind_frame,
    partition,
)
from experiments.experiment_ribbon_complete_native_capture import readiness
from experiments.experiment_ribbon_contraction.runner import restore

FOLDER = manifest.ROOT / "artifacts/verification/resume3232"


@dataclass(frozen=True)
class NativeCap:
    """
    Retain an explicitly registered face and its already-qualified ordered material chart.
    """

    side: str
    frame: CapFrame
    face: Any


def prepare(
    owner: Any, plan: dict[str, Any]
) -> tuple[tuple[NativeCap, ...], tuple[RootProfile, ...]]:
    """
    Freeze the same roots and real face identities before issuing distance measurements.
    """
    original = restore(manifest.read(manifest.ROOT / plan["route"]))
    roots = partition(original.targets.lines, original.targets.diameter_mm)
    faces = owner.displayed.component.bRepBodies.item(0).faces
    caps = []
    for record in manifest.read(manifest.ROOT / plan["cap_receipt"])["caps"]:
        side = record["side"]
        assert side in ("start", "end")
        frame = bind_frame(
            original.targets,
            side,
            Vector3(*record["plane_origin_mm"]),
            Vector3(*record["actual_inward_normal"]),
        )
        face = faces.item(record["face_index"])
        assert face.entityToken == record["face_token"]
        caps.append(NativeCap(side, frame, face))
    write(
        FOLDER / "root-plan.json",
        [
            {
                "side": cap.side,
                "frame": asdict(cap.frame),
                "profiles": [asdict(root) for root in roots],
            }
            for cap in caps
        ],
    )
    return tuple(caps), roots


def current(function: Any, qualified_name: str) -> None:
    """
    Compare the actual loaded function body against its frozen source without reloading it.
    """
    import sys

    filename = sys.modules[function.__module__].__file__
    assert isinstance(filename, str)
    assert runtime.signature(function.__code__) == runtime.signature(
        runtime.compiled_body(Path(filename), qualified_name)
    )


def inspect_cap(
    cap: NativeCap,
    roots: tuple[RootProfile, ...],
    owner: Any,
    manager: Any,
    budget: NativeBudget,
    stream: Any,
) -> list[dict[str, Any]]:
    """
    Preserve raw local trim membership and separately measured assembly-context distance.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    observed = []
    for root in roots:
        for edge in root.edges:
            for parameter in (0.0, 0.25, 0.5, 0.75, 1.0):
                budget.check("context-correct root measurement")
                point = cap.frame.point(*edge.geometry.point(parameter))
                native = adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)
                ok, uv = cap.face.evaluator.getParameterAtPoint(native)
                raw = bool(ok and cap.face.evaluator.isParameterOnFace(uv))
                distance = trimmed_distance_mm(native, cap.face, owner.displayed, manager)
                row = {
                    "side": cap.side,
                    "pin": root.pin_number,
                    "edge": edge.geometry.label,
                    "parameter": parameter,
                    "source_profile_index": edge.source_profile_index,
                    "raw_membership": raw,
                    "trimmed_distance_mm": distance,
                }
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                stream.flush()
                observed.append(row)
                if distance > 0.01:
                    raise RuntimeError("A split-root sample differs from its registered native cap")
    return observed


def collect(started: float) -> None:
    """
    Execute one new bounded read-only scope with the established assembly-context API method.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    plan = manifest.read(FOLDER / "plan.json")
    guard = memory.Headroom(plan["minimum_system_free_percent"], read_free)
    budget = NativeBudget(
        memory=guard.memory,
        maximum_seconds=plan["review_seconds"],
        maximum_rss_kib=plan["maximum_rss_kib"],
    )
    budget.started = started
    budget.check("context-correct root readiness")
    owner = readiness(plan)
    assert budget.memory() < plan["launch_rss_kib"]
    checks = (
        (prepare, "prepare"),
        (current, "current"),
        (inspect_cap, "inspect_cap"),
        (collect, "collect"),
        (trimmed_distance_mm, "trimmed_distance_mm"),
        (partition, "partition"),
        (bind_frame, "bind_frame"),
        (CapFrame.point, "CapFrame.point"),
    )
    for function, name in checks:
        current(function, name)
    write(
        FOLDER / "started.json",
        {"compiled_functions": [name for _, name in checks], "epoch_seconds": time.time()},
    )
    caps, roots = prepare(owner, plan)
    rows = []
    manager = adsk.core.Application.get().measureManager
    with (FOLDER / "samples.jsonl").open("x") as stream:
        for cap in caps:
            rows.extend(inspect_cap(cap, roots, owner, manager, budget, stream))
    assert len(rows) == plan["samples"]
    budget.check("context-correct root completion")
    readiness(plan)
    write(
        FOLDER / "result.json",
        {
            "status": "sampled_split_root_correspondence_pass",
            "known_layouts": 1,
            "samples": len(rows),
            "raw_membership_misses": sum(not row["raw_membership"] for row in rows),
            "maximum_trimmed_distance_mm": max(row["trimmed_distance_mm"] for row in rows),
            "wall_seconds": time.perf_counter() - started,
            "rss_kib": budget.memory(),
            "system_free_samples": guard.samples,
            "minimum_system_free_percent": guard.minimum_observed_percent,
            "native_builds": 0,
            "full_physical_audits": 0,
            "fresh_layouts": 0,
            "ownership_unchanged": True,
        },
    )
