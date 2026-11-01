"""
Pin and measure bounded coupled contraction on four bend-reduced gym routes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from collections import Counter
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import ROOT, material_error, restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_radius_allocation.solve import Trial as RadiusTrial
from experiments.experiment_ribbon_radius_allocation.solve import solve as allocate_radii

from .model import Model
from .relax import Trial, relax

CASES = tuple(
    (name, f"artifacts/verification/ribbon_bends263/{name}-reduced.json")
    for name in ("calibration", "gym-1", "gym-2", "gym-3")
)


def _record(trial: Trial, *, entries: list[Trial], path: Path) -> None:
    """
    Retain every proposal, including failed nonlinear closure and contact rejection.
    """
    entries.append(trial)
    with path.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "iteration": trial.iteration,
                    "backtrack": trial.backtrack,
                    "status": trial.status,
                    "values": trial.values,
                    "contact": asdict(trial.contact) if trial.contact else None,
                    "route": snapshot(trial.route) if trial.route else None,
                }
            )
            + "\n"
        )


def main() -> None:
    """
    Execute one frozen procedure without seed discovery, retries or budget renewal.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-directory", type=Path)
    parser.add_argument("--normalize-radii", action="store_true")
    args = parser.parse_args()
    cases = CASES
    if args.input_directory is not None:
        directory = args.input_directory.resolve()
        directory.relative_to(ROOT / "artifacts/verification")
        cases = tuple(
            (name, str((directory / f"{name}-joint.json").relative_to(ROOT))) for name, _ in CASES
        )
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        ROOT / "experiments/experiment_ribbon_bend_reduction/closure.py",
        ROOT / "experiments/experiment_ribbon_bend_reduction/rewrite.py",
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_radius_allocation").glob("*.py"),
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/contracts.py",
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(ROOT / path for _, path in cases),
    }
    hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    plan = {
        "question": "Does decreasing explicit straight travel while relaxing fold angles contract the already bend-reduced routes?",
        "method": "v1: projected straight-length gradient under six normalized endpoint equations; fixed banks/radii/leads, bounded signed angles; nonlinear Newton retraction; strict total and straight-length decrease plus full thick-contact acceptance. No seed bank or endpoint rediscovery.",
        "cases": list(cases),
        "coverage": "Four examined development configurations from the recorded input paths. Same procedure/budgets on all, no holdout or global optimum claim.",
        "radius_normalization": "One existing radius/straight LP followed by at most8contact fractions after angle relaxation; preserve angles/banks/leads and nonincreasing material length. Same case/phase budget includes both passes."
        if args.normalize_radii
        else "not requested",
        "fixed": "Both ordered target frames, material identities/profile, local equal material increments,99.6%pinch,no lateral bending. Reroute the plan only; native builder untouched.",
        "degrees_of_freedom": "Diameter-normalized nonnegative explicit straight lengths and signed fold angles in[-pi,pi]. Individual straights can redistribute; combined straight length and whole material length must both decrease. Banks/radii/flat leads fixed. Numerical zero pieces may disappear, bend count may not increase.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "iterations": 8,
            "proposals_per_iteration": 6,
            "newton_corrections_per_proposal": 6,
            "newton_halvings": 4,
            "maximum_angle_step_radians": 0.2,
            "contact_pairs": 20000,
            "contact_depth": 36,
            "rss_bytes": 4294967296,
            "native_attempts": 0,
            "radius_allocations": 1 if args.normalize_radii else 0,
            "radius_linear_supports": 2517 if args.normalize_radii else 0,
            "radius_contact_fractions": 8 if args.normalize_radii else 0,
        },
        "numeric_bounds": "Finite difference1e-5 in diameter-scaled/radian coordinates; affine rank1e-10/consistency1e-8; retraction normalized residual1e-10; complete ordered caps<=existing1e-7; minimum measured joint length gain1e-8D; zero pieces<=1e-12mm/radians.",
        "stop": "First source/resource/harness or falseacceptance stops batch. Expected unresolved closure, no-gain and contact rejections preserve last accepted route. Retain every proposal and unattempted case. No automatic refinement/budget renewal.",
        "prediction": "Unknown progress/closure/contact/native outcomes; passing local material equations does not certify continuous native contact, equilibrium or universal optimality.",
        "sources": hashes,
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in hashes:
        copied = run / "sources" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((ROOT / relative).read_bytes())
    batch_started = time.monotonic()
    output: dict[str, Any] = {
        "status": "running",
        "cases": [],
        "unattempted": [name for name, _ in cases],
        "native_attempts": 0,
    }
    try:
        for name, relative in cases:
            started = time.monotonic()

            def checkpoint(case_started: float = started) -> None:
                """
                Bound wall time and peak local RSS throughout descent and contact.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - batch_started > 600
                ):
                    raise TimeoutError("Frozen coupled-contraction resource limit")

            checkpoint()
            for source, digest in hashes.items():
                if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Source drift: " + source)
            route = restore(json.loads((ROOT / relative).read_text()))
            baseline = inspect_contact(route, checkpoint=checkpoint)
            model = Model(route)
            row: dict[str, Any] = {
                "id": name,
                "baseline_length_mm": route.material_length_mm,
                "baseline_straight_mm": model.straight_length(model.initial),
                "baseline_folds": fold_count(route),
                "baseline_contact": asdict(baseline),
                "baseline_seconds": time.monotonic() - started,
            }
            output["cases"].append(row)
            output["unattempted"].remove(name)
            if baseline.status != "separated":
                row["status"] = "baseline_contact_unaccepted"
                continue
            trials: list[Trial] = []
            record = partial(_record, entries=trials, path=run / f"{name}-trials.jsonl")
            relaxation_started = time.monotonic()
            result, reason = relax(route, checkpoint=checkpoint, record=record)
            angle_seconds = time.monotonic() - relaxation_started
            radius_seconds = 0.0
            radius_fraction = 0.0
            radius_reason = "not_requested"
            radius_trials: list[RadiusTrial] = []

            def record_radius(
                trial: RadiusTrial,
                case_id: str = name,
                entries: list[RadiusTrial] = radius_trials,
            ) -> None:
                """
                Retain every second-stage radius proposal independently of angle trials.
                """
                entries.append(trial)
                with (run / f"{case_id}-radius-trials.jsonl").open("a") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "fraction": trial.fraction,
                                "contact": asdict(trial.contact),
                                "route": snapshot(trial.route),
                            }
                        )
                        + "\n"
                    )

            if args.normalize_radii:
                radius_started = time.monotonic()
                result, optimum, radius_fraction, radius_reason = allocate_radii(
                    result, checkpoint=checkpoint, record=record_radius
                )
                radius_seconds = time.monotonic() - radius_started
                if optimum is not None:
                    (run / f"{name}-radius-linear.json").write_text(
                        json.dumps(asdict(optimum), indent=2)
                    )
            seconds = time.monotonic() - relaxation_started
            final_contact = inspect_contact(result, checkpoint=checkpoint)
            metric = material_error(result)
            bends = [p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)]
            pinch = max((result.targets.diameter_mm / 2 / p.radius_mm for p in bends), default=0)
            if (
                final_contact.status != "separated"
                or cap_error(result) > 1e-7
                or metric > 1e-10
                or pinch > 0.996
                or result.targets != route.targets
                or result.material_length_mm > route.material_length_mm
                or fold_count(result) > fold_count(route)
            ):
                raise ArithmeticError("Independent final coupled-contraction audit failed")
            accepted = [trial for trial in trials if trial.status == "accepted"]
            final_values = accepted[-1].values if accepted else model.initial
            max_angle = max(
                (
                    abs(a - b)
                    for i, (a, b) in enumerate(zip(final_values, model.initial))
                    if i not in model.straight_indices
                ),
                default=0,
            )
            row.update(
                status="contracted" if accepted or radius_fraction else "unchanged",
                final_length_mm=result.material_length_mm,
                gain_percent=100 * (1 - result.material_length_mm / route.material_length_mm),
                final_straight_mm=sum(
                    p.geometry.material_length_mm
                    for p in result.pieces
                    if isinstance(p.geometry, Straight)
                ),
                final_folds=fold_count(result),
                maximum_angle_change_radians=max_angle,
                cap_error=cap_error(result),
                material_metric_error=metric,
                pinch_fraction=pinch,
                final_contact=asdict(final_contact),
                reduction_seconds=seconds,
                angle_relaxation_seconds=angle_seconds,
                radius_normalization_seconds=radius_seconds,
                radius_fraction=radius_fraction,
                radius_reason=radius_reason,
                radius_proposals=len(radius_trials),
                radius_outcomes=dict(Counter(t.contact.status for t in radius_trials)),
                radii_before_mm=[
                    p.geometry.radius_mm
                    for p in route.pieces
                    if isinstance(p.geometry, CylindricalFold)
                ],
                radii_after_mm=[p.radius_mm for p in bends],
                elapsed_seconds=time.monotonic() - started,
                proposals=len(trials),
                accepted_updates=len(accepted),
                proposal_outcomes=dict(Counter(t.status for t in trials)),
                stop_reason=reason,
            )
            (run / f"{name}-relaxed.json").write_text(json.dumps(snapshot(result), indent=2))
            (run / "result.json").write_text(json.dumps(output, indent=2))
            print(json.dumps(row), flush=True)
        output["status"] = "completed"
    except (
        ArithmeticError,
        KeyError,
        OSError,
        RuntimeError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as error:
        output.update(status="stopped", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        output.update(
            elapsed_seconds=time.monotonic() - batch_started,
            maximum_local_rss_native_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        )
        (run / "result.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
