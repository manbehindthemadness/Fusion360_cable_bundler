"""
Replay six original packed complete ribbons with planar sections and bounded roll.

Original frozen scales, caps and targets are verified, not re-searched. Stop at
the first incomplete construction, source drift, host failure or resource cap.
Historical reports and retained user documents are never overwritten or closed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources

from .array_limits import scaled_case
from .bounded_twist import shortest_twist
from .faith_fixtures import FaithFixture, faith_fixtures
from .native import NativeGeometryPolicy, NativeProcedure, _run_case
from .native_budget import NativeBudget
from .planning import ShortConnectionFixture, freeze_targets
from .prescribed_twist import PrescribedTwistDiagnostic
from .screen import _fingerprints, _fits

PARENT = (
    PROJECT_ROOT
    / "artifacts/verification/ribbon_cap_transition/faith_native/435bedfe25f245cc86db435fc01dddf0/plan.json"
)
ARRAY_NAME = "Tube ribbon 4x - planar bounded twist replay"
_state: dict[str, object] | None = None
_fixtures: tuple[FaithFixture, ...] = ()
_directory: Path | None = None
_started = 0.0


def _json_value(value: object) -> object:
    """
    Match the original report representation of dataclasses, UUIDs and enums.
    """
    return json.loads(json.dumps(value, default=str))


def _checkpoint() -> None:
    """
    Retain all six dispositions and write only this replay's new evidence.
    """
    if _state is None or _directory is None:
        raise RuntimeError("Replay not initialized.")
    _state["elapsed_seconds"] = perf_counter() - _started
    (_directory / "report.json").write_text(json.dumps(_state, indent=2), encoding="utf-8")


def _start() -> None:
    """
    Freeze the hypothesis and verify all original inputs before native scheduling.
    """
    global _state, _directory, _started, _fixtures
    _started = perf_counter()
    parent_bytes = PARENT.read_bytes()
    parent = json.loads(parent_bytes)
    originals = faith_fixtures()
    if _json_value([asdict(item) for item in originals]) != parent["parents"]:
        raise RuntimeError("Original parent fixtures changed; no native scheduling.")
    inputs: list[dict[str, object]] = []
    selected: list[FaithFixture] = []
    for item, selection, frozen in zip(originals, parent["selections"], parent["inputs"]):
        case = scaled_case(item.case, selection["scale"])
        original = replace(item, case=case)
        fits = _fits(case)
        targets = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        replay = {
            "fixture": asdict(original),
            "caps": [asdict(f) for f in fits],
            "targets": asdict(targets),
        }
        if _json_value(replay) != frozen:
            raise RuntimeError("Original selected curve/caps/targets changed; no build.")
        bounded = replace(original, twist_degrees=shortest_twist(item.twist_degrees))
        selected.append(bounded)
        inputs.append(
            {
                "original_twist_degrees": item.twist_degrees,
                "bounded_twist_degrees": bounded.twist_degrees,
                **replay,
            }
        )
    if len(selected) != 6:
        raise RuntimeError("Original matrix incomplete; no native scheduling.")
    _fixtures = tuple(selected)
    _directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/bounded_twist" / uuid4().hex
    )
    _directory.mkdir(parents=True, exist_ok=False)
    plan = {
        "question": "Do the original six packed layouts construct with undeformed planar sections and endpoint-equivalent roll in [-180,180]?",
        "parent_plan": str(PARENT),
        "parent_sha256": hashlib.sha256(parent_bytes).hexdigest(),
        "inputs": inputs,
        "sources": _fingerprints(),
        "production": verify_sources(),
        "procedure": "Fixed original certificate-selected centerlines;32 planar original lobe sections;shared exact caps, same reverse-loft endings;quintic bounded signed roll;no section flex, searches, target changes or fallback.",
        "policy_revision": "User-directed no-section-deformation experiment supersedes three-anchor flex only for this replay. Half-turn ties retain sign;modulo360 preserves ordered endpoint orientation, not physical winding. Existing bank-rate diagnostic exception retained;180 is total prescribed roll, not a native per-span certificate.",
        "native_prediction": "All six predicted complete builds; hypothesis only, stop first incomplete result.",
        "limits": {
            "cases": 6,
            "shape_solves": 6,
            "native_attempts": 6,
            "search_probes": 0,
            "retries": 0,
            "case_seconds": 120,
            "batch_seconds": 840,
            "display_seconds": 60,
            "rss_kib": 2097152,
        },
        "authorization": "User approved six cases,120s each,14min overall,2GiB,first construction failure stop.",
        "retention": "Leave new array and existing failure/pilot open;archive and close only newly created successful scratch after rigid display copy;failed scratch retained.",
        "timing": "Original scale replay excludes certificate search;shape solve rechecks input certificate. Native,diagnostic audit,display and overall timings separate.",
        "coverage": "Six examined development configurations;no untouched holdouts or production-readiness claim;4x historical sphere,not3x or5x evidence.",
    }
    (_directory / "plan.json").write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
    _state = {
        "plan": _json_value(plan),
        "planned": 6,
        "cases": [{"case_id": f.case.name, "status": "not_attempted"} for f in _fixtures],
        "stop_reason": None,
        "display_seconds": 0.0,
        "array_started": False,
        "finished": False,
        "preparation_seconds": perf_counter() - _started,
    }
    _checkpoint()


def _budget(stage_seconds: float) -> NativeBudget:
    """
    Guard source/parent integrity and scheduling limits between host operations.
    """
    if _state is None:
        raise RuntimeError("Replay not initialized.")
    plan = _state["plan"]
    remaining = 840 - (perf_counter() - _started)
    if (
        remaining <= 0
        or _fingerprints() != plan["sources"]
        or verify_sources() != plan["production"]
        or hashlib.sha256(PARENT.read_bytes()).hexdigest() != plan["parent_sha256"]
    ):
        raise RuntimeError("Replay scheduling cap or source/input drift; no further builds.")
    budget = NativeBudget(maximum_seconds=min(stage_seconds, remaining))
    budget.check("between_operations")
    return budget


def run_next(_context: object) -> None:
    """
    Attempt one complete ribbon, recording failures without a retry or rollback.

    Broad exception handling intentionally preserves diagnostics at this host
    boundary; any harness error latches a stop and leaves partial geometry open.
    """
    if _state is None:
        _start()
    if _state is None or _directory is None:
        raise RuntimeError("Replay initialization failed.")
    if _state["stop_reason"] or _state["finished"]:
        raise RuntimeError("Replay stopped or finished; no retries.")
    rows = _state["cases"]
    index = sum(row["status"] != "not_attempted" for row in rows)
    if index >= 6:
        raise RuntimeError("All six cases already attempted.")
    row = rows[index]
    try:
        from .faith_display import append_and_close, start_array

        if not _state["array_started"]:
            display_started = perf_counter()
            start_array(_budget(60), array_name=ARRAY_NAME)
            _state["display_seconds"] += perf_counter() - display_started
            _state["array_started"] = True
        fixture = _fixtures[index]
        name = f"Bounded tube replay {index + 1} - {fixture.twist_degrees:g}deg"
        row["status"] = "started"
        _checkpoint()
        directory = _run_case(
            fixture.case,
            name,
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE_SHARED_CAPS,
            geometry_policy=NativeGeometryPolicy.OBSERVE_REJECTIONS,
            sphere_diameter_widths=4.0,
            twist_policy=PrescribedTwistDiagnostic(fixture.twist_degrees),
            budget=_budget(120),
            fixture_authoring={
                "parent_case": fixture.case.name,
                "batch_plan": str(_directory / "plan.json"),
                "purpose": "Original geometry replay, no section warp, bounded twist only.",
            },
        )
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(directory), result=result)
        if result["built"] != 1:
            _state["stop_reason"] = (
                "First incomplete native construction; remaining cases not attempted."
            )
        else:
            started = perf_counter()
            row["display"] = append_and_close(
                name,
                fixture.case.end_boundary.center,
                index,
                directory,
                _budget(60 - _state["display_seconds"]),
                array_name=ARRAY_NAME,
            )
            duration = perf_counter() - started
            row["display_seconds"] = duration
            _state["display_seconds"] += duration
    except Exception as error:
        row.update(status="error", error=f"{type(error).__name__}: {error}")
        _state["stop_reason"] = row["error"]
    finally:
        _checkpoint()
    print(
        json.dumps(
            {
                "directory": str(_directory),
                "case": row["case_id"],
                "status": row["status"],
                "built": row.get("result", {}).get("built"),
                "stop": _state["stop_reason"],
            }
        )
    )


def finish(_context: object) -> None:
    """
    Archive and focus the complete or stopped array without altering old evidence.
    """
    if _state is None or _directory is None or not _state["array_started"] or _state["finished"]:
        raise RuntimeError("No unfinished replay array.")
    if not _state["stop_reason"] and any(
        row["status"] == "not_attempted" for row in _state["cases"]
    ):
        raise RuntimeError("Approved cases remain.")
    from .faith_display import finish_array

    started = perf_counter()
    finish_array(_directory, _budget(60 - _state["display_seconds"]), array_name=ARRAY_NAME)
    _state["display_seconds"] += perf_counter() - started
    _state["finished"] = True
    _checkpoint()
    print(json.dumps({"directory": str(_directory), "stop": _state["stop_reason"]}))
