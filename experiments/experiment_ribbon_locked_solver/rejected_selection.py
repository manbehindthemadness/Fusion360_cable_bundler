"""
Select one provenance-preserving rejected inspection route for both native and diagnostic views.
"""

from __future__ import annotations

from typing import Any

from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


def select(
    payload: dict[str, Any], expected_case: dict[str, Any]
) -> tuple[FoldRoute, dict[str, Any]]:
    """
    Prefer an explicit rejected final result; use shortest early branch only for legacy records.

    Validate every retained route against exact fixed targets, including unselected
    branches. A malformed explicit result fails rather than silently substituting
    another path. Neither selection grants acceptance or a contact certificate.
    """
    branches = payload.get("branches")
    if not isinstance(branches, list) or len(branches) > 8:
        raise ValueError("Rejected inspection needs at most eight original branches")
    records = list(branches)
    explicit = "selected_result" in payload
    if explicit:
        result = payload["selected_result"]
        if (
            not isinstance(result, dict)
            or result.get("kind") != "final_solver_candidate"
            or result.get("accepted") is not False
        ):
            raise ValueError("Rejected final result needs explicit candidate provenance")
        records.append(result)
    if not records:
        raise ValueError("Rejected inspection has no recorded route")
    restored: list[tuple[FoldRoute, dict[str, Any]]] = []
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("route"), dict)
            or not isinstance(record.get("disposition"), str)
            or not record["disposition"].strip()
        ):
            raise ValueError("Rejected inspection lacks its exact route and disposition")
        route = restore(record["route"])
        if snapshot(route)["case"] != expected_case:
            raise ValueError("Rejected inspection differs from the fixed targets")
        restored.append((route, record))
    return restored[-1] if explicit else min(restored, key=lambda item: item[0].material_length_mm)


def describe(record: dict[str, Any]) -> str:
    """
    Label final-candidate provenance distinctly from historical algebraic branch roots.
    """
    source = (
        "final solver candidate"
        if record.get("kind") == "final_solver_candidate"
        else f"roots {record['roots']}"
    )
    return f"{source} · {record['disposition']}"
