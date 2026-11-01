"""
Freeze and compare one lightweight spline-guided construction on four examined layouts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import (
    CASES,
    ROOT,
    material_error,
    restore,
    snapshot,
)
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import Straight

from .guide import Guide, agreement
from .solve import solve


def main() -> None:
    """
    Pin all inputs and rules before solving; preserve failures without automatic renewal.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run = parser.parse_args().output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_bend_reduction").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_radius_allocation").glob("*.py"),
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/contracts.py",
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(ROOT / path for _, path in CASES),
        *(
            ROOT / f"artifacts/verification/ribbon_radius267/{name}-allocated.json"
            for name, _ in CASES
        ),
    }
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    plan = {
        "question": "Does a compact endpoint-tangent guide improve initial fold-direction choices before radius/travel allocation at low cost?",
        "method": "v1: single cubic Bezier/Hermite with both handles=chord/3;257point arc lookup;65ordered equal-arc stations. Two exact orientation roots x lateral mirror x departure-pair mirror, deduplicated. Up to24provisional bend rewrites/branch, largest reduction then guide RMS. Rank complete branches by RMS/direction/length/stable ID. Contact-check first four until separated. One existing bounded radius allocation, then retain only guide-RMS improvement with no length/fold regression versus267.",
        "cases": list(CASES),
        "coverage": "Four examined gym-created development configurations. Historical label calibration refers to202case4 Rubik gym N3/D1.5, not the retained non-gym N1 control. No new holdouts, case-specific settings, shortest-route or general reliability claim.",
        "fixed": "Ordered target positions/tangents/widths, conductor identity/order/profile, local equal material increments,99.6%pinch,no lateral bending and thick self-contact rejection. Gym geometry excluded from avoidance. No production/native-builder change.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "branches": 8,
            "provisional_rewrites_per_branch": 24,
            "branch_contact_attempts": 4,
            "radius_allocations": 1,
            "allocation_fractions": 8,
            "linear_supports": 2517,
            "contact_pairs": 20000,
            "contact_depth": 36,
            "rss_bytes": 4294967296,
            "native_attempts": 0,
        },
        "stop": "First source/resource/API/harness/false-acceptance stops remaining cases. No automatic retries/refinement/budget changes. Preserve all provisional geometry, contact failures, skipped branches and unattempted cases.",
        "prediction": "Unknown direction/length/contact/native outcomes. Guide unconstrained; guidance is branch selection, not a physical spline projection. Native validation separate.",
        "sources": hashes,
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in hashes:
        copied = run / "sources" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((ROOT / relative).read_bytes())
    started_batch = time.monotonic()
    output: dict[str, Any] = {
        "status": "running",
        "cases": [],
        "unattempted": [n for n, _ in CASES],
        "native_attempts": 0,
    }
    try:
        for name, relative in CASES:
            started = time.monotonic()

            def checkpoint(case_started: float = started) -> None:
                """
                Enforce frozen elapsed/RSS ceilings before scheduling more solver work.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - started_batch > 600
                ):
                    raise TimeoutError("Frozen spline-guide resource limit")

            def record(event: dict[str, Any], case_id: str = name) -> None:
                """
                Append every provisional/contact proposal to this complete case's ledger.
                """
                with (run / f"{case_id}-trials.jsonl").open("a") as stream:
                    stream.write(json.dumps(event) + "\n")

            checkpoint()
            for path, digest in hashes.items():
                if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Source drift: " + path)
            source = restore(json.loads((ROOT / relative).read_text()))
            baseline = restore(
                json.loads(
                    (
                        ROOT / f"artifacts/verification/ribbon_radius267/{name}-allocated.json"
                    ).read_text()
                )
            )
            row: dict[str, Any] = {
                "id": name,
                "status": "started",
                "baseline_length_mm": baseline.material_length_mm,
                "baseline_folds": fold_count(baseline),
            }
            output["cases"].append(row)
            output["unattempted"].remove(name)
            contact = inspect_contact(baseline, checkpoint=checkpoint)
            if contact.status != "separated":
                raise ArithmeticError("Latest baseline contact unaccepted")
            guide_started = time.monotonic()
            guide = Guide.create(source.targets)
            row["guide_creation_seconds"] = time.monotonic() - guide_started
            (run / f"{name}-guide.json").write_text(json.dumps(asdict(guide), indent=2))
            solve_started = time.monotonic()
            result, details = solve(source, baseline, guide, checkpoint, record)
            seconds = time.monotonic() - solve_started
            final_contact = inspect_contact(result, checkpoint=checkpoint)
            metric = material_error(result)
            if (
                final_contact.status != "separated"
                or cap_error(result) > 1e-7
                or metric > 1e-10
                or result.targets != baseline.targets
            ):
                raise ArithmeticError("Independent final guided-route checks failed")
            row.update(
                status="guided" if result is not baseline else "unchanged",
                final_length_mm=result.material_length_mm,
                final_folds=fold_count(result),
                gain_percent=100 * (1 - result.material_length_mm / baseline.material_length_mm),
                baseline_agreement=asdict(agreement(baseline, guide)),
                final_agreement=asdict(agreement(result, guide)),
                final_contact=asdict(final_contact),
                cap_error=cap_error(result),
                material_metric_error=metric,
                final_straight_mm=sum(
                    p.geometry.material_length_mm
                    for p in result.pieces
                    if isinstance(p.geometry, Straight)
                ),
                reduction_seconds=seconds,
                elapsed_seconds=time.monotonic() - started,
                branches=len(details["branches"]),
                contact_attempts=details["contact_attempts"],
                reason=details["reason"],
            )
            (run / f"{name}-details.json").write_text(json.dumps(details, indent=2))
            (run / f"{name}-guided.json").write_text(json.dumps(snapshot(result), indent=2))
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
            elapsed_seconds=time.monotonic() - started_batch,
            maximum_local_rss_native_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        )
        (run / "result.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
