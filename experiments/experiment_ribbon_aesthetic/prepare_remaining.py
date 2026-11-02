"""
Freeze a continuation disposition after one native fidelity rejection, without changing routes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from experiments.experiment_ribbon_contraction.runner import ROOT


def main() -> None:
    """
    Preserve calibration's failed308body and307numerics; schedule only remaining first attempts.

    This is a provenance-labelled report transformation, not a numerical rerun or
    change to any mathematical route. All four cases remain in the denominator.
    Geometry files are copied byte-for-byte with source hashes retained.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run = parser.parse_args().output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    numerical_path = ROOT / "artifacts/verification/ribbon_layout307/result.json"
    failure_path = ROOT / "artifacts/verification/ribbon_layout308/calibration-native.json"
    numerical = json.loads(numerical_path.read_text())
    failure = json.loads(failure_path.read_text())
    if (
        numerical["status"] != "completed"
        or failure["status"] != "stopped"
        or failure["audit"]["maximum_error_mm"] <= 1e-6
    ):
        raise RuntimeError("Expected completed307and recorded308over-tolerance surface rejection")
    paths = {
        Path(__file__),
        numerical_path,
        failure_path,
        ROOT / "artifacts/verification/ribbon_layout308/result.json",
        ROOT / "artifacts/verification/ribbon_layout307/plan.json",
        ROOT / "artifacts/verification/ribbon_aesthetic302/calibration-native.json",
        *(
            ROOT / f"artifacts/verification/ribbon_layout307/{row['id']}-eased.json"
            for row in numerical["cases"]
        ),
    }
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    plan = {
        "scope": "Metadata-only continuation after308calibration surface error5.718e-6mm exceeded unchanged1e-6gate. Preserve all307routes byte-for-byte, numerical outcomes and all four case identities. Exclude new calibration from future native scheduling, retain its previous302body; remainingGym1/Gym3first attempts unknown. No new solve/build/audit/physical-rule change in this transformation.",
        "cases": [row["id"] for row in numerical["cases"]],
        "sources": hashes,
        "limits": {"new_solves": 0, "native_attempts": 0, "seconds": 10},
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    started = time.monotonic()
    for relative in hashes:
        copied = run / "sources" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((ROOT / relative).read_bytes())
    for row in numerical["cases"]:
        name = row["id"]
        row["numerical_status"] = row["status"]
        if name == "calibration":
            row.update(
                status="excluded_after_native_fidelity_rejection",
                native_rejection=str(failure_path.relative_to(ROOT)),
                retained_native="artifacts/verification/ribbon_aesthetic302/calibration-native.json",
            )
        source = ROOT / f"artifacts/verification/ribbon_layout307/{name}-eased.json"
        destination = run / f"{name}-eased.json"
        destination.write_bytes(source.read_bytes())
        if (
            hashlib.sha256(destination.read_bytes()).hexdigest()
            != hashes[str(source.relative_to(ROOT))]
        ):
            raise RuntimeError("Frozen route copy changed bytes")
    numerical["continuation_scope"] = plan["scope"]
    numerical["original_numerical_results"] = str(numerical_path.relative_to(ROOT))
    numerical["transformation_seconds"] = time.monotonic() - started
    if numerical["transformation_seconds"] > 10:
        raise TimeoutError("Metadata-only continuation exceeded its time cap")
    (run / "result.json").write_text(json.dumps(numerical, indent=2))
    print(
        json.dumps(
            {
                "cases": plan["cases"],
                "native_excluded": ["calibration"],
                "remaining_first_attempts": [
                    r["id"] for r in numerical["cases"] if r["status"] == "eased"
                ],
                "geometry_changed": False,
                "transformation_seconds": numerical["transformation_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
