"""
Continue fixed285plans after independent trim diagnosis, without rebuilding the first body.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from experiments.experiment_ribbon_contraction.runner import ROOT
from experiments.qa_orchestrator import McpClient


def main() -> None:
    """
    Pin a new measurement policy and at most two remaining first native attempts.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run = parser.parse_args().output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    numerical_path = "artifacts/verification/ribbon_joint285/result.json"
    numerical = json.loads((ROOT / numerical_path).read_text())
    if numerical["status"] != "completed":
        raise RuntimeError("Original joint numerical phase must be complete")
    cases = [
        {
            "id": c["id"],
            "contracted": f"artifacts/verification/ribbon_joint285/{c['id']}-joint.json",
            "baseline_native": f"artifacts/verification/ribbon_fidelity221/{c['id']}-native.json",
        }
        for c in numerical["cases"]
        if c["status"] == "joint"
    ]
    if [c["id"] for c in cases] != ["gym-1", "gym-2", "gym-3"]:
        raise RuntimeError("Frozen continuation requires the same three changed285cases")
    cases[0]["existing_native"] = "artifacts/verification/ribbon_joint286/gym-1-native.json"
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        ROOT / "experiments/experiment_ribbon_bend_reduction/review.py",
        ROOT / "experiments/experiment_ribbon_bend_reduction/closure.py",
        ROOT / "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py",
        ROOT / "experiments/experiment_optional_appearance/host.py",
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/end_profiles.py",
        ROOT / "devtools/ribbon_analysis/budget.py",
        ROOT / numerical_path,
        ROOT / "artifacts/verification/ribbon_joint285/plan.json",
        ROOT / "artifacts/verification/ribbon_joint286/gym-1-native.json",
        ROOT / "artifacts/verification/ribbon_trim288/result.json",
        ROOT / "tests/test_ribbon_joint_trim.py",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(ROOT / c[k] for c in cases for k in ("contracted", "baseline_native")),
    }
    plan = {
        "root": str(ROOT),
        "cases": cases,
        "started": time.time(),
        "numerical_results": numerical_path,
        "component_prefix": "289 - Joint first-pass route - ",
        "body_name": "Joint first-pass material route",
        "display_x_cm": 410,
        "review_title": "Joint first pass with explicit trim verification",
        "pass_label": "Joint first pass and contact",
        "method_note": "No entry resets; strict native distance gates with actual-UV collapsed-edge proof",
        "fidelity_audit": "experiments/experiment_ribbon_joint_route/fidelity.py",
        "scope": "Original285plans unchanged. Re-audit existing286Gym1body without rebuilding; Gym2/Gym3first construction only. Preserve286failure and288actual-trim evidence. No solver/profile/builder/tolerance/healing changes. New audit policy adds a recorded actual-coedge/identical-NURBS/strict-interior/trimmed-distance certificate; all original distance/seam/guide/cap checks unchanged.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "new_native_attempts": 2,
            "reused_native_bodies": 1,
            "rss_kib": 4194304,
            "launch_rss_kib": 3984588,
            "trim_certifications": 64,
        },
        "prediction": "Full named fidelity still unknown. One point's strict UV interior is independently supported by288; no new native acceptance is presumed.",
        "stop": "First source/resource/API/kernel/fidelity/review failure stops remaining cases. No rebuild of Gym1, no rerouting, tolerance expansion or further automatic native retry.",
        "sources": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in plan["sources"]:
        copied = run / "sources" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((ROOT / relative).read_bytes())
    client = McpClient("http://127.0.0.1:27182/mcp", 180)
    client.initialize()
    output: dict[str, Any] = {
        "status": "running",
        "cases": [],
        "unattempted": [c["id"] for c in cases],
        "unchanged_not_rebuilt": ["calibration"],
    }
    try:
        for entry in cases:
            call = "resume.audit_existing" if "existing_native" in entry else "native.build"
            script = (
                "def run(context):\n import importlib\n from experiments.experiment_ribbon_contraction import native\n from experiments.experiment_ribbon_bend_reduction import review\n from experiments.experiment_ribbon_joint_route import fidelity, resume\n importlib.reload(native)\n importlib.reload(review)\n importlib.reload(fidelity)\n importlib.reload(resume)\n "
                + call
                + "("
                + repr(str(run))
                + ", "
                + repr(entry["id"])
                + ")\n review.show_case("
                + repr(str(run))
                + ", "
                + repr(entry["id"])
                + ")\n"
            )
            response = client.call_tool(
                "fusion_mcp_execute",
                {"featureType": "script", "object": {"script": script, "readOnly": False}},
            )
            (run / f"{entry['id']}-response.json").write_text(json.dumps(response))
            path = run / f"{entry['id']}-native.json"
            if not path.exists():
                raise RuntimeError("Missing continuation result: " + json.dumps(response)[:2000])
            row = json.loads(path.read_text())
            output["cases"].append(
                {
                    k: v
                    for k, v in row.items()
                    if k not in {"audit", "rss_samples", "kernel_outcome"}
                }
            )
            output["unattempted"].remove(entry["id"])
            print(json.dumps(output["cases"][-1]), flush=True)
            if (
                row["status"] != "built_and_named_fidelity_checks_pass"
                or not (run / f"{entry['id']}-review.json").exists()
            ):
                raise RuntimeError("Joint continuation stopped: " + json.dumps(response)[:2000])
        output["status"] = "completed"
    except (OSError, RuntimeError, ValueError) as error:
        output.update(status="stopped", error=str(error))
        raise
    finally:
        output["elapsed_seconds"] = time.time() - plan["started"]
        (run / "result.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
