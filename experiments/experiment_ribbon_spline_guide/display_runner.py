"""
Freeze one display-only reference comparison for all four spline-guide configurations.
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
    Pin guide/body evidence, then draw exact references once through local Fusion MCP.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run = parser.parse_args().output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    numerical = json.loads(
        (ROOT / "artifacts/verification/ribbon_guide270/result.json").read_text()
    )
    native = json.loads((ROOT / "artifacts/verification/ribbon_guide271/result.json").read_text())
    if numerical["status"] != "completed" or native["status"] != "completed":
        raise RuntimeError("Complete numerical/native stages required for display")
    cases = []
    for row in numerical["cases"]:
        name = row["id"]
        variants = [
            {
                "label": "baseline",
                "native": f"artifacts/verification/ribbon_radius268/{name}-native.json",
            }
        ]
        if row["status"] == "guided":
            variants.append(
                {
                    "label": "guided",
                    "native": f"artifacts/verification/ribbon_guide271/{name}-native.json",
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
        ROOT / "devtools/ribbon_analysis/graphics.py",
        ROOT / "experiments/experiment_optional_appearance/host.py",
        *(ROOT / c["guide"] for c in cases),
        *(ROOT / v["native"] for c in cases for v in c["variants"]),
    }
    plan = {
        "root": str(ROOT),
        "cases": cases,
        "scope": "Display only,0solves/builds; four examined configurations, magenta unconstrained guide with hidden exact native cubic; preserve all bodies/earlier views",
        "limits": {"seconds": 120, "rss_kib": 4194304, "launch_rss_kib": 3984588},
        "sources": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    client = McpClient("http://127.0.0.1:27182/mcp", 180)
    client.initialize()
    script = (
        "def run(context):\n from experiments.experiment_ribbon_spline_guide.display import show\n show("
        + repr(str(run))
        + ")\n"
    )
    response = client.call_tool(
        "fusion_mcp_execute",
        {"featureType": "script", "object": {"script": script, "readOnly": False}},
    )
    (run / "response.json").write_text(json.dumps(response))
    if not (run / "result.json").exists():
        raise RuntimeError("Missing display result: " + json.dumps(response)[:2000])
    result = json.loads((run / "result.json").read_text())
    if result.get("status") != "completed":
        raise RuntimeError("Reference display incomplete: " + json.dumps(response)[:2000])
    print(json.dumps(result))


if __name__ == "__main__":
    main()
