"""
Inspect local Fusion naming owners for saved Interface contacts without editing them.

Requires Fusion with the add-in, the local MCP server, and an active test design.
"""

from __future__ import annotations

import json

from experiments.qa_orchestrator import DEFAULT_MCP_URL, McpClient


def main() -> int:
    """
    Print owner sharing and referenced-component status in the active design.
    """
    script = """
import json
import adsk.core
import adsk.fusion
from cable_bundler.domain import loads
from cable_bundler.fusion.interface_contact_cache import resolve_contact_entities
from cable_bundler.fusion.attachment_targets import attachment_target_kind
def run(_context):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    if design is None:
        raise RuntimeError('Open the Interface test design.')
    for attribute in design.findAttributes('kev0.cable_bundler', 'harness_definition'):
        definition = loads(attribute.value)
        for interface in definition.interfaces:
            if not interface.contacts:
                continue
            rows = []
            for contact in interface.contacts:
                entity = next((item for item in resolve_contact_entities(design, contact.entity_token)
                    if attachment_target_kind(item) is contact.kind), None)
                if entity is None:
                    continue
                owner = getattr(entity, 'body', None) or getattr(entity, 'parentSketch', None) or entity
                occurrence = getattr(owner, 'assemblyContext', None) or getattr(entity, 'assemblyContext', None)
                rows.append({'kind': contact.kind.value, 'pin': contact.pin, 'value': contact.name,
                    'ownerToken': getattr(owner, 'entityToken', ''), 'ownerName': getattr(owner, 'name', ''),
                    'ownerType': getattr(owner, 'objectType', ''),
                    'referenced': getattr(occurrence, 'isReferencedComponent', None),
                    'hasNativeObject': getattr(owner, 'nativeObject', None) is not None})
            if rows:
                counts = {item['ownerToken']: sum(other['ownerToken'] == item['ownerToken'] for other in rows)
                    for item in rows}
                print('LOCAL_NAMES=' + json.dumps({'interface': interface.name,
                    'count': len(rows), 'samples': [dict(item, sharing=counts[item['ownerToken']])
                        for item in rows[:5]]}))
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
                execution = json.loads(block["text"])
                print(execution.get("message", ""))
                if not execution.get("success", False):
                    return 1
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
