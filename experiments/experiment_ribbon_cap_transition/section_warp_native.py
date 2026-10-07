"""
Append a bounded section-warp comparison to the existing straight twist pilot.

Use identical 360-degree twist and spline contour representation at every scale.
Retain prior bodies and the original failure example; no fixes, retries or audits.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .flex_contours import flex_contour
from .native import PROJECT_ROOT, _write
from .native_budget import NativeBudget
from .section_midpoints import split_outer_edge_midpoints
from .section_warp_trial import imposed_flex, scaled_direction
from .straight_twist import twist_frames
from .straight_twist_native import NAME, _sections
from .warp_replay import retained_path

TEMPLATE = (
    PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/straight_twist/warp_template.json"
)
SCALES = (0.0, 0.5, 1.0)
PARTIAL_REPORT = (
    PROJECT_ROOT
    / "artifacts/verification/ribbon_cap_transition/section_warp/0d37bc048c4d44a3b2b66af7a6dfbe55/report.json"
)


def _fingerprints() -> dict[str, str]:
    """
    Freeze the transferred fixture, rules and every direct geometry implementation.
    """
    paths = [
        TEMPLATE,
        PROJECT_ROOT / "experiment_testing_rules.txt",
        PROJECT_ROOT / "rollback_end_loft_notes.txt",
    ]
    paths.extend(
        PROJECT_ROOT / "experiments/experiment_ribbon_cap_transition" / name
        for name in (
            "section_warp_native.py",
            "section_warp_trial.py",
            "section_flex.py",
            "section_midpoints.py",
            "flex_contours.py",
            "curve_context.py",
            "straight_twist.py",
            "straight_twist_native.py",
            "native_budget.py",
            "warp_replay.py",
        )
    )
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def run(_context: object) -> None:
    """
    Test zero, half and full warp once; stop at first failure or 60s/300s/2GiB limit.

    Capture exceptions intentionally so partial diagnostic curves persist in the
    MCP transaction. Transferred edge directions are imposed local orientations,
    not physical edge derivatives or a claimed compliant ribbon solution.
    """
    _execute(None)


def resume(_context: object) -> None:
    """
    Finish retained preparation and all three variants after user waived time cutoffs.

    Retain2GiB scheduling ceiling and first-failure stop. Three lofts maximum,
    no geometry retries/search. Verify retained samples instead of reauthoring them.
    """
    _execute(PARTIAL_REPORT)


def _execute(parent_path: Path | None) -> None:
    """
    Execute one frozen initial or explicitly renewed partial-preparation run.
    """
    app = adsk.core.Application.get()
    if app.activeDocument.name != NAME or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned straight-twist document.")
    design = adsk.fusion.Design.cast(app.activeProduct)
    expected_occurrences = 3 if parent_path is None else 4
    if design is None or design.rootComponent.occurrences.count != expected_occurrences:
        raise RuntimeError("Pilot already changed; no repeat.")
    if any(
        occ.component.bRepBodies.count != 1 or not occ.component.bRepBodies.item(0).isSolid
        for occ in tuple(design.rootComponent.occurrences)[:3]
    ):
        raise RuntimeError("Retained original pilot solids changed.")
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    local = template["local_edge_tangents"]
    if not isinstance(local, list) or len(local) != 32:
        raise ValueError("Expected32 frozen section directions.")
    for pair in local:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Expected two edge directions per section.")
        for direction in pair:
            scaled_direction(tuple(direction), 1)
    fingerprints = _fingerprints()
    parent = None if parent_path is None else json.loads(parent_path.read_text(encoding="utf-8"))
    retained = None
    if parent is not None:
        for name, expected in parent["fingerprints"].items():
            if name.endswith("section_warp_native.py"):
                continue
            if fingerprints.get(name) != expected:
                raise RuntimeError(
                    "Frozen warp implementation/input changed after partial preparation."
                )
        retained = design.rootComponent.occurrences.item(3)
        if (
            retained.component.name
            != "360 twist - ZERO warp control - PREPARATION TIMEOUT, NO LOFT"
            or retained.component.bRepBodies.count != 0
            or retained.component.sketches.count != 61
        ):
            raise RuntimeError("Expected exact retained partial zero-warp control.")
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/section_warp" / uuid4().hex
    )
    directory.mkdir(parents=True)
    cases: list[dict[str, object]] = [
        {
            "scale": scale,
            "id": f"straight360_section_warp_{scale:g}",
            "parent": "straight_57mm_360",
            "status": "not attempted",
            "native_prediction": "unknown",
            "audit": "not attempted",
            "sections": [],
        }
        for scale in SCALES
    ]
    plan: dict[str, object] = {
        "question": "Does imposed three-anchor section warp fail on the successful twisted scaffold?",
        "twist": "Unchanged+360 degrees/quintic,57mm straight centerline,32sections,19x1.5mm",
        "variable": "Edge-normal tilt angle relative to center scaled0/0.5/1; local directions transferred from known failure",
        "representation": "All cases use42arc source topology,30interior42segment five-fit-point spline Paths; original planar cap Paths",
        "source_template": template,
        "fingerprints": fingerprints,
        "coverage": "One development family/three variants;0 complete ribbons, not independent collateral challenges",
        "exclusions": "No search, endings, sphere or mechanical skin audit; transferred normals are not scaffold edge derivatives",
        "budget": {
            "attempts": 3,
            "seconds_case": 60 if parent is None else "user-waived",
            "seconds_batch": 300 if parent is None else "user-waived",
            "rss_kib": 2097152,
        },
        "renewal": None
        if parent is None
        else {
            "parent_report": str(parent_path),
            "parent_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
            "user_instruction": "just build them we will deal with performance later",
            "change": "Time scheduling cutoff removed; identical geometry,3attempts,2GiB and first-failure stop retained",
        },
        "stop": "First failure or limit; no retries/tuning; retain original pilot and failure example",
        "cases": cases,
    }
    _write(directory / "plan.json", plan)
    batch = NativeBudget(maximum_seconds=300 if parent is None else math.inf)
    stopped: str | None = None
    for index, (scale, case) in enumerate(zip(SCALES, cases)):
        if stopped is not None:
            case["not_attempted_reason"] = stopped
            continue
        budget = NativeBudget(maximum_seconds=60 if parent is None else math.inf)
        started = perf_counter()
        stage = "preparation"
        try:
            if _fingerprints() != fingerprints:
                raise RuntimeError("Fixture/source drift; no build.")
            batch.check(f"case{scale}")
            budget.check("component")
            occurrence = retained if index == 0 else None
            if occurrence is None:
                placement = adsk.core.Matrix3D.create()
                placement.translation = adsk.core.Vector3D.create(index * 4.5, 6, 0)
                occurrence = design.rootComponent.occurrences.addNewComponent(placement)
            component = occurrence.component
            component.name = f"360 twist - section warp{scale:g} - preparing"
            if index != 0 or retained is None:
                _sections(component, 360, budget)
            sources = tuple(component.sketches)[:32]
            paths = []
            for number, (source, frame, pair) in enumerate(
                zip(sources, twist_frames(360), local), 1
            ):
                budget.check(f"warp section{number}")
                batch.check(f"warp section{number}")
                if source.sketchCurves.sketchArcs.count == 40:
                    split_outer_edge_midpoints(source, 19)
                elif (
                    index != 0
                    or retained is None
                    or number > 30
                    or source.sketchCurves.sketchArcs.count != 42
                ):
                    raise RuntimeError("Unexpected source contour topology in renewed run.")
                flex = imposed_flex(
                    frame, tuple(pair[0]), tuple(pair[1]), scale, terminal=number in (1, 32)
                )
                if index == 0 and retained is not None and 2 <= number <= 30:
                    sketch, path, error = retained_path(
                        component, source, occurrence, frame, flex, number
                    )
                    observation = dict(parent["cases"][0]["sections"][number - 1])
                    observation["retained_contour_reused"] = True
                    observation["maximum_replay_fit_error_mm"] = error
                else:
                    sketch, path, observation = flex_contour(
                        component, source, frame, flex, number, occurrence
                    )
                sketch.isLightBulbOn = False
                paths.append(path)
                observation["maximum_imposed_edge_tilt_degrees"] = (
                    max(
                        math.degrees(
                            math.acos(max(-1, min(1, scaled_direction(tuple(direction), scale).z)))
                        )
                        for direction in pair
                    )
                    if number not in (1, 32)
                    else 0
                )
                case["sections"].append(observation)
            case["preparation_seconds"] = perf_counter() - started
            budget.check("native trunk")
            batch.check("native trunk")
            if _fingerprints() != fingerprints:
                raise RuntimeError("Frozen input drift before loft.")
            loft_input = component.features.loftFeatures.createInput(
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            loft_input.isSolid = True
            for path in paths:
                loft_input.loftSections.add(path)
            stage = "native"
            case["native_attempted"] = True
            native_started = perf_counter()
            try:
                feature = component.features.loftFeatures.add(loft_input)
            finally:
                case["native_seconds"] = perf_counter() - native_started
            case["bodies"] = [{"solid": b.isSolid, "volume_cm3": b.volume} for b in feature.bodies]
            if (
                feature.bodies.count != 1
                or not feature.bodies.item(0).isSolid
                or feature.bodies.item(0).volume <= 0
            ):
                raise RuntimeError("One positive-volume solid was not returned.")
            feature.bodies.item(0).name = f"360twist - {scale:g}section warp (unaudited)"
            component.name = f"360 twist - section warp{scale:g} - BUILT unaudited"
            case["status"] = "built"
            stage = "post-build scheduling"
            budget.check("after trunk")
            batch.check("after case")
        except Exception as error:
            if case["status"] != "built":
                case["status"] = (
                    "kernel/output failure" if stage == "native" else "harness/scheduling stop"
                )
            case["error"] = str(error)
            stopped = f"Stopped at warp{scale}: {error}"
        finally:
            case["case_seconds"] = perf_counter() - started
            case["memory_samples"] = budget.samples
            _write(
                directory / "report.json",
                {**plan, "stop_reason": stopped, "batch_seconds": perf_counter() - batch.started},
            )
    _write(
        directory / "report.json",
        {
            **plan,
            "stop_reason": stopped,
            "batch_seconds": perf_counter() - batch.started,
            "memory_samples": batch.samples,
            "artifact_directory": str(directory),
        },
    )
    app.log(f"Section warp diagnostic evidence: {directory}")
