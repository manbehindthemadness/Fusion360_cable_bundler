"""
Execute retained ribbon failure diagnostics through the local Fusion MCP server.
"""

from __future__ import annotations

import argparse
import json

from experiments.qa_orchestrator import DEFAULT_MCP_URL, McpClient


def main() -> int:
    """
    Return failure unless the requested diagnostic pass completes in Fusion.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("smoke", "baseline", "planes", "caps", "dense", "compact", "spatial"),
        default="compact",
    )
    parser.add_argument("--case-index", type=int, default=0)
    arguments = parser.parse_args()
    script = """
import importlib
def run(context: object) -> None:
    shared = 'experiments.experiment_secure_discrete_ribbon.'
    for name in ('policy', 'transitions', 'end_boundary', 'cases', 'audits', 'reporting', 'live'):
        importlib.reload(importlib.import_module(shared + name))
    production = 'experiments.experiment_production_split_ribbon.'
    for name in ('sources', 'live'):
        importlib.reload(importlib.import_module(production + name))
    prefix = 'experiments.experiment_ribbon_diagnosis.'
    for name in ('observations', 'audit_probe', 'inputs', 'landmark_probe', 'storage', 'compact', 'cloth', 'end_sections', 'spatial', 'preflight', 'rail_topology', 'rail_audit', 'live'):
        importlib.reload(importlib.import_module(prefix + name))
    importlib.import_module(prefix + 'live').run(context, MODE, CASE_INDEX)
""".replace("MODE", repr(arguments.mode)).replace("CASE_INDEX", repr(arguments.case_index))
    client = McpClient(DEFAULT_MCP_URL, timeout_seconds=900.0)
    try:
        client.initialize()
        result = client.call_tool(
            "fusion_mcp_execute", {"featureType": "script", "object": {"script": script}}
        )
        for block in result.get("content", []):
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                print(block["text"])
                response = json.loads(block["text"])
                if isinstance(response, dict) and response.get("success") is True:
                    return 0
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
