"""
Replay only the changed263routes using the shared native builder and fixed audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from experiments.experiment_ribbon_contraction.runner import ROOT
from experiments.qa_orchestrator import McpClient


def main() -> None:
    """
    Freeze at most three new native attempts and stop after the first failed stage.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    numerical_path = "artifacts/verification/ribbon_bends263/result.json"
    numerical = json.loads((ROOT / numerical_path).read_text())
    if numerical["status"] != "completed":
        raise RuntimeError("Numerical batch is not complete")
    cases = [
        {
            "id": item["id"],
            "contracted": f"artifacts/verification/ribbon_bends263/{item['id']}-reduced.json",
            "baseline_native": f"artifacts/verification/ribbon_fidelity221/{item['id']}-native.json",
        }
        for item in numerical["cases"]
        if item["status"] == "reduced"
    ]
    if len(cases) > 3:
        raise RuntimeError("At most three changed native cases in this frozen comparison")
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        ROOT / "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py",
        ROOT / "experiments/experiment_optional_appearance/host.py",
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/end_profiles.py",
        ROOT / "devtools/ribbon_analysis/budget.py",
        ROOT / numerical_path,
        ROOT / "artifacts/verification/ribbon_bends263/plan.json",
        *(ROOT / item[key] for item in cases for key in ("contracted", "baseline_native")),
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
    }
    plan = {
        "root": str(ROOT),
        "cases": cases,
        "started": time.time(),
        "numerical_results": numerical_path,
        "component_prefix": "264 - Bend simplification - ",
        "body_name": "Bend-reduced material ribbon",
        "display_x_cm": 170,
        "question": "Do the three changed bend-first routes build with fewer native surfaces and retained ordered material fidelity?",
        "unchanged_not_rebuilt": [
            item["id"] for item in numerical["cases"] if item["status"] == "unchanged"
        ],
        "scope": "Four independently evaluated development configurations, three changed variants attempted once;0straightcontraction/refinement/retries. Shared unchanged material builder/profile and archived221audit. Preserve originals and259variants. Leave new geometry visible; retain three hidden original guides and fixed cap sketches.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "native_attempts": 3,
            "rss_kib": 4194304,
            "launch_rss_kib": 3984588,
            "review_seconds_per_case": 45,
        },
        "prediction": "Unknown kernel outcomes; numerical contact separated. Sampled native fidelity is not a complete physical audit or universal success claim.",
        "stop": "First source/API/resource/kernel/fidelity/review error stops remaining cases. Preserve partial records and all unattempted cases; no automatic retry/refinement.",
        "sources": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        },
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in plan["sources"]:
        copied = run / "sources" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((ROOT / relative).read_bytes())
    client = McpClient("http://127.0.0.1:27182/mcp", 180)
    client.initialize()
    summary = {
        "status": "running",
        "cases": [],
        "unattempted": [item["id"] for item in cases],
        "unchanged_not_rebuilt": plan["unchanged_not_rebuilt"],
    }
    try:
        for entry in cases:
            script = (
                "def run(context):\n import importlib\n from experiments.experiment_ribbon_contraction import native\n importlib.reload(native)\n native.build("
                + repr(str(run))
                + ", "
                + repr(entry["id"])
                + ")\n from experiments.experiment_ribbon_bend_reduction.review import show_case\n show_case("
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
                raise RuntimeError("Missing native result: " + json.dumps(response)[:3000])
            row = json.loads(path.read_text())
            summary["cases"].append(
                {
                    key: value
                    for key, value in row.items()
                    if key not in {"audit", "rss_samples", "kernel_outcome"}
                }
            )
            summary["unattempted"].remove(entry["id"])
            print(json.dumps(summary["cases"][-1]), flush=True)
            if (
                row["status"] != "built_and_named_fidelity_checks_pass"
                or not (run / f"{entry['id']}-review.json").exists()
            ):
                raise RuntimeError(
                    "Native build/audit/review stopped: " + json.dumps(response)[:3000]
                )
        summary["status"] = "completed"
    except (OSError, RuntimeError, ValueError) as error:
        summary.update(status="stopped", error=str(error))
        raise
    finally:
        summary["elapsed_seconds"] = time.time() - plan["started"]
        (run / "result.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
