"""
Read-only live probe of saved Interface contact positions in the active Fusion design.

Requires Fusion, the add-in, local MCP server, and the user's active PCB document.
The script does not change the document or selection.
"""

from __future__ import annotations

from experiments.qa_orchestrator import DEFAULT_MCP_URL, McpClient


def main() -> int:
    """
    Print saved contact metadata and resolved assembly-space centers.
    """
    script = """
import json
import adsk.core
import adsk.fusion
from cable_bundler.domain import loads
from cable_bundler.fusion.interface_contact_projection_copy import _oriented_contacts
def run(_context):
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError('Open the PCB design before running the probe.')
    for attribute in design.findAttributes('kev0.cable_bundler', 'harness_definition'):
        definition = loads(attribute.value)
        for interface in definition.interfaces:
            positions = {item.contact_id: item for item in _oriented_contacts(design, interface.contacts)}
            selected = [contact for contact in interface.contacts
                if not contact.name or contact.name.startswith(('J4.17', 'J4.18', 'J4.19', 'J3.01'))]
            if not selected:
                continue
            print('INTERFACE_PROJECTION=' + json.dumps({
                'interface': interface.name,
                'contacts': [{
                    'value': contact.name,
                    'pin': contact.pin,
                    'center': positions[contact.contact_id].center_mm,
                    'normal': positions[contact.contact_id].normal,
                } for contact in selected if contact.contact_id in positions],
            }))
"""
    client = McpClient(DEFAULT_MCP_URL, timeout_seconds=60.0)
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
