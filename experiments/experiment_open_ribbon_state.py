"""
List saved ribbon configurations in open Fusion documents without changing them.

Requires Fusion, the add-in, and the local development MCP server.
"""

from __future__ import annotations

from experiments.qa_orchestrator import DEFAULT_MCP_URL, McpClient


def main() -> int:
    """
    Log a compact inventory of open designs and their saved ribbon groups.
    """
    script = """
import json
import adsk.core
import adsk.fusion
from cable_bundler.domain import loads

def run(_context):
    application = adsk.core.Application.get()
    rows = []
    for document in application.documents:
        design = adsk.fusion.Design.cast(document.products.itemByProductType('DesignProductType'))
        if design is None:
            continue
        for attribute in design.findAttributes('kev0.cable_bundler', 'harness_definition'):
            definition = loads(attribute.value)
            for index, group in enumerate(definition.cable_groups, start=1):
                if group.group_type.value != 'ribbon':
                    continue
                rows.append({
                    'document': document.name,
                    'group_index': index,
                    'name': group.name,
                    'behavior': group.interface_behavior.value,
                    'geometry': group.ribbon_geometry.value,
                    'body': group.ribbon_body_type.value,
                    'lines': group.ribbon_lines,
                })
    adsk.core.Application.log(
        'OPEN_RIBBON_STATE=' + json.dumps(rows),
        adsk.core.LogLevels.InfoLogLevel,
        adsk.core.LogTypes.FileLogType,
    )
"""
    client = McpClient(DEFAULT_MCP_URL, timeout_seconds=30.0)
    try:
        client.initialize()
        result = client.call_tool(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": script, "readOnly": True}},
        )
        for block in result.get("content", []):
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                print(block["text"])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
