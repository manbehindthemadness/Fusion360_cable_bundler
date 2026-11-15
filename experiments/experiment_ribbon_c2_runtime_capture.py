"""
Capture pinned C2numerical authoring in the idle Fusion runtime without CAD construction.

Requires Fusion's supplied adsk, the unchanged selected source and pinned3218..3222
experimental helpers. Invoke collect(name, started) through a read-only Fusion MCP
callback whose perf_counter start precedes importing this module. No kernel,
surface creation, native body, graphics, cleanup or production operation occurs.
Reports and numerical data belong under artifacts/verification/resume3223/.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from fractions import Fraction
from functools import partial
from pathlib import Path
from types import CodeType
from typing import Any

from artifacts.verification.resume3212 import runtime
from artifacts.verification.resume3220.certificate import Prepared, prepare
from artifacts.verification.resume3221.schedule import ReviewSchedule
from artifacts.verification.resume3222.certified import certified
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_scale import NativeScale, construction
from experiments.experiment_ribbon_fold_route.material_surfaces import MaterialPatch

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "artifacts/verification/resume3223"


def patch_record(physical: MaterialPatch, scaled: MaterialPatch) -> dict[str, Any]:
    """
    Serialize physical controls and exact numeric inputs to the existing cm boundary.

    The conditioned tuple comes from original construction(), not a new scaling
    implementation. Dividing each stored scaled coordinate by10 matches native_point;
    no Point3D/NurbsSurface/BRep objects are created. Kernel output is unmeasured.
    """
    if (
        physical.piece_index,
        physical.region,
        physical.profile_index,
        physical.degree_u,
        physical.knots_u,
    ) != (
        scaled.piece_index,
        scaled.region,
        scaled.profile_index,
        scaled.degree_u,
        scaled.knots_u,
    ) or len(physical.rows) != len(scaled.rows):
        raise ValueError("Conditioning must preserve complete patch/basis identity")
    return {
        "piece": physical.piece_index,
        "region": physical.region,
        "profile_index": physical.profile_index,
        "degree_u": physical.degree_u,
        "knots_u": physical.knots_u,
        "profile": asdict(physical.profile),
        "rows_mm": [[asdict(p) for p in row] for row in physical.rows],
        "rows_conditioned_cm": [
            [{a: getattr(p, a) / 10 for a in "xyz"} for p in row] for row in scaled.rows
        ],
        "weights_u": getattr(physical, "weights_u", (1.0,) * len(physical.rows)),
        "emitted_bound_mm": physical.error_bound_mm,
    }


def midplane_record(value: Prepared) -> dict[str, Any]:
    """
    Retain actual runtime scalar fields and b0world controls for independent offline proof.
    """
    return {
        "half_mm": value.half,
        "breaks_exact": [str(x) for x in value.surface.basis.breaks],
        "sine_exact": [str(x) for x in value.fields.sine.controls],
        "cosine_exact": [str(x) for x in value.fields.cosine.controls],
        "phase_exact": [str(x) for x in value.fields.phase.controls],
        "rows_mm": [[asdict(p) for p in row] for row in value.surface.rows],
    }


def compiled_arithmetic() -> dict[str, str]:
    """
    Compare effective existing and new author/proof bodies with current pinned source.
    """
    from artifacts.verification.resume3196 import native as rational_native
    from artifacts.verification.resume3216 import basis, field, spline
    from artifacts.verification.resume3218 import profile
    from artifacts.verification.resume3219 import interval, position, scalar
    from artifacts.verification.resume3220 import certificate
    from artifacts.verification.resume3221 import schedule
    from artifacts.verification.resume3222 import certified as cert_module
    from artifacts.verification.resume3222 import conversion
    from cable_bundler.routing import geometry as vectors
    from experiments.experiment_ribbon_fold_route import geometry, material_scale

    checks = runtime.runtime_checks()
    for module, names in (
        (basis, ("Basis.__post_init__", "Basis.jets")),
        (spline, ("Spline.__post_init__", "Spline.rounded", "interpolate", "solve", "linear")),
        (field, ("build",)),
        (profile, ("prepare", "bend_patch", "patches")),
        (
            interval,
            (
                "Interval.enclose",
                "Interval.add",
                "Interval.multiply",
                "Interval.divide",
                "trigonometry",
            ),
        ),
        (position, ("frame", "coefficients", "bank_error", "enclose")),
        (scalar, ("enclose",)),
        (
            schedule,
            (
                "ReviewSchedule._budget",
                "ReviewSchedule.case_budget",
                "ReviewSchedule.cohort_budget",
            ),
        ),
        (cert_module, ("certified",)),
        (conversion, ("control_error", "upper_float")),
        (certificate, ("prepare",)),
        (rational_native, ("native_point",)),
        (geometry, ("Pose.point", "Pose.direction", "Straight.surface")),
        (vectors, ("cross", "Vector3.translated")),
    ):
        filename = getattr(module, "__file__", None)
        if not isinstance(filename, str):
            raise RuntimeError("A pinned source file required for compiled comparison")
        for name in names:
            current: Any = module
            for part in name.split("."):
                current = getattr(current, part)
            current = getattr(current, "__func__", current)
            current = getattr(current, "__wrapped__", current)
            code = getattr(current, "__code__", None)
            if not isinstance(code, CodeType):
                raise RuntimeError("A compiled function body required: " + name)
            assert runtime.signature(code) == runtime.signature(
                runtime.compiled_body(Path(filename), name)
            ), name
            checks[module.__name__ + "." + name] = "exact_current_compiled_body"
    geometry_path, scale_path = geometry.__file__, material_scale.__file__
    assert isinstance(geometry_path, str) and isinstance(scale_path, str)
    assert runtime.signature(geometry.Pose.__dict__["_normal"].func.__code__) == runtime.signature(
        runtime.compiled_body(Path(geometry_path), "Pose._normal")
    )
    checks["Pose._normal"] = "exact_current_compiled_body"
    assert (
        material_scale.NativeScale.CONDITIONED.value == 10
        and material_scale.NativeScale.CONDITIONED.factor == 1024
    )
    getter = getattr(material_scale.NativeScale.__dict__["factor"], "fget", None)
    code = getattr(getter, "__code__", None)
    assert isinstance(code, CodeType)
    assert runtime.signature(code) == runtime.signature(
        runtime.compiled_body(Path(scale_path), "NativeScale.factor")
    )
    checks["NativeScale.factor"] = "exact_current_compiled_body"
    return checks


def verify(plan: dict[str, Any]) -> None:
    """
    Reject selected/helper/input drift without reloading modules or touching CAD.
    """
    runtime.sources()
    for path, expected in plan["pins"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


def required_state(owner: Any, name: str) -> Any:
    """
    Read explicitly named legacy runtime state, rejecting absence instead of assuming idle.

    Live owner registries and worker flags are runtime-installed attributes of
    the unchanged selected modules, not a new public production interface.
    """
    return getattr(owner, name)


def idle_owner(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Require the same idle design, exact retained owner and no active diagnostic/gym worker.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    from devtools.ribbon_analysis import end_profile_command
    from experiments.experiment_ribbon_locked_solver import native
    from experiments.experiment_ribbon_spatial_inspection import host

    app = adsk.core.Application.get()
    assert os.getpid() == plan["pid"] and app.activeDocument.creationId == plan["document_id"]
    assert (
        app.userInterface.activeCommand == "SelectCommand"
        and not end_profile_command.pending_state()
    )
    assert len(host.VIEWS) == 1 and host.VIEWS[0].process is None
    view = host.VIEWS[0]
    assert view.component.entityToken == plan["view"]["component_token"]
    assert view.ledger.fingerprint == plan["view"]["fingerprint"]
    assert view.palette.id == plan["view"]["palette"]
    gym = sys.modules.get("experiments.experiment_ribbon_locked_solver.gym")
    for owner in () if gym is None else required_state(gym, "_owners"):
        assert not owner.range_tester.active and not required_state(
            owner.range_tester.engine, "_polling"
        )
        assert required_state(owner.diagnostics.runner, "_process") is None
    retained = required_state(native, "_qualification_3202")
    runtime.check_ownership(retained, plan["ownership"])
    return runtime.ownership(retained)


def write(path: Path, value: Any) -> None:
    """
    Preserve each raw snapshot once, rejecting incomplete or nonfinite serialization.
    """
    with path.open("x") as stream:
        json.dump(value, stream, allow_nan=False)


def collect(name: str, started: float) -> None:
    """
    Freeze actual3.14authoring/proofs under an earlier review deadline with no native operation.
    """
    if name not in ("calibration", "cohort"):
        raise ValueError("Only a frozen bounded runtime capture permitted")
    cpu = time.process_time()
    plan = json.loads((FOLDER / f"{name}-plan.json").read_text())
    schedule = ReviewSchedule(started, plan["estimated_wall_seconds"])
    verify(plan)
    cohort = schedule.cohort_budget()
    ownership = idle_owner(plan)
    checks = compiled_arithmetic()
    write(
        FOLDER / f"{name}-runtime.json",
        {"python": sys.version, "compiled": checks, "ownership": ownership},
    )
    results = []
    for ordinal, case in enumerate(plan["cases"]):
        cohort.check("actual runtime C2case launch")
        budget = schedule.case_budget()
        case_cpu = time.process_time()
        folder = FOLDER / f"{name}-case-{ordinal:03d}"
        folder.mkdir()
        payload = json.loads((ROOT / case["folder"] / "route.json").read_text())
        route = restore(payload)
        actual = snapshot(route)
        original = json.loads((ROOT / case["folder"] / "plan.json").read_text())
        assert actual["case"] == original["targets"]
        assert all(actual[k] == payload[k] for k in ("case", "pieces", "radius_mm"))
        profile = material_profile(route.targets.lines, route.targets.diameter_mm)
        observations: dict[str, Any] = {}
        patches = certified(route.pieces, profile, NativeScale.CONDITIONED, budget, observations)
        for record in observations["certificates"]:
            assert (
                Fraction(record["total_exact_mm"])
                <= Fraction(record["emitted_mm"])
                <= Fraction(1e-6)
            )
        inputs = construction(
            route.pieces,
            patches,
            NativeScale.CONDITIONED,
            partial(budget.check, "actual runtime conditioning"),
        )
        records = []
        for physical, scaled in zip(patches, inputs.patches):
            budget.check("actual runtime input serialization")
            records.append(patch_record(physical, scaled))
        write(folder / "patches.json", records)
        write(folder / "outgoing-certificates.json", observations)
        half = max(abs(q) for arc in profile for q, _ in arc.controls)
        midplanes = {}
        for bend in case["bends"]:
            index = bend["piece"]
            prepared = prepare(route.pieces[index], half, budget)
            midplanes[str(index)] = midplane_record(prepared)
        write(folder / "midplanes.json", midplanes)
        verify(plan)
        assert idle_owner(plan) == ownership
        budget.check("actual runtime C2case terminal")
        result = {
            "case": case,
            "patches": len(patches),
            "bend_patches": sum(p.region == "bend" for p in patches),
            "midplanes": len(midplanes),
            "maximum_emitted_mm": max(p.error_bound_mm for p in patches),
            "cpu_seconds": time.process_time() - case_cpu,
            "wall_seconds": budget.clock() - budget.started,
            "rss_kib": budget.memory(),
            "data_sha256": {
                name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                for name in ("patches.json", "outgoing-certificates.json", "midplanes.json")
            },
            "new_solves": 0,
            "native_attempts": 0,
            "full_physical_passes": 0,
        }
        write(folder / "result.json", result)
        results.append(result)
    verify(plan)
    assert idle_owner(plan) == ownership
    assert compiled_arithmetic() == checks
    cohort.check("actual runtime C2capture terminal")
    result = {
        "known_complete_inputs_planned": len(plan["cases"]),
        "evaluated": len(results),
        "unattempted": len(plan["cases"]) - len(results),
        "cases": results,
        "compiled_checks": len(checks),
        "cpu_seconds": time.process_time() - cpu,
        "wall_seconds": time.perf_counter() - started,
        "rss_kib": cohort.memory(),
        "estimated_review_seconds": plan["estimated_wall_seconds"],
        "new_solves": 0,
        "native_attempts": 0,
        "fresh_credit": 0,
        "full_physical_passes": 0,
        "scope": "Actual Fusion Python numerical C2authoring/outgoing input bounds, no native API surface/body/kernel/geometry or physical acceptance",
    }
    write(FOLDER / f"{name}-result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}))
