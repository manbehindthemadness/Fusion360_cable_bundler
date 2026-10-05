"""
Invoke the isolated Discrete/Split experiment through the local Fusion MCP.
"""

from __future__ import annotations

import argparse

from experiments.qa_orchestrator import DEFAULT_MCP_URL, McpClient


def main() -> int:
    """
    Author only the experiment's new scratch document in the current session.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--close-unmodified", action="store_true")
    parser.add_argument("--inventory", action="store_true")
    arguments = parser.parse_args()
    script = """
import importlib

def run(context: object) -> None:
    prefix = 'experiments.experiment_secure_discrete_ribbon.'
    for name in ('contract', 'frames', 'bank', 'shape', 'guides', 'builder', 'exits', 'transitions', 'end_boundary', 'cases', 'audits', 'reporting', 'live'):
        importlib.reload(importlib.import_module(prefix + name))
    importlib.import_module(prefix + 'live').run(context)
"""
    if arguments.close_unmodified:
        script = """
import adsk.core

def run(context: object) -> None:
    app = adsk.core.Application.get()
    expected_name = 'Secure ribbon experiment ' + chr(8212) + ' Discrete Split'
    scratch = next((doc for doc in app.documents if doc.name == expected_name), None)
    if scratch is None:
        raise RuntimeError('The final experiment scratch is not open.')
    for doc in tuple(app.documents):
        if doc.isValid and doc != scratch and doc.isVisible and not doc.isModified:
            doc.activate()
            if not doc.isModified and not doc.close(False):
                raise RuntimeError('Could not close unchanged document: ' + doc.name)
            adsk.doEvents()
    scratch.activate()
"""
    if arguments.inventory:
        script = """
import json
from pathlib import Path
import cable_bundler
import adsk.core

def run(context: object) -> None:
    app = adsk.core.Application.get()
    rows = [{'name': doc.name, 'modified': doc.isModified, 'saved': doc.isSaved, 'visible': doc.isVisible, 'active': doc.isActive} for doc in app.documents]
    path = Path(cable_bundler.__file__).resolve().parents[1] / 'artifacts/verification/secure_discrete_ribbon/documents.json'
    path.write_text(json.dumps(rows, indent=2), encoding='utf-8')
"""
    client = McpClient(DEFAULT_MCP_URL, timeout_seconds=900.0)
    try:
        client.initialize()
        result = client.call_tool(
            "fusion_mcp_execute",
            {
                "featureType": "script",
                "object": {"script": script},
            },
        )
        for block in result.get("content", []):
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                print(block["text"])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
