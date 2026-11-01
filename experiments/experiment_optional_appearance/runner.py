"""
Pin bounded deferred-color trials before invoking the local Fusion MCP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.qa_orchestrator import McpClient

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    {"id": "calibration", "input": "artifacts/verification/ribbon_sweep202/case-4.json"},
    *(
        {"id": f"gym-{i}", "input": f"artifacts/verification/ribbon_fidelity216/case-{i}.json"}
        for i in (1, 2, 3)
    ),
]


def main() -> None:
    """
    Run one immutable phase without solving, building, repairing or changing targets.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("export", "apply"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bake", type=Path)
    parser.add_argument("--export", dest="export_path", type=Path)
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts" / "verification")
    run.mkdir(parents=True, exist_ok=True)
    cases = [
        {**case, "evidence": f"artifacts/verification/ribbon_fidelity221/{case['id']}-native.json"}
        for case in CASES
    ]
    paths = [
        *Path(__file__).parent.glob("*.py"),
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(ROOT / case["input"] for case in cases),
        *(ROOT / case["evidence"] for case in cases),
    ]
    plan = {
        "phase": args.phase,
        "root_path": str(ROOT),
        "cases": cases,
        "question": "Can supported color appearances be chosen after geometry creation and baked reliably across four existing gym layouts?",
        "scope": "Four independent existing complete configurations;0newsolves or geometry constructions. Export creates exactly4appearance-only copies;later apply uses those copies. Endcap mismatch accepted by user. No target, profile, rule or production changes. Initial plain colors require no source bitmap or bake. Library Fabric base-color image is copied into a generic opaque source appearance;this does not promise reproduction of the library Fabric's full shader.",
        "prediction": "Unknown complete appearance outcomes. Native maps remain unchanged. Material inverse and native chart/image read-back must agree;source image and texture selection are explicit optional work.",
        "limits": {
            "native_phase_seconds": 120,
            "rss_kib": 4194304,
            "launch_rss_kib": 3984588,
            "resource_sample_group": 16,
            "geometry_attempts": 0,
            "solves": 0,
            "retries": 0,
        },
        "stop": "First API/source/resource/geometry/native-chart mismatch. Preserve partial evidence and all unattempted cases. Further work requires a reviewed fresh pinned plan;no automatic retries.",
        "timing_policy": "Geometry generation excludes all optional appearance extraction,baking,assignment and checks; retain full elapsed time when executed. No new geometry timing or speedup measured by this appearance-only trial.",
    }
    if args.phase == "apply":
        if args.bake is None or args.export_path is None:
            parser.error("apply requires --bake and --export")
        plan["bake_path"] = str(args.bake.resolve())
        plan["export_path"] = str(args.export_path.resolve())
        paths += [
            args.bake / "result.json",
            *args.bake.glob("*/*.png"),
            *args.export_path.glob("*-charts.json"),
        ]
    plan["sources"] = {
        str(p.resolve().relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }
    with (run / "plan.json").open("x") as stream:
        json.dump(plan, stream, indent=2)
    client = McpClient("http://127.0.0.1:27182/mcp", 150)
    client.initialize()
    host = Path(__file__).with_name("host.py")
    script = (
        "def run(context):\n import runpy\n ns=runpy.run_path("
        + repr(str(host))
        + ")\n ns['run_phase']("
        + repr(str(run))
        + ")\n"
    )
    response = client.call_tool(
        "fusion_mcp_execute",
        {"featureType": "script", "object": {"script": script, "readOnly": False}},
    )
    with (run / "response.json").open("x") as stream:
        json.dump(response, stream)
    print(json.dumps(response)[:4000])


if __name__ == "__main__":
    main()
