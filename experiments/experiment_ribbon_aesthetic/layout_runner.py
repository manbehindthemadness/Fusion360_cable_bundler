"""
Compare layout-relative fold relaxation and compatible turn merging on four frozen layouts.
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

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import ROOT, material_error, restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_joint_route.runner import NAMES

from .layout_model import surface_score
from .layout_solve import ease
from .merge import merge
from .model import curvature_score, peak_curvature


def main() -> None:
    """
    Pin one common procedure, preserving liked prior results and every unsuccessful proposal.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run = parser.parse_args().output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_relaxation").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_bend_reduction").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        ROOT / "experiments/experiment_ribbon_joint_route/runner.py",
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/contracts.py",
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "tests/test_ribbon_aesthetic.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(ROOT / f"artifacts/verification/ribbon_aesthetic296/{n}-eased.json" for n in NAMES),
        *(ROOT / f"artifacts/verification/ribbon_joint285/{n}-joint.json" for n in NAMES),
    }
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    plan = {
        "question": "Can layouts use their straightaways as runway for scale-relative full-fold easing, and can compatible consecutive turns merge without losing material/cap/contact correctness?",
        "renewal": "304retained after all four configurations were examined. Read-only trial diagnosis found retraction-created microscopic straight slots causing unresolved near-contact at nonadjacent folds. This comparison keeps predicted zero-runway slots exactly on their active face during Newton reclosure; same inputs, physical gates and budgets. No contact bypass, interval-budget increase or new geometry cases.",
        "cases": NAMES,
        "coverage": "Same4examined gym development layouts. Start from liked296/302results; preserve prior bodies. No holdouts or general success claim.",
        "method": "v2: lengths normalized by each immutable initial material length. Full cylindrical curvature integral, not lane-only curvature. Relax signed fold angles, banks, radii and every nonnegative straight slot. No reserved straight runs. Project descent onto six cap equations and active length bound; bounded Newton retraction. At most5%layout-length linear change and0.2rad angular change per iteration. Compatible same-bank/same-sign consecutive turn groups may merge with angle-weighted radii; complete affine reclosure and contact required. Merge once before and once after relaxation.",
        "fixed": "Original285ordered targets/profile/identities/order; local equal material increments,99.6%pinch,no lateral bending and thick joined-profile contact rejection. Peak lane curvature may not worsen from296. Original285length*1.05 ceiling is not compounded. No native builder/profile/appearance/production change; G1curvature jumps remain.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "rss_bytes": 4294967296,
            "relax_iterations": 8,
            "relax_halvings": 6,
            "newton_corrections": 6,
            "newton_halvings": 4,
            "relax_contact_proposals": 8,
            "merge_calls": 2,
            "merge_passes_per_call": 2,
            "merge_proposals_per_call": 12,
            "merge_contact_proposals_per_call": 4,
            "contact_pairs": 20000,
            "contact_depth": 36,
            "native_attempts": 0,
        },
        "numerical_bounds": "Retain affine rank1e-10/consistency1e-8, finite difference1e-5, normalized retraction1e-10, complete ordered caps1e-7, length uncertainty1e-8D, objective gain1e-9, numerical zero1e-12mm. Fold sign preserved with1e-6rad numerical angle floor; bank regularity1e-3rad from right angle. No physical tolerance relaxation.",
        "prediction": "Unknown progress, merger and native outcomes. Shared bank/sign compatibility is necessary for the implemented exact merge, not a characterization of all possible global bend simplifications.",
        "stop": "First source/resource/API/harness/falseacceptance stops remaining work. Preserve every unattempted/unsuccessful configuration and proposal. No in-flight tuning or automatic extra iterations.",
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
                Bound mathematical proposals and thick-contact scheduling before native work.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - batch_started > 600
                ):
                    raise TimeoutError("Frozen layout-easing resource limit")

            def record(
                event: dict[str, Any], case_id: str = name, ledger: Counter[str] = counts
            ) -> None:
                """
                Record relaxation and merging outcomes as distinct stages on the same case.
                """
                kind = "merge" if "rewrite" in event else "relax"
                ledger[kind + "_" + event["status"]] += 1
                with (run / f"{case_id}-trials.jsonl").open("a") as stream:
                    stream.write(json.dumps({"kind": kind, **event}) + "\n")

            checkpoint()
            for relative, expected in hashes.items():
                if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
                    raise RuntimeError("Source drift: " + relative)
            source = restore(
                json.loads(
                    (
                        ROOT / f"artifacts/verification/ribbon_aesthetic296/{name}-eased.json"
                    ).read_text()
                )
            )
            original = restore(
                json.loads(
                    (ROOT / f"artifacts/verification/ribbon_joint285/{name}-joint.json").read_text()
                )
            )
            maximum_length = original.material_length_mm * 1.05
            row: dict[str, Any] = {
                "id": name,
                "status": "started",
                "baseline_length_mm": source.material_length_mm,
                "baseline_folds": fold_count(source),
                "baseline_surface_score": surface_score(source, source.material_length_mm),
                "baseline_peak_curvature": peak_curvature(source),
            }
            output["cases"].append(row)
            output["unattempted"].remove(name)
            if (
                source.targets != original.targets
                or inspect_contact(source, checkpoint=checkpoint).status != "separated"
            ):
                raise ArithmeticError("Frozen aesthetic baseline is not accepted")
            pass_started = time.monotonic()
            merged, before_reason = merge(source, maximum_length, checkpoint, record)
            relaxed, reason = ease(merged, maximum_length, checkpoint, record)
            final, after_reason = merge(relaxed, maximum_length, checkpoint, record)
            seconds = time.monotonic() - pass_started
            contact = inspect_contact(final, checkpoint=checkpoint)
            metric = material_error(final)
            if (
                contact.status != "separated"
                or cap_error(final) > 1e-7
                or metric > 1e-10
                or final.targets != source.targets
                or fold_count(final) > fold_count(source)
                or final.material_length_mm > maximum_length + 1e-8 * source.targets.diameter_mm
                or peak_curvature(final)
                > peak_curvature(source) + 1e-10 / source.targets.diameter_mm
                or surface_score(final, source.material_length_mm)
                > surface_score(source, source.material_length_mm) + 1e-9
            ):
                raise ArithmeticError("Independent final layout-easing audit failed")
            row.update(
                status="eased" if final is not source else "unchanged",
                final_length_mm=final.material_length_mm,
                final_folds=fold_count(final),
                final_surface_score=surface_score(final, source.material_length_mm),
                surface_score_reduction_percent=100
                * (
                    1
                    - surface_score(final, source.material_length_mm)
                    / surface_score(source, source.material_length_mm)
                ),
                final_peak_curvature=peak_curvature(final),
                final_lane_score=curvature_score(final),
                final_contact=asdict(contact),
                cap_error=cap_error(final),
                material_metric_error=metric,
                reduction_seconds=seconds,
                elapsed_seconds=time.monotonic() - started,
                stop_reason=reason,
                merge_before_reason=before_reason,
                merge_after_reason=after_reason,
                outcomes=dict(counts),
                final_radii_mm=[
                    p.geometry.radius_mm
                    for p in final.pieces
                    if isinstance(p.geometry, CylindricalFold)
                ],
                final_straight_mm=sum(
                    p.geometry.material_length_mm
                    for p in final.pieces
                    if isinstance(p.geometry, Straight)
                ),
                original_first_pass_length_mm=original.material_length_mm,
                growth_from_first_pass_percent=100
                * (final.material_length_mm / original.material_length_mm - 1),
            )
            (run / f"{name}-eased.json").write_text(json.dumps(snapshot(final), indent=2))
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
