"""
Freeze and run four bounded numerical contraction cases; requires only project SDK.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

from cable_bundler.routing.geometry import Vector3, dot, magnitude
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight

from .contract import Trial, cap_error, contract

ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ("calibration", "artifacts/verification/ribbon_sweep202/case-4.json"),
    *((f"gym-{i}", f"artifacts/verification/ribbon_fidelity216/case-{i}.json") for i in (1, 2, 3)),
)


def restore(payload: dict[str, Any]) -> FoldRoute:
    """
    Restore an existing frozen route without invoking an endpoint solver.
    """
    radius = payload.get("radius_mm", payload.get("policy_radius_mm"))
    if radius is None:
        raise ValueError("Frozen route lacks its declared construction radius.")
    targets = Targets(
        **{
            key: Vector3(**value) if isinstance(value, dict) else value
            for key, value in payload["case"].items()
        }
    )
    pieces = tuple(
        PlacedPiece(
            Pose(**{key: Vector3(**value) for key, value in piece["pose"].items()}),
            Straight(**piece["geometry"])
            if piece["kind"] == "straight"
            else CylindricalFold(**piece["geometry"]),
            piece["label"],
        )
        for piece in payload["pieces"]
    )
    return FoldRoute(targets, pieces, radius)


def snapshot(route: FoldRoute) -> dict[str, Any]:
    """
    Retain exact geometry and ordered poses in the existing frozen-route format.
    """
    return {
        "case": asdict(route.targets),
        "radius_mm": route.radius_mm,
        "material_length_mm": route.material_length_mm,
        "pieces": [
            {
                **asdict(piece),
                "kind": "straight" if isinstance(piece.geometry, Straight) else "fold",
            }
            for piece in route.pieces
        ],
    }


def material_error(route: FoldRoute) -> float:
    """
    Sample local metric and no-lateral-bend identities independently of shortening.
    """
    errors = []
    for piece in route.pieces:
        length = piece.geometry.material_length_mm
        for q in (-route.half_width_mm, 0.0, route.half_width_mm):
            for u in (0.0, 0.13, 0.41, 0.79, 1.0):
                _, velocity, across, acceleration = piece.surface(u, q)
                errors.extend(
                    (
                        abs(magnitude(velocity) / length - 1),
                        abs(magnitude(across) - 1),
                        abs(dot(velocity, across)) / length,
                        abs(dot(acceleration, across)) / length**2,
                    )
                )
    return max(errors)


def _record_trial(trial: Trial, *, entries: list[Trial], path: Path) -> None:
    """
    Append every proposal to its explicitly bound case ledger.
    """
    entries.append(trial)
    with path.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "iteration": trial.iteration,
                    "backtrack": trial.backtrack,
                    "accepted": trial.accepted,
                    "gain_mm": trial.gain_mm,
                    "contact": asdict(trial.contact),
                    "route": snapshot(trial.route),
                }
            )
            + "\n"
        )


def main() -> None:
    """
    Pin before execution, retain every contact trial and stop on any harness error.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts" / "verification")
    run.mkdir(parents=True, exist_ok=False)
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/contracts.py",
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(ROOT / path for _, path in CASES),
    }
    hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    plan = {
        "question": "Can endpoint-nullspace straight contraction reliably reduce existing material length without changing folds or accepting contact?",
        "method": "v1: project negative length gradient into straight-direction nullspace; largest nonnegative step then bounded halving; immutable fold geometry and topology",
        "prior_setup_failure": "ribbon_contract257 stopped before any case evaluation: calibration archive stores policy_radius_mm rather than radius_mm. Restore now accepts either explicit declared field; no numerical rule or budget changed.",
        "cases": list(CASES),
        "coverage": "4 examined gym-created development configurations; no holdout or generalized geometry claim",
        "degrees_of_freedom": "Straight lengths only; no fold reversal/angle/radius/bank/lead changes, target movement, native edits or seed discovery",
        "acceptance": "Strict shorter common material length, original ordered caps within existing1e-7 check, unchanged material folds and pinch; full thick contact reports separated",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "maximum_iterations": 4,
            "backtracks_per_iteration": 8,
            "contact_checks_per_case": 34,
            "rss_bytes": 4294967296,
            "native_attempts": 0,
            "new_endpoint_solves": 0,
        },
        "numeric_bound": "Positive1e-7D straight floor; row rank tolerance1e-10; neither is a physical routing minimum",
        "stop": "First source/resource/harness error or false acceptance stops the batch; preserve rejected contact proposals and all unattempted cases. No automatic budget renewal.",
        "remaining_limits": "Fixed topology may block useful contractions; no global/local nonlinear optimum, continuous exact arithmetic or native compliance claim",
        "sources": hashes,
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in hashes:
        copy = run / "sources" / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes((ROOT / relative).read_bytes())
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
                Bound wall time and peak local RSS throughout contact subdivision.
                """
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss_bytes = peak if sys.platform == "darwin" else peak * 1024
                if (
                    rss_bytes >= 4294967296
                    or time.monotonic() - case_started > 120
                    or time.monotonic() - batch_started > 600
                ):
                    raise TimeoutError("Frozen resource budget reached")

            for source, digest in hashes.items():
                if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Frozen source changed: " + source)
            checkpoint()
            route = restore(json.loads((ROOT / relative).read_text()))
            baseline = inspect_contact(route, checkpoint=checkpoint)
            baseline_seconds = time.monotonic() - started
            row: dict[str, Any] = {
                "id": name,
                "baseline_length_mm": route.material_length_mm,
                "baseline_contact": asdict(baseline),
                "baseline_seconds": baseline_seconds,
            }
            output["cases"].append(row)
            output["unattempted"].remove(name)
            trials: list[Trial] = []

            record = partial(_record_trial, entries=trials, path=run / f"{name}-trials.jsonl")

            if baseline.status != "separated":
                row["status"] = "baseline_contact_unaccepted"
                continue
            contraction_started = time.monotonic()
            result, reason = contract(route, checkpoint=checkpoint, record=record)
            contraction_seconds = time.monotonic() - contraction_started
            final_contact = inspect_contact(result, checkpoint=checkpoint)
            metric_error = material_error(result)
            if (
                final_contact.status != "separated"
                or cap_error(result) > 1e-7
                or metric_error > 1e-10
                or result.material_length_mm > route.material_length_mm
            ):
                raise ArithmeticError("Final independent numerical audit failed")
            original_folds = tuple(
                p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold)
            )
            final_folds = tuple(
                p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)
            )
            if original_folds != final_folds or result.targets != route.targets:
                raise ArithmeticError("Immutable fold/target contract changed")
            row.update(
                status="shortened"
                if result.material_length_mm < route.material_length_mm
                else "unchanged",
                final_length_mm=result.material_length_mm,
                gain_mm=route.material_length_mm - result.material_length_mm,
                gain_percent=100 * (1 - result.material_length_mm / route.material_length_mm),
                cap_error=cap_error(result),
                material_metric_error=metric_error,
                final_contact=asdict(final_contact),
                contraction_seconds=contraction_seconds,
                elapsed_seconds=time.monotonic() - started,
                trials=len(trials),
                accepted_updates=sum(t.accepted for t in trials),
                stop_reason=reason,
                folds_unchanged=len(final_folds),
            )
            (run / f"{name}-contracted.json").write_text(json.dumps(snapshot(result), indent=2))
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
        output["elapsed_seconds"] = time.monotonic() - batch_started
        output["maximum_local_rss_native_units"] = resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss
        (run / "result.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
