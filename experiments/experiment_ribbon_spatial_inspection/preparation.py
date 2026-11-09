"""
Author one unseen numerical-only gym diagnostic and freeze its inspection packet without resampling.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_locked_solver import lock
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification, defaults
from experiments.experiment_ribbon_regression.fresh import FreshRegistry

from .ledger import create, digest

ROOT = Path(__file__).resolve().parents[2]


def author(directory: Path, document_id: str) -> dict[str, Any]:
    """
    Reserve one new N5 layout before its sole120second numerical solve; authorize zero native bodies.

    Fresh endpoint frames/rolls and nonadjacent cubicles follow the maintained gym
    generator. No outcome-based resampling is available from this entry point.
    """
    directory.mkdir(parents=True, exist_ok=False)
    payload = defaults(Scene(Config(0, 5, 0.75, 300, 300), Goal(0, 0), Goal(25, 0)))
    payload["maximum_cases"] = 1
    payload["ranges"]["lines"] = {"min": "5", "max": "5", "step": "1"}
    payload["avoid_adjacent_zones"] = True
    payload["screenshots"] = {"enabled": False, "directory": "~/Pictures/test4"}
    for end in ("a", "b"):
        payload["ranges"][end + "_roll"] = {"min": "-90", "max": "90", "step": "1"}
    registry = FreshRegistry(ROOT / "artifacts/verification/ribbon-fresh-runs/novelty.sqlite3")
    fresh = registry.prepare(
        Specification.parse(payload),
        "spatial-" + uuid4().hex,
        {"population": "fresh_spatial_diagnostic", "maximum_cases": 1, "native_attempts": 0},
    )
    scene = fresh.specification.scene(0)
    plan = {
        "question": "One fresh spatial inspection and one precommitted bounded numerical perturbation; no solver repair or native body.",
        "identifier": fresh.identifier,
        "specification": fresh.specification.payload(),
        "fingerprints": fresh.fingerprints,
        "sources": lock.verify(),
        "native_attempts": 0,
        "numerical_seconds": 120,
        "rss_kib": 4194304,
        "analysis_seconds": 10,
        "probe_cpu_seconds": 0.35,
        "probe_wall_seconds": 2,
        "stop": "One solve; preserve any failure. No resampling/retries. One probe only after a committed prediction; no native construction.",
    }
    create(directory / "diagnostic-plan.json", plan)
    job = directory / "job"
    job.mkdir()
    create(
        job / "plan.json",
        {
            "version": "guide-material-v2",
            "result_id": fresh.identifier + ":guide-material-v2",
            "document_id": document_id,
            "sources": plan["sources"],
            "targets": asdict(scene.targets),
            "gym": scene.payload(),
            "settings": {
                "first_pass_optimization": True,
                "smoothing_percent": 1,
                "material_uv": False,
                "terminal_hardware": True,
            },
            "contact_measurement_policy": "require_separation",
            "native_point_tolerance_mm": 1e-5,
        },
    )
    return {
        "job": str(job),
        "identifier": fresh.identifier,
        "seed": fresh.specification.seed,
        "target_fingerprint": fresh.fingerprints[0],
    }


def freeze_job(directory: Path) -> dict[str, Any]:
    """
    Inspect the sole original accepted or explicitly rejected material route without another solve.
    """
    from devtools.ribbon_analysis.inspection.archive import snapshot_payload
    from experiments.experiment_ribbon_contraction.runner import restore
    from experiments.experiment_ribbon_locked_solver.inspection import freeze
    from experiments.experiment_ribbon_locked_solver.rejected_selection import select

    from .geometry import capture

    plan = json.loads((directory / "diagnostic-plan.json").read_text())
    if lock.verify() != plan["sources"]:
        raise RuntimeError("Solver source drift before inspection capture")
    job = directory / "job"
    if (job / "route.json").exists():
        route = restore(json.loads((job / "route.json").read_text()))
        disposition = "Numerical route; no native construction attempted"
    else:
        rejected = json.loads((job / "rejected-geometry.json").read_text())
        job_plan = json.loads((job / "plan.json").read_text())
        route, record = select(rejected, job_plan["targets"])
        disposition = "NOT ACCEPTED: " + record["disposition"]
    budget = NativeBudget(maximum_seconds=10, maximum_rss_kib=4194304)
    started = monotonic()
    last_memory_check = started

    def checkpoint() -> None:
        """
        Check time at every step and sample RSS at most ten times per second.
        """
        nonlocal last_memory_check
        now = monotonic()
        if now - started >= 10:
            raise TimeoutError("Spatial capture exceeded10seconds")
        if now - last_memory_check >= 0.1:
            budget.check("spatial capture")
            last_memory_check = now

    budget.check("spatial capture launch")
    packet = capture(route, checkpoint)
    packet["original_disposition"] = disposition
    packet["original_guides_snapshot"] = snapshot_payload(freeze(route, "spatial-original"))
    sources = dict(plan["sources"])
    for path in sorted(Path(__file__).parent.iterdir()):
        if path.suffix in (".py", ".html"):
            sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    create(directory / "baseline.json", packet)
    create(
        directory / "inspection-plan.json",
        {
            "baseline_fingerprint": digest(packet),
            "sources": sources,
            "diagnostic_identifier": plan["identifier"],
            "analysis_seconds": monotonic() - started,
            "native_attempts": 0,
            "probe_cpu_seconds": 0.35,
            "probe_wall_seconds": 2,
        },
    )
    return {
        "disposition": disposition,
        "sections": len(packet["sections"]),
        "witnesses": len(packet["witnesses"]),
        "baseline_fingerprint": digest(packet),
        "analysis_seconds": monotonic() - started,
    }
