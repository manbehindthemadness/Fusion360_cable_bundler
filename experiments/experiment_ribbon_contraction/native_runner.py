"""
Pin four native replay attempts on the local Fusion MCP, without numerical refinement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from experiments.qa_orchestrator import McpClient

from .runner import CASES, ROOT


def main() -> None:
    """
    Attempt each frozen contracted case once and stop after the first host failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotate", action="store_true")
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    cases = [
        {
            "id": name,
            "contracted": f"artifacts/verification/ribbon_contract258/{name}-contracted.json",
            "baseline_native": f"artifacts/verification/ribbon_fidelity221/{name}-native.json",
        }
        for name, _ in CASES
    ]
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        ROOT / "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py",
        ROOT / "experiments/experiment_optional_appearance/host.py",
        ROOT / "devtools/ribbon_analysis/budget.py",
        ROOT / "devtools/ribbon_analysis/end_profiles.py",
        ROOT / "artifacts/verification/ribbon_contract258/plan.json",
        ROOT / "artifacts/verification/ribbon_contract258/result.json",
        *(ROOT / item[key] for item in cases for key in ("contracted", "baseline_native")),
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
    }
    plan = {
        "root": str(ROOT),
        "cases": cases,
        "started": time.time(),
        "question": "Do the four frozen shortened routes construct and retain native material fidelity?",
        "scope": "4 existing gym configurations, at most4newcreateBody attempts,0newsolves/refinements/retries; unchanged builder and profile. Originals and unrelated designs untouched. New bodies retained hidden after isolated captures.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "rss_kib": 4194304,
            "launch_rss_kib": 3984588,
        },
        "stop": "First source/API/resource/kernel/fidelity failure stops all remaining attempts; preserve incomplete case and ledger. No automatic renewal.",
        "audit": "Unchanged221sampled surface/orderedguide/seam/cap checks; no full native contact/strain/equilibrium certificate",
        "sources": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        },
    }
    if args.annotate:
        plan.update(
            question="Retain three original guides and visible measurements on each frozen native result",
            scope="4 owned259components only;0newsolves/builds/geometryrepairs;120s total,4GiB RSS/3.8GiB headroom. Preserve body revisions and all unrelated content.",
            prior_display_stop="260 stopped at the calibration panel after guide authoring; Fusion log confirms an off-plane text anchor. Failed artifacts remain. Renewed display-only phase uses an XY anchor, verifies/reuses complete guides when present, leaves partial annotations untouched, and reloads only the display adapter. Native transaction retention is not assumed. No geometry rerun.",
        )
        for entry in cases:
            relative = f"artifacts/verification/ribbon_contract259/{entry['id']}-native.json"
            plan["sources"][relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in plan["sources"]:
        destination = run / "sources" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    client = McpClient("http://127.0.0.1:27182/mcp", 150)
    client.initialize()
    if args.annotate:
        script = (
            "def run(context):\n import importlib\n from experiments.experiment_ribbon_contraction import display\n importlib.reload(display)\n display.annotate("
            + repr(str(run))
            + ")\n"
        )
        response = client.call_tool(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": script, "readOnly": False}},
        )
        (run / "response.json").write_text(json.dumps(response))
        print(json.dumps(response)[:4000])
        result_path = run / "result.json"
        if (
            not result_path.exists()
            or json.loads(result_path.read_text())["unattempted_or_incomplete"]
        ):
            raise RuntimeError("Annotation stopped; preserve partial evidence")
        return
    for entry in cases:
        script = (
            "def run(context):\n from experiments.experiment_ribbon_contraction.native import build\n build("
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
        result_path = run / f"{entry['id']}-native.json"
        if not result_path.exists():
            raise RuntimeError(
                "Host did not return a native result: " + json.dumps(response)[:2000]
            )
        result = json.loads(result_path.read_text())
        print(
            json.dumps(
                {
                    key: value
                    for key, value in result.items()
                    if key not in {"audit", "rss_samples", "kernel_outcome"}
                }
            ),
            flush=True,
        )
        if result["status"] != "built_and_named_fidelity_checks_pass":
            raise RuntimeError("Native replay stopped; remaining cases unattempted")


if __name__ == "__main__":
    main()
