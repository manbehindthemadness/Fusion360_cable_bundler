"""
Freeze twelve unseen gym inputs and measure the unchanged two-stage tight constructor.
"""

from __future__ import annotations

import hashlib
import json
import resource
import sys
from dataclasses import asdict, replace
from functools import partial
from pathlib import Path
from time import perf_counter, process_time
from typing import Any, TextIO

from cable_bundler.routing.geometry import difference, magnitude
from devtools.ribbon_analysis.gym.scene import Config, generate
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_route.geometry import Straight, pose_error
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver.lock import ROOT, verify
from experiments.experiment_ribbon_spline_guide.guide import agreement

from .guide_frames import Frames
from .solve import construct

# Endpoint generation only: these seeds never initialize or select route guesses.
CONFIGS = (
    (1, 0.75, 300, 300),
    (3, 1.0, 400, 300),
    (8, 1.5, 500, 300),
    (3, 0.75, 300, 50),
    (8, 1.0, 300, 75),
    (16, 0.5, 300, 100),
    (2, 1.5, 350, 150),
    (5, 0.5, 600, 400),
    (12, 0.75, 450, 200),
    (24, 1.0, 300, 600),
    (32, 1.5, 700, 100),
    (64, 0.5, 400, 250),
)
NATIVE_IDS = ("gym424-01", "gym424-04", "gym424-08")


def digest(path: Path) -> str:
    """
    Pin exact source or input bytes without changing them.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(event: dict[str, Any], *, outcome: dict[str, Any], stream: TextIO) -> None:
    """
    Preserve every branch and rejected certificate in the explicitly bound case ledger.
    """
    stream.write(json.dumps(event, allow_nan=False) + "\n")
    if event["stage"] == "feature_contact" and event["status"] != "started":
        outcome["contact_events"].append(event["status"])


def main() -> None:
    """
    Retain every outcome under fixed budgets; never resample, tune or build natively here.
    """
    out = ROOT / "artifacts/verification/ribbon_holdout424"
    out.mkdir(exist_ok=False)
    inputs = []
    for index, (lines, diameter, void, zone) in enumerate(CONFIGS, 1):
        name = f"gym424-{index:02}"
        scene = generate(Config(2026110200 + index, lines, diameter, void, zone))
        targets = replace(scene.targets, name=name)
        path = out / f"{name}-input.json"
        path.write_text(
            json.dumps({"scene": scene.payload(), "targets": asdict(targets)}, indent=2)
        )
        inputs.append((name, targets, path))
    pins = verify()
    paths = (
        *Path(__file__).parent.glob("*.py"),
        ROOT / "experiments/experiment_ribbon_reduced_joints/kinematics.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        ROOT / "artifacts/verification/ribbon_snap410/result.json",
        *(path for _, _, path in inputs),
    )
    extra = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    tolerance = json.loads((ROOT / "artifacts/verification/ribbon_snap410/result.json").read_text())
    if tolerance["status"] != "completed":
        raise RuntimeError("Live native tolerance prerequisite missing")
    threshold = float(tolerance["point_tolerance_mm"])
    plan: dict[str, Any] = {
        "question": "Does unchanged421two-stage tight construction transfer to unseen endpoint-gym layouts?",
        "cases": [name for name, _, _ in inputs],
        "sources": pins,
        "experiment_sources": extra,
        "procedure": "One constructor per frozen input, guide parameter1/2only, unchanged421root enumeration/angular feasibility repair/straight allocation/contact budgets. No extra-feature insertion, smoothing, radius relaxation, post-pass optimization, guessed seed bank or historical route fallback. Radius=D/2/PinchLimit.fraction*(1+1e-9), as selected solver. All inputs frozen before first solve; no outcome filtering.",
        "coverage": "12unseen complete gym layouts:3ordinary default-depth contexts,3shallow-zone contexts,6additional independent generated contexts; counts1..64,diameters0.5..1.5mm. This replaces legacy non-gym inventories under gym-only revision. Feasibility unknown for every case, no invalid-oracle accuracy claim; no split/full-winding/obstacle coverage. Context groups are generation parameters, not promises of physical difficulty or feasibility. No previous selected-solver comparison or shortest-route certificate.",
        "acceptance": "Separated thick joined-profile contact, unchanged ordered targets/profile, fixed declared radii, cap/join<=1e-7, sampled local material metric<=1e-10. Positive straight slots<=measured native point tolerance rejected by candidate. Length/chord, guide agreement and flat lengths measured without an invented quality threshold. No closure/contact certificate means unresolved, not impossible.",
        "limits": {
            "case_seconds": 4,
            "phase_seconds": 48,
            "rss_bytes": 4294967296,
            "contact_attempts_per_case": 2,
            "contact_pairs": 1024,
            "root_chains": 8,
            "angular_corrections_per_chain": 2,
            "step_halvings": 2,
            "native_attempts_here": 0,
        },
        "native_sample_preselected": list(NATIVE_IDS),
        "later_native_scope": "Only these3IDs if numerically accepted; no substitutions for rejected/unresolved cases. Separate pinned plan,3attempts maximum,120s/case,370s/phase,4GiB RSS/3.8GiB launch headroom. Unknown kernel prediction; unchanged strict named fidelity audit,stop first source/resource/API/build/fidelity failure. No geometry repair or retries. Other9native-unattempted. Full physical audit unmeasured.",
        "stop": "First resource/source/input/API/harness error or accepted-gate failure stops remaining work. Ordinary no-closure/contact-unresolved outcomes retained and batch proceeds unchanged. No parameter changes, budget expansion or specimen refinement.",
    }
    (out / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in extra:
        if not relative.startswith("artifacts/"):
            saved = out / "source_snapshot" / (relative + ".frozen")
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes((ROOT / relative).read_bytes())
    phase, cpu = perf_counter(), process_time()
    report: dict[str, Any] = {
        "status": "running",
        "cases": [],
        "unattempted": plan["cases"].copy(),
        "native_attempts": 0,
        "full_physical_audits": 0,
    }
    try:
        for name, targets, _ in inputs:
            started, case_cpu = perf_counter(), process_time()
            last_sources = started

            def checkpoint(case_started: float = started) -> None:
                """
                Enforce frozen case/phase/RSS budgets and periodically recheck all pins.
                """
                nonlocal last_sources
                now = perf_counter()
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if now - case_started > 4 or now - phase > 48 or rss >= 4294967296:
                    raise TimeoutError("Frozen424resource limit")
                if now - last_sources >= 0.5:
                    if verify() != pins or any(digest(ROOT / p) != h for p, h in extra.items()):
                        raise RuntimeError("424source/input drift")
                    last_sources = now

            row: dict[str, Any] = {"id": name, "native": "not_attempted", "contact_events": []}
            report["cases"].append(row)
            report["unattempted"].remove(name)
            checkpoint()
            with (out / f"{name}-trials.jsonl").open("x", buffering=1) as stream:
                record = partial(_record, outcome=row, stream=stream)
                try:
                    frames = Frames.create(targets)
                    radius = targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
                    result = construct(
                        Boundary(targets, radius), frames, (0.5,), threshold, checkpoint, record
                    )
                except ValueError as error:
                    row.update(status="representation_unresolved", error=str(error))
                else:
                    row.update(
                        status=result.status,
                        contacts=result.contacts,
                        contact_seconds=result.contact_seconds,
                        closed_branches=result.closed_branches,
                        unattempted_contacts=result.unattempted_contacts,
                    )
                    if result.route is not None and result.allocation is not None:
                        route = result.route
                        joins = max(
                            (
                                max(pose_error(a.end_pose(), b.pose))
                                for a, b in zip(route.pieces, route.pieces[1:])
                            ),
                            default=0.0,
                        )
                        caps, metric = cap_error(route), material_error(route)
                        if (
                            route.targets != targets
                            or caps > 1e-7
                            or metric > 1e-10
                            or joins > 1e-7
                            or any(
                                f.radius_mm != radius
                                for f in result.allocation.chain.topology.folds
                            )
                        ):
                            raise ArithmeticError("424accepted gate failure")
                        flat = sum(
                            p.geometry.material_length_mm
                            if isinstance(p.geometry, Straight)
                            else p.geometry.material_length_mm
                            * (
                                1
                                - (p.geometry.bend_interval(0)[1] - p.geometry.bend_interval(0)[0])
                            )
                            for p in route.pieces
                        )
                        row.update(
                            length_mm=route.material_length_mm,
                            chord_mm=magnitude(difference(targets.end, targets.start)),
                            guide=asdict(agreement(route, frames.guide)),
                            flat_percent=100 * flat / route.material_length_mm,
                            primitives=len(result.allocation.chain.topology.folds),
                            cap_error=caps,
                            material_metric=metric,
                            join_error=joins,
                        )
                        (out / f"{name}-route.json").write_text(
                            json.dumps(snapshot(route), indent=2)
                        )
            checkpoint()
            row.update(seconds=perf_counter() - started, cpu_seconds=process_time() - case_cpu)
            print(json.dumps(row), flush=True)
        if verify() != pins or any(digest(ROOT / p) != h for p, h in extra.items()):
            raise RuntimeError("424final source/input drift")
        report["status"] = "completed"
    except (
        ArithmeticError,
        KeyError,
        OSError,
        RuntimeError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as error:
        report.update(status="stopped", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report.update(
            seconds=perf_counter() - phase,
            cpu_seconds=process_time() - cpu,
            maximum_local_rss_native_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        )
        (out / "result.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
