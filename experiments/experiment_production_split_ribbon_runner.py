"""
Execute only the production-copy Split-ribbon comparison in the Fusion scratch.
"""

from __future__ import annotations

import argparse
import json

from experiments.qa_orchestrator import DEFAULT_MCP_URL, McpClient


def main() -> int:
    """
    Return a failure when Fusion does not complete the requested comparison script.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    arguments = parser.parse_args()
    script = """
import importlib

def run(context: object) -> None:
    shared = 'experiments.experiment_secure_discrete_ribbon.'
    for name in ('transitions', 'end_boundary', 'cases', 'reporting'):
        importlib.reload(importlib.import_module(shared + name))
    prefix = 'experiments.experiment_production_split_ribbon.'
    for name in ('sources', 'live'):
        importlib.reload(importlib.import_module(prefix + name))
    importlib.import_module(prefix + 'live').run(context)
"""
    if arguments.smoke:
        script = script.replace(".run(context)", ".run_smoke(context)")
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
