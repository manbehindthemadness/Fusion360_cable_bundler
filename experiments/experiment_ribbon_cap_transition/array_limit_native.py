"""
Schedule the approved three-family certificate-limit construction diagnostic.

At most72 certificate probes, three solves/builds,120 seconds per case,2GiB RSS.
Preserve all warnings, documents and failures; no tuning or native retries.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint

from .array_fixtures import array_fixtures
from .array_limits import scaled_case, select_scale
from .array_native import ArrayBatch, _checkpoint
from .native import NativeGeometryPolicy, NativeProcedure, _run_case
from .native_budget import NativeBudget
from .planning import ShortConnectionFixture, freeze_targets
from .screen import _fingerprints, _fits

DOCUMENT_NAMES = (
    "Tube ribbon limit - 1 U-turn 360",
    "Tube ribbon limit - 2 spatial S 360",
    "Tube ribbon limit - 3 orthogonal bends 360",
)
ARRAY_NAME = "Tube ribbon 4x - certificate-limit 360 array"
_state: ArrayBatch | None = None


def _freeze() -> ArrayBatch:
    """
    Register parents and limits before probing; freeze all targets before any solve.

    Authoring exceptions are deliberately recorded without native scheduling;
    historical artifacts and source documents are never overwritten or closed.
    """
    started = perf_counter()
    parents = array_fixtures()
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/array_native" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    sources, production = _fingerprints(), verify_sources()
    state = ArrayBatch(
        directory,
        parents,
        sources,
        production,
        [
            {"case_id": item.case.name + "_certificate_limit", "status": "not_attempted"}
            for item in parents
        ],
        started,
    )
    plan = {
        "question": "Can the unchanged full-turn solver construct each uniformly tightened family at its input curve-certificate boundary?",
        "parents": [asdict(item) for item in parents],
        "sources": sources,
        "production": production,
        "limits": {
            "cases": 3,
            "certificate_probes_per_family": 24,
            "authoring_seconds_per_family": 10,
            "shape_solves": 3,
            "native_attempts": 3,
            "retries": 0,
            "case_seconds": 120,
            "batch_seconds": 390,
            "fusion_rss_kib": 2097152,
        },
        "authoring": "Uniform centerline scaling about fixed sphere center, fixed material/width directions/4x sphere; freeze newly positioned caps and connection targets upfront. Solver cannot reroute.",
        "certificate": "Unchanged curvature*enclosing reach <=0.8, depth16; finite passing/rejected bracket, not physical/native limit.",
        "authorization": "Three certificate-limit builds approved; warnings/findings non-blocking. No hidden repair or retries.",
        "stops": "Authoring error, incomplete native construction, host error, source drift, time/RSS caps.",
        "estimate": "About three minutes plus <=30s authoring, based on preceding 47-54s case diagnostics and12s display.",
        "retention": "Keep all documents including partial/empty; rigid array copies are not additional coverage.",
        "scope": "Three examined development families; no holdouts, generality or mechanical compliance claim.",
        "native_predictions": {row["case_id"]: "unknown" for row in state.rows},
        "selections": [],
        "inputs": [],
    }
    path = directory / "plan.json"

    def checkpoint_plan() -> None:
        """
        Retain every authoring selection and input before expensive construction.
        """
        path.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
        _checkpoint(state)

    checkpoint_plan()
    fixtures = []
    try:
        for parent in parents:
            selection = select_scale(parent.case)
            fixture = replace(
                parent, case=scaled_case(parent.case, selection.scale), parent_case=parent.case.name
            )
            fixtures.append(fixture)
            plan["selections"].append({"parent": parent.case.name, **asdict(selection)})
            fits = _fits(fixture.case)
            targets = freeze_targets(
                fixture.case, *fits, fixture=ShortConnectionFixture(fixture.case, turn_degrees=15)
            )
            plan["inputs"].append(
                {
                    "fixture": asdict(fixture),
                    "caps": [asdict(fit) for fit in fits],
                    "targets": asdict(targets),
                }
            )
            checkpoint_plan()
    except Exception as error:
        state.stop_reason = f"Certificate authoring error: {type(error).__name__}: {error}"
        checkpoint_plan()
        raise
    state.fixtures = tuple(fixtures)
    plan["matrix_sha256"] = matrix_fingerprint(tuple(item.case for item in fixtures))
    checkpoint_plan()
    return state


def run_next(_context: object) -> None:
    """
    Build one fixed case despite warnings; checkpoint and latch incomplete/host errors.
    """
    global _state
    if _state is None:
        _state = _freeze()
    state = _state
    if state.stop_reason:
        raise RuntimeError(state.stop_reason)
    index = sum(row["status"] != "not_attempted" for row in state.rows)
    if index >= 3:
        raise RuntimeError("Certificate-limit scope exhausted; no retries.")
    remaining = 390 - (perf_counter() - state.started)
    if remaining <= 0 or _fingerprints() != state.sources or verify_sources() != state.production:
        state.stop_reason = "Certificate-limit cap or source drift."
        _checkpoint(state)
        raise RuntimeError(state.stop_reason)
    fixture, row = state.fixtures[index], state.rows[index]
    row["status"] = "started"
    _checkpoint(state)
    try:
        directory = _run_case(
            fixture.case,
            DOCUMENT_NAMES[index],
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE_FULL_TURN,
            sphere_diameter_widths=4.0,
            geometry_policy=NativeGeometryPolicy.OBSERVE_REJECTIONS,
            budget=NativeBudget(maximum_seconds=min(120.0, remaining)),
            fixture_authoring={
                "parent_case": fixture.parent_case,
                "batch_plan": str(state.directory / "plan.json"),
                "boundary_note": "Uniformly tightened certificate-boundary inputs and exact targets frozen before all native attempts.",
            },
        )
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(directory), result=result)
        if result["built"] != 1:
            state.stop_reason = (
                "Incomplete certificate-limit construction; remaining cases not attempted."
            )
    except Exception as error:
        row.update(status="error", error=f"{type(error).__name__}: {error}")
        state.stop_reason = "Certificate-limit host error; remaining cases not attempted."
        raise
    finally:
        _checkpoint(state)
    print(
        json.dumps(
            {
                "directory": str(state.directory),
                "case": fixture.case.name,
                "built": result["built"],
                "stop": state.stop_reason,
            }
        )
    )


def show_array(_context: object) -> None:
    """
    Assemble retained rigid display copies only after all three complete builds.
    """
    if (
        _state is None
        or _state.stop_reason
        or any(row["status"] != "completed" for row in _state.rows)
    ):
        raise RuntimeError("Certificate-limit batch incomplete; no display assembly.")
    if _fingerprints() != _state.sources or verify_sources() != _state.production:
        raise RuntimeError("Certificate-limit source drift; no display assembly.")
    remaining = 390 - (perf_counter() - _state.started)
    if remaining <= 0:
        raise RuntimeError("Certificate-limit cap; documents retained.")
    from .array_display import create_array

    create_array(
        DOCUMENT_NAMES,
        tuple(item.case.end_boundary.center for item in _state.fixtures),
        _state.directory,
        NativeBudget(maximum_seconds=remaining),
        array_name=ARRAY_NAME,
    )
