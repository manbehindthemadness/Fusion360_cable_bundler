"""
Draw the unchanged reference splines on new successfully audited joint first-pass bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.experiment_ribbon_contraction.runner import ROOT
from experiments.qa_orchestrator import McpClient


def main() -> None:
    """
    Reuse the guarded reference renderer without editing old bodies or solving in Fusion.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run = parser.parse_args().output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    numerical_path = ROOT / "artifacts/verification/ribbon_joint285/result.json"
    native_path = ROOT / "artifacts/verification/ribbon_joint289/result.json"
    numerical, native = json.loads(numerical_path.read_text()), json.loads(native_path.read_text())
    if numerical["status"] != "completed" or native["status"] != "completed":
        raise RuntimeError("Successful numerical/native stages required")
    cases = []
    for row in numerical["cases"]:
        name = row["id"]
        variants = []
        if row["status"] == "joint":
            variants.append(
                {
                    "label": "joint",
                    "native": f"artifacts/verification/ribbon_joint289/{name}-native.json",
                }
            )
        cases.append(
            {
                "id": name,
                "guide": f"artifacts/verification/ribbon_guide270/{name}-guide.json",
                "variants": variants,
            }
        )
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_spline_guide").glob("*.py"),
        ROOT / "devtools/ribbon_analysis/graphics.py",
        ROOT / "experiments/experiment_optional_appearance/host.py",
        numerical_path,
        native_path,
        *(ROOT / c["guide"] for c in cases),
        *(ROOT / v["native"] for c in cases for v in c["variants"]),
    }
    plan = {
        "root": str(ROOT),
        "cases": cases,
        "scope": "Display-only magenta frozen guide on289audited joint results (Gym1existing286body);0solves/builds. Preserve previous successful geometry, visibility and failed evidence.",
        "limits": {"seconds": 120, "rss_kib": 4194304, "launch_rss_kib": 3984588},
        "sources": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    client = McpClient("http://127.0.0.1:27182/mcp", 180)
    client.initialize()
    script = (
        "def run(context):\n import importlib\n from experiments.experiment_ribbon_spline_guide import display\n importlib.reload(display)\n display.show("
        + repr(str(run))
        + ")\n"
    )
    response = client.call_tool(
        "fusion_mcp_execute",
        {"featureType": "script", "object": {"script": script, "readOnly": False}},
    )
    (run / "response.json").write_text(json.dumps(response))
    if not (run / "result.json").exists():
        raise RuntimeError("Missing joint reference display: " + json.dumps(response)[:2000])
    result = json.loads((run / "result.json").read_text())
    if result.get("status") != "completed":
        raise RuntimeError("Joint reference display incomplete: " + json.dumps(response)[:2000])
    print(json.dumps({k: v for k, v in result.items() if k != "rss_samples"}))


if __name__ == "__main__":
    main()
