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
from .rejected_selection import describe, select


def retain(
    method: dict[str, Any],
    trials: Path,
    destination: Path,
    targets: Targets,
    checkpoint: Callable[[], None],
) -> int:
    """
    Freeze original branches plus an explicitly rejected final candidate when supplied.

    No solve, contact retry or native-ready route is produced. Missing closed geometry
    stays unavailable. Final solver provenance takes priority over an earlier short
    branch; legacy records retain their shortest-branch choice. Original branch
    order/dispositions remain in history, followed by the optional final candidate.
    """
    started = perf_counter()
    if not trials.exists():
        return 0
    if trials.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("Rejected-route ledger exceeds256MiB")
    branches: dict[str, dict[str, Any]] = {}
    final_result: dict[str, Any] | None = None
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
            elif event.get("stage") == "rejected_result":
                if (
                    final_result is not None
                    or event.get("status") != "not_accepted"
                    or not isinstance(event.get("route"), dict)
                    or not isinstance(event.get("reason"), str)
                    or not event["reason"].strip()
                ):
                    raise ValueError("Rejected final result needs one complete explicit record")
                final_result = {
                    "kind": "final_solver_candidate",
                    "accepted": False,
                    "route": event["route"],
                    "disposition": event["reason"],
                }
    if not branches and final_result is None:
        return 0
    payload: dict[str, Any] = {"branches": list(branches.values())}
    if final_result is not None:
        payload["selected_result"] = final_result
    _, selected = select(payload, asdict(targets))
    records = [*branches.values(), *([final_result] if final_result is not None else [])]
    selected_snapshot = None
    with (destination / "rejected-history.jsonl").open("x") as history:
        for sequence, branch in enumerate(records):
            checkpoint()
            frozen = snapshot_payload(freeze(restore(branch["route"]), method["id"]))
            history.write(
                canonical(
                    {
                        "kind": "path",
                        "sequence": sequence,
                        "solver": method["id"],
                        "stage": "NOT ACCEPTED: " + describe(branch),
                        "snapshot": frozen,
                    }
                )
                + "\n"
            )
            if branch is selected:
                selected_snapshot = frozen
    write_document(destination / "rejected-geometry.json", payload)
    method.update(
        label=method["label"] + " — rejected geometry",
        detail=method["detail"]
        + f" NOT ACCEPTED. Default inspection: {describe(selected)}. All {len(records)} recorded paths are available in history; native inspection does not imply acceptance.",
        history="rejected-history.jsonl",
        snapshot=selected_snapshot,
        diagnostic_geometry_seconds=perf_counter() - started,
    )
    method["rules"].append(
        asdict(
            RuleObservation(
                "Rejected diagnostic geometry",
                "warning",
                "Display interpolation of recorded rejected paths only; failures and incomplete measurements remain unresolved. No acceptance or physical compliance is implied.",
            )
        )
    )
    return len(records)
