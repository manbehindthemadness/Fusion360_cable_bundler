"""
Overlay the same frozen reference splines on successfully audited aesthetic bodies.
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
    Display the four original guides without solving, rebuilding or editing prior geometry.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    native_path = ROOT / "artifacts/verification/ribbon_aesthetic302/result.json"
    numerical_path = ROOT / "artifacts/verification/ribbon_aesthetic296/result.json"
    native, numerical = json.loads(native_path.read_text()), json.loads(numerical_path.read_text())
    if native["status"] != "completed" or numerical["status"] != "completed":
        raise RuntimeError("Successful numerical/native aesthetic phases required")
    cases = [
        {
            "id": c["id"],
            "guide": f"artifacts/verification/ribbon_guide270/{c['id']}-guide.json",
            "variants": [
                {
                    "label": "eased",
                    "native": f"artifacts/verification/ribbon_aesthetic302/{c['id']}-native.json",
                }
            ],
        }
        for c in native["cases"]
    ]
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_spline_guide").glob("*.py"),
        ROOT / "devtools/ribbon_analysis/graphics.py",
        ROOT / "experiments/experiment_optional_appearance/host.py",
        native_path,
        numerical_path,
        *(ROOT / c["guide"] for c in cases),
        *(ROOT / v["native"] for c in cases for v in c["variants"]),
    }
    plan = {
        "root": str(ROOT),
        "cases": cases,
        "scope": "Display-only frozen270guides on audited302bodies;0solves/builds, preserve all earlier geometry/visibility/revisions.",
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
        raise RuntimeError("Missing aesthetic reference display: " + json.dumps(response)[:2000])
    result = json.loads((run / "result.json").read_text())
    if result["status"] != "completed":
        raise RuntimeError("Aesthetic reference display incomplete: " + json.dumps(response)[:2000])
    print(json.dumps({k: v for k, v in result.items() if k != "rss_samples"}))


if __name__ == "__main__":
    main()
