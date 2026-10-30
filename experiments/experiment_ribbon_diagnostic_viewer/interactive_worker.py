"""
Reject historical worker plans after removal of diagnostic path search.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .procedures import DISCOVERY_REMOVED, selections


def run(directory: Path) -> Path:
    """
    Reject stale jobs without altering their inputs, plans or recorded evidence.
    """
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    selections(plan["procedures"])
    raise ValueError(DISCOVERY_REMOVED)


if __name__ == "__main__":
    run(Path(sys.argv[1]))
