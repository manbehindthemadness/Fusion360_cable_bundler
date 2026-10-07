"""
Replay the failed half-warp trunk once using alternate stations and both exact caps.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT


def selected_sections(count: int = 32) -> tuple[int, ...]:
    """
    Select one-based odd stations, always retaining the final terminal section.
    """
    if count < 2:
        raise ValueError("At least two terminal sections are required.")
    selected = tuple(range(1, count + 1, 2))
    return selected if selected[-1] == count else (*selected, count)


def run(_context: object) -> None:
    """
    Attempt one17-section solid loft, without changing warp, twist or stored curves.

    User requested this explicit retry; no automatic second attempt or other parity.
    Time cutoff remains user-waived, RSS scheduling ceiling2GiB retained. Capture
    native failure intentionally to preserve inputs in the MCP transaction.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    from .flex_contours import flex_contour
    from .native import _write
    from .native_budget import NativeBudget
    from .section_warp_native import _fingerprints
    from .section_warp_trial import imposed_flex
    from .straight_twist import twist_frames
    from .straight_twist_native import NAME
    from .warp_replay import retained_path

    app = adsk.core.Application.get()
    if app.activeDocument.name != NAME or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned twist pilot.")
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Design unavailable.")
    matches = [
        o
        for o in design.rootComponent.occurrences
        if o.component.name == "360 twist - HALF SECTION WARP - SELF-INTERSECTION FAILURE, NO BODY"
    ]
    if len(matches) != 1 or matches[0].component.bRepBodies.count != 0:
        raise RuntimeError("Expected retained failed half-warp inputs, no new body.")
    occurrence = matches[0]
    component = occurrence.component
    parent_path = (
        PROJECT_ROOT
        / "artifacts/verification/ribbon_cap_transition/section_warp/ba8be6ab459645d291fa8da45016575d/report.json"
    )
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    fingerprints = _fingerprints()
    if fingerprints != parent["fingerprints"]:
        raise RuntimeError("Frozen half-warp inputs/implementation changed.")
    numbers = selected_sections()
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/alternate_warp" / uuid4().hex
    )
    directory.mkdir(parents=True)
    report: dict[str, object] = {
        "question": "Does alternate-section sampling avoid the half-warp native failure?",
        "parent_report": str(parent_path),
        "parent_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fingerprints": fingerprints,
        "selected_sections": numbers,
        "skipped_sections": [n for n in range(1, 33) if n not in numbers],
        "fixed": "Same+360quintic twist,half section warp,57mm straight route,unchanged anchor positions/contours and terminal caps",
        "coverage": "One existing development trunk, one sampling retry;0 complete ribbons",
        "budget": {"native_attempts": 1, "seconds": "user-waived", "rss_kib": 2097152, "search": 0},
        "native_prediction": "unknown",
        "audit": "not attempted; omitted-station fidelity and skin mechanics unmeasured",
        "native_attempted": False,
        "status": "not attempted",
    }
    _write(directory / "plan.json", report)
    budget = NativeBudget(maximum_seconds=math.inf)
    stage = "preparation"
    try:
        paths = []
        maximum_error = 0.0
        frames = twist_frames(360)
        local = parent["source_template"]["local_edge_tangents"]
        for number in numbers:
            budget.check(f"retained section{number}")
            sources = [
                s for s in component.sketches if s.name == f"Original planar section {number:02}"
            ]
            if len(sources) != 1:
                raise RuntimeError("Retained source section missing/ambiguous.")
            frame = frames[number - 1]
            pair = local[number - 1]
            flex = imposed_flex(
                frame, tuple(pair[0]), tuple(pair[1]), 0.5, terminal=number in (1, 32)
            )
            if number in (1, 32):
                _, path, _ = flex_contour(component, sources[0], frame, flex, number, occurrence)
            else:
                _, path, error = retained_path(
                    component, sources[0], occurrence, frame, flex, number
                )
                maximum_error = max(maximum_error, error)
            paths.append(path)
        report["maximum_replay_fit_error_mm"] = maximum_error
        report["preparation_seconds"] = perf_counter() - budget.started
        budget.check("alternate loft")
        loft_input = component.features.loftFeatures.createInput(
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        loft_input.isSolid = True
        for path in paths:
            loft_input.loftSections.add(path)
        stage = "native"
        report["native_attempted"] = True
        started = perf_counter()
        try:
            feature = component.features.loftFeatures.add(loft_input)
        finally:
            report["native_seconds"] = perf_counter() - started
        report["bodies"] = [{"solid": b.isSolid, "volume_cm3": b.volume} for b in feature.bodies]
        if (
            feature.bodies.count != 1
            or not feature.bodies.item(0).isSolid
            or feature.bodies.item(0).volume <= 0
        ):
            raise RuntimeError("Loft did not return one positive-volume solid.")
        feature.bodies.item(
            0
        ).name = "360twist - half section warp - alternate17sections (unaudited)"
        report["status"] = "built"
    except Exception as error:
        report["status"] = (
            "kernel/output failure" if stage == "native" else "harness/scheduling stop"
        )
        report["error"] = str(error)
    report["total_seconds"] = perf_counter() - budget.started
    report["memory_samples"] = budget.samples
    _write(directory / "report.json", report)
    app.log(f"Alternate-section evidence: {directory}")
