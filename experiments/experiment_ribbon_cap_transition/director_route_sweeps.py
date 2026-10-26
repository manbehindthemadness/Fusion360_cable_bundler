"""
Construct three preselected frozen route trunks with one sweep per conductor.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, cast

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import CubicBezier, Vector3
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from . import director_route_display, director_route_trials
from .director_transport import DirectorPath
from .edge_interpolation import cubic_controls
from .endpoint_first import EndpointCase
from .endpoint_trace_paths import TracePath
from .native_budget import NativeBudget
from .trace_sweep_native import _author, _check_cap

_state: dict[str, Any] | None = None
NUMBERS = (97, 102, 104)


def _trace(path: DirectorPath, number: int, offset: float) -> TracePath:
    """
    Preserve the solved material lane's position and velocity in512cubic intervals.
    """

    def jet(u: float) -> tuple[Vector3, Vector3]:
        """
        Evaluate one immutable conductor offset without fitting or endpoint repair.
        """
        return path.lane(u, offset)

    controls, knots = cubic_controls(jet, 512)
    curves = tuple(CubicBezier(*controls[i : i + 4]) for i in range(0, len(controls) - 1, 3))
    return TracePath(number, curves, controls, knots)


# noinspection PyProtectedMember
def run(number: int, case: EndpointCase) -> dict[str, Any]:
    """
    Build each preselected trunk once,in order;97calibrates cost before102/104.

    Each is19circular conductor solids,not19independent ribbon configurations.
    Limits30s/case,90s summed work,2GiB sampledRSS;stop first incomplete outcome.
    Native prediction unknown. Check solid status,available feature health,ordered identity
    and both feature-provided planar caps against fixed inputs(1e-5mm/1e-7normal).
    No split endings,bonded insulation,fullvolume/contact/strain audit or reports.
    Authoring,kernel and cap audits timed separately;the solve is cached/excluded.
    Direct-mode Unknown health is unavailable,never a healthy classification.
    Continue97's preserved first solid without rebuilding it;retain the stopped
    calibration ledger in its original module before loading this continuation.
    """
    global _state
    baseline = director_route_display._state
    if baseline is None or baseline["stop_reason"] or number not in NUMBERS:
        raise RuntimeError("Expected completed frozen route display.")
    if _state is None:
        fingerprints = dict(baseline["plan"]["sources"])
        for name in ("director_route_sweeps.py", "trace_sweep_native.py", "endpoint_caps.py"):
            file = Path(__file__).with_name(name)
            fingerprints[str(file.relative_to(PROJECT_ROOT))] = hashlib.sha256(
                file.read_bytes()
            ).hexdigest()
        _state = {
            "plan": {
                "numbers": NUMBERS,
                "sources": fingerprints,
                "case_seconds": 30,
                "sum_seconds": 90,
                "rss_kib": 2 * 1024 * 1024,
                "health_policy": "Unknown allowed only for direct design with empty message;health unavailable",
                "continuation": "97reuses one preserved solid;102/104start empty",
            },
            "rows": [
                {"number": n, "native_prediction": "unknown", "attempted": False, "built": False}
                for n in NUMBERS
            ],
            "stop_reason": None,
        }
    state = cast(dict[str, Any], _state)
    if state["stop_reason"]:
        raise RuntimeError("Sweep stop latched:" + state["stop_reason"])
    pending = next((row for row in state["rows"] if not row["attempted"]), None)
    if pending is None:
        raise RuntimeError("All registered sweep cases were already attempted.")
    row = cast(dict[str, Any], pending)
    if row["number"] != number:
        raise RuntimeError("Expected next registered sweep case exactly once.")
    for name, digest in state["plan"]["sources"].items():
        if hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Sweep source drift before construction.")
    index = number - 88
    source = baseline["rows"][index]
    if not source["companions_allowed"] or source["native_findings"]:
        raise RuntimeError("Preselected path did not pass its frozen native checks.")
    if baseline["plan"]["inputs"][index] != asdict(case) or case.lines != 19:
        raise RuntimeError("Fixed nineteen-conductor target mismatch.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    component = (
        design.rootComponent.occurrences.item(12).component.occurrences.item(index).component
    )
    path = cast(DirectorPath, director_route_trials._paths[source["trial"]][source["index"]])
    budget = NativeBudget(maximum_seconds=30)
    row.update(
        case=case.name,
        attempted=True,
        traces_attempted=0,
        traces_built=0,
        caps_checked=0,
        path_seconds=0.0,
        authoring_seconds=0.0,
        kernel_seconds=0.0,
        cap_audit_seconds=0.0,
        unavailable_health_traces=[],
    )
    try:
        existing = 1 if number == 97 else 0
        if (
            component.bRepBodies.count != existing
            or component.features.sweepFeatures.count != existing
        ):
            raise RuntimeError("Unexpected existing solids before registered continuation.")
        if existing:
            previous = component.features.sweepFeatures.item(0)
            offset = -(case.lines - 1) * case.diameter_mm / 2
            if (
                not previous.bodies.item(0).isSolid
                or not _check_cap(
                    previous.startFaces,
                    case.start.translated(case.start_width, offset),
                    case.start_tangent,
                )
                or not _check_cap(
                    previous.endFaces, case.end.translated(case.end_width, offset), case.end_tangent
                )
            ):
                raise RuntimeError("Preserved first sweep failed continuation checks.")
            if (
                previous.healthState != adsk.fusion.FeatureHealthStates.UnknownFeatureHealthState
                or previous.errorOrWarningMessage
                or design.designType != adsk.fusion.DesignTypes.DirectDesignType
            ):
                raise RuntimeError("Preserved direct-mode health disposition changed.")
            previous.bodies.item(0).name = f"{number} - conductor 01"
            previous.bodies.item(0).attributes.add("director_route_experiment", "conductor", "1")
            row.update(reused_prior_solids=1, traces_built=1, caps_checked=2)
            row["unavailable_health_traces"].append(1)
        for i in range(existing, case.lines):
            budget.check("trace_plan")
            started = perf_counter()
            offset = (i - (case.lines - 1) / 2) * case.diameter_mm
            trace = _trace(path, i + 1, offset)
            row["path_seconds"] += perf_counter() - started
            started = perf_counter()
            try:
                profile, native_path = _author(component, trace, case)
                inputs = component.features.sweepFeatures.createInput(
                    profile, native_path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                )
                inputs.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
            finally:
                row["authoring_seconds"] += perf_counter() - started
            budget.check("trace_kernel")
            row["traces_attempted"] += 1
            started = perf_counter()
            try:
                feature = component.features.sweepFeatures.add(inputs)
            finally:
                row["kernel_seconds"] += perf_counter() - started
            if feature is None or feature.bodies.count != 1 or not feature.bodies.item(0).isSolid:
                raise RuntimeError("Native sweep did not produce one solid.")
            health = feature.healthState
            if (
                health == adsk.fusion.FeatureHealthStates.UnknownFeatureHealthState
                and design.designType == adsk.fusion.DesignTypes.DirectDesignType
                and not feature.errorOrWarningMessage
            ):
                row["unavailable_health_traces"].append(i + 1)
            elif health != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
                raise RuntimeError("Native sweep feature health:" + feature.errorOrWarningMessage)
            body = feature.bodies.item(0)
            body.name = f"{number} - conductor {i + 1:02}"
            body.attributes.add("director_route_experiment", "conductor", str(i + 1))
            row["traces_built"] += 1
            started = perf_counter()
            try:
                if not _check_cap(
                    feature.startFaces,
                    case.start.translated(case.start_width, offset),
                    case.start_tangent,
                ):
                    raise RuntimeError("Fixed start cap mismatch.")
                if not _check_cap(
                    feature.endFaces, case.end.translated(case.end_width, offset), case.end_tangent
                ):
                    raise RuntimeError("Fixed end cap mismatch.")
                row["caps_checked"] += 2
            finally:
                row["cap_audit_seconds"] += perf_counter() - started
            budget.check("trace_complete")
        row.update(
            built=True,
            audit="solid/identity/fixed caps pass;direct feature health unavailable;full compliance unresolved",
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
        row["error"] = str(error)
    row["seconds"] = perf_counter() - budget.started
    row["maximum_sampled_rss_kib"] = max(
        (cast(int, s["rss_kib"]) for s in budget.samples), default=None
    )
    state["seconds"] = sum(r.get("seconds", 0.0) for r in state["rows"])
    return state
