"""
Run a frozen forward-transport matrix and draw numbered native reference paths.

This tests a representation across prescribed fields,not endpoint-first routing.
Existing scratch candidates and all earlier outcomes remain untouched.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, unit
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import coupled_native, edge_interpolation_native, event_display
from .director_audit import measure
from .director_fields import development, rejection_controls, validation
from .director_transport import DirectorPath, integrate

# noinspection PyProtectedMember
from .edge_display import _curve
from .edge_native_checks import audit_curves
from .endpoint_first import EndpointCase
from .native_budget import NativeBudget

NAME = "Material directors - forward benchmarks75-87"
_state: dict[str, Any] | None = None
_paths: list[DirectorPath] = []


def _case(path: DirectorPath) -> EndpointCase:
    """
    Author reference terminal guides before the lower-resolution transport test.

    Field-defined endpoints are fixtures rather than discovered target solutions.
    Tiny reference frame drift is measured before unit guide axes are authored.
    """
    first, _ = path.pose(0)
    last, _ = path.pose(1)
    field = path.field
    return EndpointCase(
        field.name,
        Vector3(*first[:3]),
        Vector3(*last[:3]),
        unit(Vector3(*first[3:6])),
        unit(Vector3(*last[3:6])),
        unit(Vector3(*first[6:9])),
        unit(Vector3(*last[6:9])),
        field.lines,
        field.diameter_mm,
    )


def _sources() -> dict[str, str]:
    """
    Freeze direct transport,display,audit and host-budget dependencies before work.
    """
    names = (
        "director_fields.py",
        "director_transport.py",
        "director_audit.py",
        "director_native.py",
        "edge_display.py",
        "edge_interpolation.py",
        "edge_native_checks.py",
        "native_budget.py",
        "coupled_native.py",
        "event_display.py",
    )
    paths = [Path(__file__).with_name(name) for name in names]
    paths.extend(
        PROJECT_ROOT / path
        for path in (
            "cable_bundler/routing/geometry.py",
            "experiments/experiment_ribbon_diagnosis/storage.py",
        )
    )
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def _draw_lane(component: Any, path: DirectorPath, name: str, offset: float) -> None:
    """
    Bind one fixture's path and offset before synchronous native authoring.
    """

    def jet(u: float) -> tuple[Vector3, Vector3]:
        """
        Evaluate the actual interpolated material-lane position and velocity.
        """
        return path.lane(u, offset)

    _curve(component, name, jet, 512)


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Test7development+4one-usevalidation+2rejection fields with unchanged settings.

    RK4grids256and512,259off-node/end samples;512reference authors guide targets
    before256transport. Each path is one prescribed-field fixture,not a route
    solve. Native kernel predictions unknown;curvature/sphere policies measured
    separately from numerical accuracy. Draw all13centers;A/B companions only
    when sampled J>0. Three-path native audits run for the11positive fixtures;
    invalid controls explicitly skip native compliance after their rejection.
    Limits:10s total numerical including fixture authoring,30s draw,10s native
    audit,60s overall/2GiB sampledRSS.0solids/search/retries/reportfiles.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Director matrix already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    previous = edge_interpolation_native._state
    if (
        design is None
        or app.userInterface.activeCommand != "SelectCommand"
        or previous is None
        or previous["stop_reason"]
    ):
        raise RuntimeError("Expected idle retained scratch with interpolation baseline.")
    root = design.rootComponent
    if (
        root.occurrences.count != 11
        or root.occurrences.item(10).component.name != edge_interpolation_native.NAME
    ):
        raise RuntimeError("Expected eleven retained arrays.")
    groups = (
        ("development", development()),
        ("validation", validation()),
        ("rejection", rejection_controls()),
    )
    fields = tuple(field for _, items in groups for field in items)
    phases = tuple(phase for phase, items in groups for _ in items)
    sources = _sources()
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "material-director-RK4-Hermite-v1",
            "sources": sources,
            "fields": [asdict(field) for field in fields],
            "phases": phases,
            "hypothesis": "Material-frame transport retains bending reversals and neutral runs without Frenet division,across distinct prescribed fields.",
            "procedure": "All cases:512reference authoring before256transport;259off-node/end audits;512native Hermite intervals;1535native samples/path.",
            "limits": "13fields;0route solves/search/solids/retries/reports;10s numerical/30s draw/10s nativeaudit/60s overall/2GiBRSS",
            "tolerances": {
                "position_convergence_mm": 0.005,
                "frame_drift": 1e-6,
                "metric": 1e-5,
                "wide_bend_per_mm": 1e-6,
            },
            "policy": "Existing center.8,lane radius3diameters,sphere diameter5nominalwidth;uncalibrated for real material;length mechanical goal,no repair.",
            "native_prediction": "unknown for every path;no complete-ribbon build prediction",
            "scope": "Forward field/fixture tests,not fixed-target routing,equilibrium,physical photo reconstruction or complete cable/split validation.",
            "validation_policy": "Four reserved fields evaluated once after method/source freeze;no adaptation after development results.",
        },
        "rows": [
            {
                "number": 75 + i,
                "case": f.name,
                "phase": phases[i],
                "evaluated": False,
                "drawn": False,
                "native_audit": "unattempted",
                "overall": "unresolved",
            }
            for i, f in enumerate(fields)
        ],
        "stop_reason": None,
    }
    _state = state
    stage_started = perf_counter()
    stage_cap = 10.0
    last_memory = stage_started

    def checkpoint() -> None:
        """
        Enforce stage time with frequent checks and quarter-second RSS sampling.
        """
        nonlocal last_memory
        now = perf_counter()
        if now - stage_started >= stage_cap:
            raise RuntimeError("Director matrix stage time cap reached.")
        if now - last_memory >= 0.25:
            budget.check("director_stage")
            last_memory = now

    try:
        numerical_started = perf_counter()
        references = []
        targets = []
        for field, row in zip(fields, state["rows"]):
            started = perf_counter()
            reference = integrate(field, 512, checkpoint)
            references.append(reference)
            targets.append(_case(reference))
            row["fixture_authoring_seconds"] = perf_counter() - started
        state["plan"]["authored_targets"] = [asdict(case) for case in targets]
        for field, reference, row in zip(fields, references, state["rows"]):
            if _sources() != sources:
                raise RuntimeError("Director source drift.")
            started = perf_counter()
            path = integrate(field, 256, checkpoint)
            _paths.append(path)
            row["transport_seconds"] = perf_counter() - started
            started = perf_counter()
            row.update(measure(path, reference, checkpoint))
            row["reference_audit_seconds"] = perf_counter() - started
            row["evaluated"] = True
            if row["numerical_findings"]:
                raise RuntimeError("Director numerical regression:" + field.name)
            if row["phase"] == "rejection":
                expected = (
                    "sampled material map folds"
                    if field.name.startswith("I01")
                    else "current curvature policy rejected"
                )
                row["expected_rejection_detected"] = expected in row["policy_findings"]
                if not row["expected_rejection_detected"]:
                    raise RuntimeError("Missed director rejection control:" + field.name)
            row["overall"] = (
                "policy rejected"
                if row["policy_findings"]
                else "sampled reference gates pass;full compliance unresolved"
            )
        state["numerical_seconds"] = perf_counter() - numerical_started
        checkpoint()
        stage_started = perf_counter()
        stage_cap = 30.0
        pitch = 94.17185167125959
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(0, -19 * pitch, 0)
        array = root.occurrences.addNewComponent(transform).component
        array.name = NAME
        components = []
        for i, (path, case, row) in enumerate(zip(_paths, targets, state["rows"])):
            checkpoint()
            if _sources() != sources:
                raise RuntimeError("Director drawing source drift.")
            started = perf_counter()
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(i % 4 * pitch, -(i // 4) * pitch, 0)
            component = array.occurrences.addNewComponent(placement).component
            components.append(component)
            component.name = f"{75 + i:02d} - {path.field.name} - {row['overall']}"
            coupled_native._guides(component, case)

            _draw_lane(component, path, "Derived center", 0)
            if row["minimum_material_jacobian"] > 0:
                _draw_lane(component, path, "A boundary", path.field.half_width_mm)
                _draw_lane(component, path, "Derived B boundary", -path.field.half_width_mm)
            label = component.sketches.add(component.xYConstructionPlane)
            label.name = f"{75 + i:02d} - forward benchmark status"
            event_display._text(label, f"{75 + i:02d}", -3, -5, 0.9)
            caption = "FORWARD FIELD - " + row["phase"].upper()
            event_display._text(label, caption, -3, -7, 0.3)
            label.isLightBulbOn = True
            row.update(drawn=True, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - stage_started
        checkpoint()
        stage_started = perf_counter()
        stage_cap = 10.0
        for component, case, row in zip(components, targets, state["rows"]):
            checkpoint()
            if row["phase"] == "rejection":
                row["native_audit"] = "skipped:rejection diagnostic only"
                continue
            row["native_curves"] = []
            started = perf_counter()
            audit_curves(component, case, 512, checkpoint, row["native_curves"])
            row["native_audit_seconds"] = perf_counter() - started
            if len(row["native_curves"]) != 3:
                raise RuntimeError("Missing native director paths.")
            findings = []
            for curve in row["native_curves"]:
                if curve["minimum_radius_mm"] < 3 * case.diameter_mm:
                    findings.append("native radius policy rejected")
                if curve["occupied_sphere_reach_mm"] > row["sphere_radius_mm"]:
                    findings.append("native sphere policy rejected")
                if curve["center_ratio"] is not None and curve["center_ratio"] > 0.8:
                    findings.append("native center policy rejected")
                if curve["endpoint_error_mm"] > 0.005:
                    findings.append("native fixture convergence tolerance exceeded")
            row["native_findings"] = sorted(set(findings))
            row["native_audit"] = (
                "named sampled policies rejected"
                if findings
                else "named sampled curve checks pass;full compliance unresolved"
            )
        state["native_audit_seconds"] = perf_counter() - stage_started
        checkpoint()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/directors" / uuid4().hex
        )
        directory.mkdir(parents=True)
        app.activeViewport.fit()
        app.activeViewport.refresh()
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Director matrix image export failed.")
        state.update(
            directory=str(directory),
            archive_seconds=perf_counter() - started,
            display_pitch_cm=pitch,
        )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state["overall_seconds"] = perf_counter() - budget.started
    state["maximum_sampled_rss_kib"] = max(cast(int, s["rss_kib"]) for s in budget.samples)
    return state
