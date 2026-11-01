"""
Freeze and evaluate one bounded linear radius/travel rule on four existing layouts.
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

from .model import Model
from .solve import Trial, solve

CASES = tuple(
    (name, f"artifacts/verification/ribbon_bends263/{name}-reduced.json")
    for name in ("calibration", "gym-1", "gym-2", "gym-3")
)


def _record(trial: Trial, *, entries: list[Trial], path: Path) -> None:
    """
    Preserve every contact-tested allocation before advancing to another fraction.
    """
    entries.append(trial)
    with path.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "fraction": trial.fraction,
                    "values": trial.values,
                    "contact": asdict(trial.contact),
                    "route": snapshot(trial.route),
                }
            )
            + "\n"
        )


def main() -> None:
    """
    Pin the rule/input/budgets, then compare four cases without result-driven tuning.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-directory", type=Path)
    parser.add_argument("--input-suffix", default="reduced")
    args = parser.parse_args()
    cases = CASES
    if args.input_directory is not None:
        directory = args.input_directory.resolve()
        directory.relative_to(ROOT / "artifacts/verification")
        if args.input_suffix not in {"reduced", "joint"}:
            raise ValueError("Unsupported frozen material-route suffix")
        cases = tuple(
            (name, str((directory / f"{name}-{args.input_suffix}.json").relative_to(ROOT)))
            for name, _ in CASES
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
        "question": "Can one joint radius/travel allocation soften the recorded input folds while preserving material length and full target poses?",
        "method": "v1: fixed fold angles/banks/leads; nonnegative explicit straight lengths and radius growth above each original radius. Lexicographic LP minimizes straight travel, then total material length, under three positional equations and original total-length budget. Enumerate supports0..4, then test full allocation or seven dyadic fractions if contact is unaccepted.",
        "cases": list(cases),
        "coverage": "Four examined gym-created development configurations from the recorded input paths. No holdout, no specimen-specific settings and no global physical optimum claim.",
        "fixed": "Both ordered caps, conductor identities/profile, equal local material increments,99.6%pinch,no lateral bending. No radius may tighten below its existing value; angles and crease directions unchanged. Explicit straight controls remain straight.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "allocation_variables": 15,
            "linear_supports_maximum": 2517,
            "contact_fractions": 8,
            "contact_pairs": 20000,
            "contact_depth": 36,
            "rss_bytes": 4294967296,
            "native_attempts": 0,
        },
        "numeric_bounds": "Affine rank1e-10/equation residual1e-8; nonnegative uncertainty1e-9; objective tie rounding1e-10; omitted straight<=1e-10D; independent complete ordered cap guard1e-7; material budget uncertainty1e-8D; straight gain must exceed1e-8D.",
        "stop": "First source/resource/harness/falseacceptance stops batch. Preserve LP solution, every contact proposal and unattempted cases. Unresolved contact never passes. No automatic fitting, refinement or budget renewal.",
        "prediction": "Unknown radius/travel/contact/native outcomes; algebraic endpoint closure is not a volume-contact or native-build guarantee.",
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
                Bound cold linear enumeration and full contact work by time and RSS.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - batch_started > 600
                ):
                    raise TimeoutError("Frozen radius-allocation resource limit")

            checkpoint()
            for source, digest in hashes.items():
                if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Source drift: " + source)
            route = restore(json.loads((ROOT / relative).read_text()))
            model = Model(route)
            baseline = inspect_contact(route, checkpoint=checkpoint)
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
            allocation_started = time.monotonic()
            result, optimum, fraction, reason = solve(route, checkpoint=checkpoint, record=record)
            seconds = time.monotonic() - allocation_started
            if optimum is not None:
                (run / f"{name}-linear.json").write_text(json.dumps(asdict(optimum), indent=2))
            final_contact = inspect_contact(result, checkpoint=checkpoint)
            metric = material_error(result)
            original_folds = [
                p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold)
            ]
            result_folds = [
                p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)
            ]
            if len(original_folds) != len(result_folds) or any(
                b.radius_mm < a.radius_mm
                or (a.angle_radians, a.bank_radians, a.width_mm, a.before_mm, a.after_mm)
                != (b.angle_radians, b.bank_radians, b.width_mm, b.before_mm, b.after_mm)
                for a, b in zip(original_folds, result_folds)
            ):
                raise ArithmeticError("Radius allocation changed fixed fold geometry.")
            if (
                final_contact.status != "separated"
                or cap_error(result) > 1e-7
                or metric > 1e-10
                or result.targets != route.targets
                or result.material_length_mm
                > route.material_length_mm + 1e-8 * route.targets.diameter_mm
            ):
                raise ArithmeticError("Independent final radius-allocation audit failed")
            final_values = trials[-1].values if fraction else model.initial
            row.update(
                status="allocated" if fraction else "unchanged",
                final_length_mm=result.material_length_mm,
                gain_percent=100 * (1 - result.material_length_mm / route.material_length_mm),
                final_straight_mm=model.straight_length(final_values),
                straight_reduction_percent=100
                * (1 - model.straight_length(final_values) / row["baseline_straight_mm"])
                if row["baseline_straight_mm"]
                else 0,
                final_folds=fold_count(result),
                radii_before_mm=[p.radius_mm for p in original_folds],
                radii_after_mm=[p.radius_mm for p in result_folds],
                maximum_radius_factor=max(
                    (b.radius_mm / a.radius_mm for a, b in zip(original_folds, result_folds)),
                    default=1,
                ),
                fraction=fraction,
                cap_error=cap_error(result),
                material_metric_error=metric,
                final_contact=asdict(final_contact),
                reduction_seconds=seconds,
                elapsed_seconds=time.monotonic() - started,
                contact_proposals=len(trials),
                proposal_outcomes=dict(Counter(t.contact.status for t in trials)),
                linear_supports=optimum.bases_evaluated if optimum else 0,
                linear_feasible_supports=optimum.feasible_bases if optimum else 0,
                stop_reason=reason,
            )
            (run / f"{name}-allocated.json").write_text(json.dumps(snapshot(result), indent=2))
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
