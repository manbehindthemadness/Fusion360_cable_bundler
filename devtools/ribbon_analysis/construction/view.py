"""
Export a self-contained offline viewer; no network, solver or playback-time geometry evaluation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .journal import load
from .records import canonical


def export(journal_path: Path, destination: Path) -> Path:
    """
    Embed validated frozen records and bundled presentation code in a new HTML artifact.

    Escaping HTML-significant characters prevents recorded labels from terminating
    the data script. The viewer inserts labels with textContent, never innerHTML.
    Existing artifacts are never replaced.
    """
    packet = load(journal_path)
    packet["fingerprint"] = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    directory = Path(__file__).parent
    data = canonical(packet).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    page = (directory / "viewer.html").read_text(encoding="utf-8")
    page = page.replace(
        "/*CONSTRUCTION_STYLE*/", (directory / "viewer.css").read_text(encoding="utf-8")
    )
    page = page.replace('"CONSTRUCTION_DATA"', data)
    page = page.replace(
        "/*CONSTRUCTION_SCRIPT*/", (directory / "viewer.js").read_text(encoding="utf-8")
    )
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(page)
    return destination
