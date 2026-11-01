"""
Freeze one curvature-focused aesthetic pass on four accepted joint-route configurations.
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
from pathlib import Path
from typing import Any

from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import ROOT, material_error, restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_joint_route.runner import NAMES

from .model import curvature_score, peak_curvature
from .solve import ease


def main() -> None:
    """
    Preserve fixed inputs and every proposal under one declared length and resource policy.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--length-growth", type=float, default=0.05)
    args = parser.parse_args()
    if not 0 <= args.length_growth <= 0.1:
        raise ValueError("Declare at most10%aesthetic length growth.")
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_joint_route").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        ROOT / "experiments/experiment_ribbon_bend_reduction/closure.py",
        ROOT / "experiments/experiment_ribbon_bend_reduction/rewrite.py",
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/contracts.py",
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "tests/test_ribbon_aesthetic.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        ROOT / "artifacts/verification/ribbon_joint285/plan.json",
        ROOT / "artifacts/verification/ribbon_joint285/result.json",
        *(ROOT / f"artifacts/verification/ribbon_joint285/{n}-joint.json" for n in NAMES),
    }
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    plan = {
        "question": "Can an aesthetic curvature objective soften tight first-pass folds with at most the declared small material-length increase?",
        "cases": NAMES,
        "coverage": "Same four examined gym development configurations from285; no new holdouts or general reliability claim.",
        "method": "v1: fixed angles/banks/leads; all straight slots and radius redistribution. Minimize exact D*integral(lane curvature squared ds). Project gradient onto3affine endpoint-position equations and active nonnegative/material-length bounds. Endpoint orientation is invariant. Original physical radius floor and original peak lane curvature retained. Up to8iterations,6halvings and8totalcontactproposals;<=0.5Dcoordinatechange periteration. No randomness, endpoint rediscovery, guide attraction or native repair.",
        "length_growth_fraction": args.length_growth,
        "fixed": "Both ordered cap frames, conductor identity/profile/order, equal local material increments,99.6%pinch,no lateral bending, thick self-contact rejection. Gym geometry excluded from avoidance; native constructor unchanged. G1flat/arc joins retain curvature jumps; no G2claim.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "rss_bytes": 4294967296,
            "iterations": 8,
            "halvings": 6,
            "contact_proposals": 8,
            "contact_pairs": 20000,
            "contact_depth": 36,
            "native_attempts": 0,
        },
        "numeric_bounds": "Existing affine rank1e-10/consistency1e-8; activebound1e-10; objective decrease>1e-9; full ordered caps1e-7; length arithmetic uncertainty1e-8D; peak-curvature arithmetic uncertainty1e-10/D. No physical rule relaxed.",
        "prediction": "Unknown aesthetic improvement/contact/native outcomes. Smaller integrated curvature may not remove every visible crease; no optimum or elastic equilibrium claim.",
        "stop": "First resource/source/API/harness/falseacceptance stops remaining cases. Preserve all unsuccessful/unattempted cases and contact proposals. No in-flight budget/tolerance change or automatic refinement.",
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
        "unattempted": list(NAMES),
        "native_attempts": 0,
    }
    try:
        for name in NAMES:
            started = time.monotonic()
            counts: Counter[str] = Counter()

            def checkpoint(case_started: float = started) -> None:
                """
                Bound candidate/contact scheduling by frozen elapsed time and local peak RSS.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - batch_started > 600
                ):
                    raise TimeoutError("Frozen aesthetic resource limit")

            def record(
                event: dict[str, Any], case_id: str = name, ledger: Counter[str] = counts
            ) -> None:
                """
                Preserve every complete proposal, including unresolved thick contact.
                """
                ledger[event["status"]] += 1
                with (run / f"{case_id}-trials.jsonl").open("a") as stream:
                    stream.write(json.dumps(event) + "\n")

            checkpoint()
            for relative, expected in hashes.items():
                if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
                    raise RuntimeError("Source drift: " + relative)
            source = restore(
                json.loads(
                    (ROOT / f"artifacts/verification/ribbon_joint285/{name}-joint.json").read_text()
                )
            )
            row: dict[str, Any] = {
                "id": name,
                "status": "started",
                "baseline_length_mm": source.material_length_mm,
                "baseline_folds": fold_count(source),
                "baseline_curvature_score": curvature_score(source),
                "baseline_peak_curvature": peak_curvature(source),
            }
            output["cases"].append(row)
            output["unattempted"].remove(name)
            if inspect_contact(source, checkpoint=checkpoint).status != "separated":
                raise ArithmeticError("Accepted joint baseline lost contact certificate")
            pass_started = time.monotonic()
            result, reason = ease(source, args.length_growth, checkpoint, record)
            pass_seconds = time.monotonic() - pass_started
            contact = inspect_contact(result, checkpoint=checkpoint)
            metric = material_error(result)
            if (
                contact.status != "separated"
                or cap_error(result) > 1e-7
                or metric > 1e-10
                or result.targets != source.targets
                or fold_count(result) != fold_count(source)
                or result.material_length_mm
                > source.material_length_mm * (1 + args.length_growth)
                + 1e-8 * source.targets.diameter_mm
            ):
                raise ArithmeticError("Independent final aesthetic audit failed")
            row.update(
                status="eased" if result is not source else "unchanged",
                final_length_mm=result.material_length_mm,
                length_growth_percent=100
                * (result.material_length_mm / source.material_length_mm - 1),
                final_curvature_score=curvature_score(result),
                curvature_score_reduction_percent=100
                * (1 - curvature_score(result) / curvature_score(source)),
                final_peak_curvature=peak_curvature(result),
                final_folds=fold_count(result),
                cap_error=cap_error(result),
                material_metric_error=metric,
                final_contact=asdict(contact),
                reduction_seconds=pass_seconds,
                elapsed_seconds=time.monotonic() - started,
                proposals=dict(counts),
                stop_reason=reason,
            )
            (run / f"{name}-eased.json").write_text(json.dumps(snapshot(result), indent=2))
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
