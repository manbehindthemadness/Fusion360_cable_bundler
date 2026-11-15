"""
Check frozen split-root profiles against retained native caps without creating geometry.

Requires live Fusion/adsk, exact qualified ownership and resume3231/plan.json.
This bounded inspection writes only local receipts. It never lofts, offsets a
branch, moves a target, chooses a nearest cap or claims junction compliance.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from artifacts.verification.resume3202 import runtime
from artifacts.verification.resume3227 import manifest, memory
from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from experiments.experiment_ribbon_c2_native_qualification import write
from experiments.experiment_ribbon_c2_native_qualification_renewal import read_free
from experiments.experiment_ribbon_complete import root_profiles
from experiments.experiment_ribbon_complete_native_capture import readiness
from experiments.experiment_ribbon_contraction.runner import restore

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "artifacts/verification/resume3231"


def collect(started: float) -> None:
    """
    Preserve and inspect each planned root edge on its explicitly registered real cap.

    Raw native trim membership and minimum trimmed distance are separate evidence.
    A membership miss can be corroborated by actual distance within0.01mm, never
    by snapping the source point. Preserve every row and stop at the first failure.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    plan = manifest.read(FOLDER / "plan.json")
    guard = memory.Headroom(10, read_free)
    budget = NativeBudget(
        memory=guard.memory, maximum_seconds=plan["review_seconds"], maximum_rss_kib=4194304
    )
    budget.started = started
    budget.check("split-root capture readiness")
    owner = readiness(plan)
    assert budget.memory() < 3984588
    assert memory.checked_read(read_free) >= 10
    compiled = {}
    for module, names in ((root_profiles, ("partition", "seam", "bind_frame", "CapFrame.point")),):
        filename = module.__file__
        assert isinstance(filename, str)
        for name in names:
            body: Any = module
            for part in name.split("."):
                body = getattr(body, part)
            assert runtime.signature(body.__code__) == runtime.signature(
                runtime.compiled_body(Path(filename), name)
            )
            compiled[name] = "exact_current_compiled_body"
    assert runtime.signature(collect.__code__) == runtime.signature(
        runtime.compiled_body(Path(__file__), "collect")
    )
    compiled["collect"] = "exact_current_compiled_body"
    write(FOLDER / "started.json", {"compiled": compiled, "epoch_seconds": time.time()})
    route = restore(manifest.read(ROOT / plan["route"]))
    caps = manifest.read(ROOT / plan["cap_receipt"])["caps"]
    roots = root_profiles.partition(route.targets.lines, route.targets.diameter_mm)
    fractions = (0.0, 0.25, 0.5, 0.75, 1.0)
    assert sum(len(root.edges) for root in roots) * len(caps) * len(fractions) == plan["samples"]
    body = owner.displayed.component.bRepBodies.item(0)
    app = adsk.core.Application.get()
    maximum, observed, distance_queries, misses = 0.0, 0, 0, 0
    bound_roots = []
    prepared = []
    for cap in caps:
        side = cap["side"]
        assert side in ("start", "end")
        frame = root_profiles.bind_frame(
            route.targets,
            side,
            Vector3(*cap["plane_origin_mm"]),
            Vector3(*cap["actual_inward_normal"]),
        )
        face = body.faces.item(cap["face_index"])
        assert face.entityToken == cap["face_token"]
        prepared.append((cap, frame, face))
        bound_roots.append(
            {"side": side, "frame": asdict(frame), "profiles": [asdict(root) for root in roots]}
        )
    write(FOLDER / "root-plan.json", bound_roots)
    with (FOLDER / "samples.jsonl").open("x") as stream:
        for cap, frame, face in prepared:
            side = cap["side"]
            for root in roots:
                for edge in root.edges:
                    for fraction in fractions:
                        budget.check("split-root trimmed-cap correspondence")
                        q, b = edge.geometry.point(fraction)
                        point = frame.point(q, b)
                        native_point = adsk.core.Point3D.create(
                            point.x / 10, point.y / 10, point.z / 10
                        )
                        ok, uv = face.evaluator.getParameterAtPoint(native_point)
                        member = bool(ok and face.evaluator.isParameterOnFace(uv))
                        distance = (
                            app.measureManager.measureMinimumDistance(native_point, face).value * 10
                        )
                        distance_queries += 1
                        row = {
                            "side": side,
                            "pin": root.pin_number,
                            "edge": edge.geometry.label,
                            "parameter": fraction,
                            "source_profile_index": edge.source_profile_index,
                            "raw_membership": member,
                            "trimmed_distance_mm": distance,
                        }
                        stream.write(json.dumps(row, allow_nan=False) + "\n")
                        stream.flush()
                        observed += 1
                        misses += int(not member)
                        maximum = max(maximum, distance)
                        if not 0 <= distance <= 0.01:
                            raise RuntimeError(
                                "A planned split-root edge differs from its actual native cap"
                            )
    budget.check("split-root capture completion")
    readiness(plan)
    write(
        FOLDER / "result.json",
        {
            "status": "sampled_split_root_correspondence_pass",
            "known_layouts": 1,
            "samples": observed,
            "distance_queries": distance_queries,
            "raw_membership_misses": misses,
            "maximum_trimmed_distance_mm": maximum,
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
