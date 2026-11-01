"""
Freeze and evaluate four existing gym routes with one bounded bend-reduction rule.
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
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import (
    CASES,
    ROOT,
    material_error,
    restore,
    snapshot,
)
from experiments.experiment_ribbon_fold_route.contact import inspect_contact

from .reduce import Trial, reduce_bends
from .rewrite import fold_count


def _record(trial: Trial, *, entries: list[Trial], path: Path) -> None:
    """
    Preserve each structural proposal before further work, including failed closure.
    """
    entries.append(trial)
    with path.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "rewrite": asdict(trial.rewrite),
                    "accepted": trial.accepted,
                    "contact": asdict(trial.contact) if trial.contact else None,
                    "route": snapshot(trial.route) if trial.route else None,
                }
            )
            + "\n"
        )


def main() -> None:
    """
    Start from original pre-contraction routes, retain all cases and stop on errors.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/contracts.py",
        ROOT / "devtools/ribbon_analysis/pinch.py",
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(ROOT / path for _, path in CASES),
    }
    hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    plan = {
        "question": "Can an algebraic common-crease bend rewrite reduce unnecessary fold features before straight optimization?",
        "method": "v1: combine2+consecutive equal-bank/radius/width bends to their principal net crease turn; cancelling groups become a flat connector. Reclose all straight lengths by exact nonnegative least-change projection. Greedy largest bend reduction first, then route order; no length ranking.",
        "cases": list(CASES),
        "baseline": "Original frozen pre-contraction routes, not258shortenedvariants. Four examined development configurations; no holdout or universal minimal-bend claim.",
        "degrees_of_freedom": "Rewrite compatible bend groups, replace internal straight runs, reclose outside straights. Radius/bank/profile unchanged; fixed ordered endpoints, equal material increments,99.6%pinch,no lateral bending and full thick self-contact. No external landmarks/winding input exists in these four targets; no user-prescribed winding may be discarded.",
        "acceptance": "Strictly fewer bends; final cap error<=existing1e-7; sampled metric<=1e-10; unchanged dimensions/identities; full thick contact separated. Length change recorded, not used to select or reject structural improvements.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "passes": 3,
            "proposals_per_case": 24,
            "closure_slots": 10,
            "active_sets_per_projection": 1024,
            "contact_pairs": 20000,
            "contact_depth": 36,
            "rss_bytes": 4294967296,
            "native_attempts": 0,
        },
        "numeric_bounds": "row rank1e-10, positional equation residual1e-8, negative length uncertainty1e-9; zero slots<=1e-10omitted and independent cap guard still applies",
        "stop": "First source/resource/harness/falseacceptance stops batch. Expected infeasible closures, penetrating and unresolved proposals retain previous valid route. Preserve every outcome, no automatic refinement or budget renewal.",
        "prediction": "Unknown reduction/contact outcomes on all four cases; a valid numerical rewrite is not a native-build prediction or global-optimum certificate.",
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
        "unattempted": [name for name, _ in CASES],
        "native_attempts": 0,
    }
    try:
        for name, relative in CASES:
            started = time.monotonic()

            def checkpoint(case_started: float = started) -> None:
                """
                Bound all closure/contact work by frozen wall time and local peak RSS.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - batch_started > 600
                ):
                    raise TimeoutError("Frozen bend-reduction resource limit")

            checkpoint()
            for source, digest in hashes.items():
                if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Source drift: " + source)
            route = restore(json.loads((ROOT / relative).read_text()))
            baseline = inspect_contact(route, checkpoint=checkpoint)
            row: dict[str, Any] = {
                "id": name,
                "baseline_folds": fold_count(route),
                "baseline_length_mm": route.material_length_mm,
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
            reduction_started = time.monotonic()
            candidate, reason = reduce_bends(route, checkpoint=checkpoint, record=record)
            reduction_seconds = time.monotonic() - reduction_started
            final_contact = inspect_contact(candidate, checkpoint=checkpoint)
            errors = material_error(candidate)
            bends = [
                p.geometry for p in candidate.pieces if isinstance(p.geometry, CylindricalFold)
            ]
            utilization = max(
                (candidate.targets.diameter_mm / 2 / g.radius_mm for g in bends), default=0
            )
            if (
                cap_error(candidate) > 1e-7
                or errors > 1e-10
                or utilization > 0.996
                or candidate.targets != route.targets
                or final_contact.status != "separated"
                or fold_count(candidate) > fold_count(route)
            ):
                raise ArithmeticError("Independent final bend-reduction audit failed")
            row.update(
                status="reduced" if fold_count(candidate) < fold_count(route) else "unchanged",
                final_folds=fold_count(candidate),
                final_length_mm=candidate.material_length_mm,
                length_change_percent=100
                * (candidate.material_length_mm / route.material_length_mm - 1),
                cap_error=cap_error(candidate),
                material_metric_error=errors,
                pinch_fraction=utilization,
                final_contact=asdict(final_contact),
                reduction_seconds=reduction_seconds,
                elapsed_seconds=time.monotonic() - started,
                proposals=len(trials),
                accepted_rewrites=sum(t.accepted for t in trials),
                proposal_outcomes=dict(
                    Counter(t.contact.status if t.contact else "infeasible_closure" for t in trials)
                ),
                stop_reason=reason,
            )
            (run / f"{name}-reduced.json").write_text(json.dumps(snapshot(candidate), indent=2))
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
