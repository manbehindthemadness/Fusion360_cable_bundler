"""
Retain small exact input recipes and recreate endpoint-only inspection documents.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym.handoff import validate as validate_gym
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.inspection.archive import SCHEMA
from devtools.ribbon_analysis.inspection.values import finite_number, json_object
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy
from experiments.experiment_ribbon_locked_solver.settings import Settings


def targets(payload: Any) -> Targets:
    """
    Validate complete exact ordered poses without fitting or regenerating their coordinates.
    """
    data = dict(json_object(payload))
    if set(data) != {field.name for field in fields(Targets)}:
        raise ValueError("Supply complete exact endpoint targets")
    for name in ("start", "end", "start_tangent", "end_tangent", "start_width", "end_width"):
        coordinates = json_object(data[name])
        if set(coordinates) != {"x", "y", "z"}:
            raise ValueError("Supply complete XYZ endpoint vectors")
        data[name] = Vector3(*(finite_number(coordinates[axis]) for axis in "xyz"))
    data["diameter_mm"] = finite_number(data["diameter_mm"])
    return Targets.capture(Targets(**data))


def scene(recipe: dict[str, Any]) -> Scene:
    """
    Reconstruct only input layout controls, never a solved route or Fusion object.
    """
    try:
        return Scene(
            Config(**json_object(recipe["config"])),
            Goal(**json_object(recipe["a"])),
            Goal(**json_object(recipe["b"])),
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Supply complete gym configuration and ordered goals") from error


def validate(recipe: Any) -> dict[str, Any]:
    """
    Accept only compact input controls, fixed targets and original solver settings.

    No drawing, station, mesh, body, saved route or solver-result field is
    accepted. Keep original JSON coordinates; validation supplies no feasibility.
    """
    data = json_object(recipe)
    if set(data) != {"config", "a", "b", "targets", "solver_version", "settings", "policy"}:
        raise ValueError("A case recipe contains input values only")
    layout = scene(data)
    fixed = targets(data["targets"])
    if (layout.config.lines, layout.config.diameter_mm) != (fixed.lines, fixed.diameter_mm):
        raise ValueError("Gym dimensions and fixed targets disagree")
    if not isinstance(data["solver_version"], str) or not data["solver_version"].strip():
        raise ValueError("Retain the original solver version")
    Settings.parse(data["settings"])
    policy = json_object(data["policy"])
    if set(policy) != {"native_point_tolerance_mm", "contact_measurement_policy", "limits"}:
        raise ValueError("Retain original measurement policy and resource limits")
    ContactPolicy(policy["contact_measurement_policy"])
    if finite_number(policy["native_point_tolerance_mm"]) <= 0:
        raise ValueError("Retain positive native point tolerance")
    limits = json_object(policy["limits"])
    if set(limits) != {"launch_rss_kib", "native_seconds", "numerical_seconds", "rss_bytes"} or any(
        finite_number(value) <= 0 for value in limits.values()
    ):
        raise ValueError("Retain complete positive original resource limits")
    if limits["launch_rss_kib"] * 1024 > limits["rss_bytes"]:
        raise ValueError("Launch headroom exceeds the memory limit")
    return data


def from_plan(plan: Any) -> dict[str, Any]:
    """
    Extract selected original values, discarding all generated geometry and source listings.
    """
    payload = json_object(plan)
    gym = json_object(payload.get("gym"))
    if gym.get("targets") != payload.get("targets"):
        raise ValueError("Original gym and exact solver targets disagree")
    return validate(
        {
            "config": gym.get("config"),
            "a": gym.get("a"),
            "b": gym.get("b"),
            "targets": payload.get("targets"),
            "solver_version": payload.get("version"),
            "settings": payload.get("settings"),
            "policy": {
                "native_point_tolerance_mm": payload.get("native_point_tolerance_mm"),
                "contact_measurement_policy": payload.get("contact_measurement_policy"),
                "limits": payload.get("limits"),
            },
        }
    )


def inspection_document(
    identifier: str, recipe: dict[str, Any], provenance: dict[str, Any]
) -> dict[str, Any]:
    """
    Recreate a labelled endpoint-only diagnostic while preserving every saved target exactly.

    Generator drift beyond the existing input-handoff tolerance stops export;
    fixed poses are never moved to fit a newer generator. No solver is run.
    """
    data = validate(recipe)
    gym = scene(data).payload()
    gym["targets"] = data["targets"]
    checked = validate_gym(gym, targets(data["targets"]))
    assert checked is not None
    return {
        "schema": SCHEMA,
        "targets": data["targets"],
        "gym": checked,
        "diagnostic_replay": {
            "case_id": identifier,
            "fresh_validation": False,
            "provenance": provenance,
            "original_solver": {"version": data["solver_version"], "settings": data["settings"]},
            "original_policy": data["policy"],
        },
        "solvers": [
            {
                "id": "input",
                "label": "Selected diagnostic replay — not fresh validation",
                "source": identifier,
                "status": "not_run",
                "detail": "Endpoint-only reconstruction; no solver or native build attempted.",
                "rules": [],
            }
        ],
    }
