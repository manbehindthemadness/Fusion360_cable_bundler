"""
Freeze a four-layout comparison of joint first-pass position and orientation construction.
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

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import ROOT, material_error, restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_spline_guide.guide import Guide, agreement

from .solve import solve

NAMES = ("calibration", "gym-1", "gym-2", "gym-3")


def main() -> None:
    """
    Pin inputs, rules and finite support/contact bounds before any new route construction.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run = parser.parse_args().output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        ROOT / "experiments/experiment_ribbon_bend_reduction/closure.py",
        ROOT / "experiments/experiment_ribbon_bend_reduction/rewrite.py",
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        ROOT / "experiments/experiment_ribbon_spline_guide/guide.py",
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/contracts.py",
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "tests/test_ribbon_joint_route.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(
            ROOT / f"artifacts/verification/ribbon_guide270/{n}-{suffix}.json"
            for n in NAMES
            for suffix in ("guided", "guide")
        ),
    }
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    plan = {
        "question": "Does solving travel/radius and distributed orientation together remove the serial entry-frame-reset/backtrack/arrival-last bias in the first pass?",
        "method": "v1: exact direct endpoint rotation roots plus two-stage roots through one guide-middle orientation. Guide tangent at1/2; projected mean endpoint width with covariant degeneracy fallback. No fixed midpoint position. Up to6topologies/6folds. Joint diameter-normalized nonnegative travel and radius growth closes3position equations before construction. Enumerate supports0..3, at most378/topology. Rank closed nonregressing candidates by material length, then ordered guide RMS/fold count/stable ID. Full contact on at most12shortest candidates until first separated. No serial translation modules, envelope gaps, entry resets, signed-distance U-turns, bend-reduction/radius post-pass or attraction.",
        "cases": NAMES,
        "coverage": "Four examined gym development configurations: historical calibration label=N3/D1.5 from202case4; gym1N1/D.75,gym2N3/D1.5,gym3N6/D3. No holdouts or generalized success claim.",
        "baseline": "Last successful270plans/271and268bodies; old route used only for target/profile/declared radius and comparison limits. No reuse of old folds/straight lengths as solver initialization.",
        "fixed": "Ordered caps, conductor/profile identity, local equal material increments,99.6%pinch, no lateral bending and thick self-contact rejection. Gym geometry excluded from avoidance. Preserve native builder and tolerance gates; no production edits.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "topologies": 6,
            "folds_per_topology": 6,
            "linear_supports_per_topology": 378,
            "contact_attempts_per_case": 12,
            "contact_pairs": 20000,
            "contact_depth": 36,
            "rss_bytes": 4294967296,
            "native_attempts": 0,
        },
        "numeric_bounds": "Affine rank1e-10/equation residual1e-8, negative uncertainty1e-9, coordinate dedup1e-10, omitted straight<=1e-10D; independent ordered cap1e-7; comparison length uncertainty1e-8D. No physical rule changed.",
        "stop": "First source/resource/API/harness/falseacceptance stops remaining work. All closed/infeasible support outcomes, skipped/rejected candidates and unattempted cases retained. No automatic refinement/budget enlargement.",
        "prediction": "Algebraic cap closure expected where the nonnegative cone supports the target. Contact/native success unknown; finite family failure is not physical infeasibility. Guide itself unconstrained.",
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
        "unattempted": list(NAMES),
        "native_attempts": 0,
    }
    try:
        for name in NAMES:
            started = time.monotonic()
            counts: Counter[str] = Counter()

            def checkpoint(case_started: float = started) -> None:
                """
                Enforce frozen wall time and sampled memory before more candidate work.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - started_batch > 600
                ):
                    raise TimeoutError("Frozen joint first-pass resource limit")

            def record(
                event: dict[str, Any], case_id: str = name, ledger: Counter[str] = counts
            ) -> None:
                """
                Retain every finite algebraic support and complete contact proposal.
                """
                stage = event["stage"]
                ledger[stage] += 1
                if "status" in event:
                    ledger[stage + "_" + event["status"]] += 1
                with (run / f"{case_id}-trials.jsonl").open("a") as stream:
                    stream.write(json.dumps(event) + "\n")

            checkpoint()
            for relative, digest in hashes.items():
                if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Source drift: " + relative)
            source = restore(
                json.loads(
                    (
                        ROOT / f"artifacts/verification/ribbon_guide270/{name}-guided.json"
                    ).read_text()
                )
            )
            payload = json.loads(
                (ROOT / f"artifacts/verification/ribbon_guide270/{name}-guide.json").read_text()
            )
            guide = Guide(
                tuple(Vector3(**p) for p in payload["controls"]),
                tuple(payload["parameters"]),
                tuple(payload["distances"]),
            )
            row: dict[str, Any] = {
                "id": name,
                "status": "started",
                "baseline_length_mm": source.material_length_mm,
                "baseline_folds": fold_count(source),
                "baseline_agreement": asdict(agreement(source, guide)),
            }
            output["cases"].append(row)
            output["unattempted"].remove(name)
            if inspect_contact(source, checkpoint=checkpoint).status != "separated":
                raise ArithmeticError("Last successful baseline contact unaccepted")
            pass_started = time.monotonic()
            result, details = solve(source, guide, checkpoint, record)
            seconds = time.monotonic() - pass_started
            contact = inspect_contact(result, checkpoint=checkpoint)
            metric = material_error(result)
            if (
                contact.status != "separated"
                or cap_error(result) > 1e-7
                or metric > 1e-10
                or result.targets != source.targets
                or result.material_length_mm
                > source.material_length_mm + 1e-8 * source.targets.diameter_mm
            ):
                raise ArithmeticError("Independent joint construction checks failed")
            row.update(
                status="joint" if details["selected"] else "unchanged",
                final_length_mm=result.material_length_mm,
                final_folds=fold_count(result),
                final_agreement=asdict(agreement(result, guide)),
                final_contact=asdict(contact),
                final_straight_mm=sum(
                    p.geometry.material_length_mm
                    for p in result.pieces
                    if isinstance(p.geometry, Straight)
                ),
                gain_percent=100 * (1 - result.material_length_mm / source.material_length_mm),
                cap_error=cap_error(result),
                material_metric_error=metric,
                reduction_seconds=seconds,
                elapsed_seconds=time.monotonic() - started,
                selected=details["selected"],
                stop_reason=details["stop_reason"],
                events=dict(counts),
            )
            (run / f"{name}-joint.json").write_text(json.dumps(snapshot(result), indent=2))
            (run / f"{name}-details.json").write_text(json.dumps(details, indent=2))
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
