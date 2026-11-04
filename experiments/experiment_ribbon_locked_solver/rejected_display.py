"""
Expose recorded closed branches for inspection without authorizing native construction.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.inspection.archive import (
    RuleObservation,
    canonical,
    snapshot_payload,
    write_document,
)
from experiments.experiment_ribbon_contraction.runner import restore

from .inspection import freeze


def retain(
    method: dict[str, Any],
    trials: Path,
    destination: Path,
    targets: Targets,
    checkpoint: Callable[[], None],
) -> int:
    """
    Freeze up to eight recorded closed branches and their original contact dispositions.

    No solve, contact retry or native-ready route is produced. Missing closed geometry
    stays unavailable. The shortest recorded branch is the initial display; history
    retains original branch order, including branches whose contact was unattempted.
    """
    started = perf_counter()
    if not trials.exists():
        return 0
    if trials.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("Rejected-route ledger exceeds256MiB")
    branches: dict[str, dict[str, Any]] = {}
    with trials.open("rb") as stream:
        while line := stream.readline(4 * 1024 * 1024 + 1):
            checkpoint()
            if len(line) > 4 * 1024 * 1024 or not line.endswith(b"\n"):
                raise ValueError("Oversized or interrupted rejected-route event")
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("Rejected-route event must be an object")
            key = canonical(event.get("roots"))
            if event.get("stage") == "feature_branch" and event.get("status") == "closed":
                roots, geometry = event.get("roots"), event.get("route")
                if (
                    not isinstance(roots, list)
                    or not roots
                    or any(type(root) is not int or root < 0 for root in roots)
                    or not isinstance(geometry, dict)
                    or not {"case", "pieces"} <= geometry.keys()
                ):
                    raise ValueError("Closed branch lacks its recorded roots/geometry")
                if key in branches or len(branches) >= 8:
                    raise ValueError("Duplicate or excessive rejected branches")
                route = restore(geometry)
                if route.targets != targets:
                    raise ValueError("Rejected geometry differs from the fixed targets")
                branches[key] = {
                    "roots": event.get("roots"),
                    "route": event["route"],
                    "length_mm": route.material_length_mm,
                    "disposition": "contact unattempted",
                }
            elif (
                event.get("stage") == "feature_contact"
                and event.get("status") != "started"
                and key in branches
            ):
                branches[key].update(disposition=event["status"], contact=event.get("contact"))
    if not branches:
        return 0
    selected = min(branches, key=lambda branch_key: branches[branch_key]["length_mm"])
    selected_snapshot = None
    with (destination / "rejected-history.jsonl").open("x") as history:
        for sequence, (key, branch) in enumerate(branches.items()):
            checkpoint()
            frozen = snapshot_payload(freeze(restore(branch["route"]), method["id"]))
            history.write(
                canonical(
                    {
                        "kind": "path",
                        "sequence": sequence,
                        "solver": method["id"],
                        "stage": f"NOT ACCEPTED: roots {branch['roots']} · {branch['disposition']}",
                        "snapshot": frozen,
                    }
                )
                + "\n"
            )
            if key == selected:
                selected_snapshot = frozen
    write_document(destination / "rejected-geometry.json", {"branches": list(branches.values())})
    branch = branches[selected]
    method.update(
        label=method["label"] + " — rejected geometry",
        detail=method["detail"]
        + f" Diagnostic scaffold only; NOT ACCEPTED, no native build. Showing roots {branch['roots']}: {branch['disposition']}. All {len(branches)} recorded branches are available in history.",
        history="rejected-history.jsonl",
        snapshot=selected_snapshot,
        diagnostic_geometry_seconds=perf_counter() - started,
    )
    method["rules"].append(
        asdict(
            RuleObservation(
                "Rejected diagnostic geometry",
                "warning",
                "Display interpolation of recorded closed branches only; contact failures and incomplete measurements remain unresolved. No acceptance or physical compliance is implied.",
            )
        )
    )
    return len(branches)
