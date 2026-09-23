"""Launch the isolated weld local-frame probe through the Fusion MCP server."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.qa_orchestrator import DEFAULT_MCP_URL, McpClient

RESULT_PREFIX = "WELD_PROJECTION_RESULT="
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PATH = "/private/tmp/cable_bundler_weld_projection.png"


def _fusion_script() -> str:
    """Return the Fusion-hosted entry point for the production geometry probe."""
    root = json.dumps(str(PROJECT_ROOT))
    prefix = json.dumps(RESULT_PREFIX)
    capture_path = json.dumps(CAPTURE_PATH)
    return f"""import importlib
import json
import sys

def run(_context):
    project_root = {root}
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    welds = importlib.import_module("cable_bundler.fusion.cable_solid_parts.welds")
    importlib.reload(welds)
    module = importlib.import_module("experiments.experiment_weld_projection")
    module = importlib.reload(module)
    result = module.run_projection_probe({capture_path})
    print({prefix} + json.dumps(result, sort_keys=True))
"""


def _execution_message(tool_result: dict[str, object]) -> str:
    """Extract the script's captured standard output from an MCP tool result."""
    content = tool_result.get("content")
    if not isinstance(content, list) or not content:
        raise RuntimeError(f"Fusion MCP returned no result content: {tool_result!r}")
    first = content[0]
    if not isinstance(first, dict) or not isinstance(first.get("text"), str):
        raise RuntimeError(f"Fusion MCP returned malformed result content: {tool_result!r}")
    execution = json.loads(first["text"])
    if not isinstance(execution, dict):
        raise RuntimeError(f"Fusion MCP returned a malformed execution: {execution!r}")
    message = execution.get("message")
    if not isinstance(message, str):
        raise RuntimeError(f"Fusion MCP execution omitted its message: {execution!r}")
    return message


def main() -> int:
    """Execute the probe and return nonzero unless all geometry cases pass."""
    client = McpClient(DEFAULT_MCP_URL, timeout_seconds=120.0)
    try:
        client.initialize()
        tool_result = client.call_tool(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": _fusion_script()}},
        )
    finally:
        client.close()
    message = _execution_message(tool_result)
    print(message)
    marker = next(
        (line for line in message.splitlines() if line.startswith(RESULT_PREFIX)),
        "",
    )
    if not marker:
        return 1
    result = json.loads(marker.removeprefix(RESULT_PREFIX))
    return 0 if isinstance(result, dict) and result.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
