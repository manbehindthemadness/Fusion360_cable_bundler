"""
Build existing flexed contour prefixes once, retaining the last successful solid.
"""

from __future__ import annotations

import hashlib
import json
import math
import traceback
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .curve_context import connected_curve_order, occurrence_curve
from .flex_native import DOCUMENT_NAME
from .native import PROJECT_ROOT, _write
from .native_budget import NativeBudget
from .screen import _fingerprints

PARENT = "artifacts/verification/ribbon_cap_transition/flex_native/e8cbb5e632244200af529f56efa33637/report.json"


def run(_context: object) -> None:
    """
    Probe prefixes 1-2 through at most 1-32, stopping on the first failure or budget.

    Reuse all frozen contours without solving or changing their geometry. Keep the
    old planar baseline intact if present; never restore a user-removed body.
    Each successful new prefix replaces only the prior
    prefix created by this call; no historical/user features are deleted. Expected
    native failures are caught so the last success commits. A prefix introduces a
    nonplanar end closure and is not equivalent to a span of the original full loft.
    Endings/compliance audits are excluded. Presentation/archive is a separate call.
    """
    budget = NativeBudget()
    app = adsk.core.Application.get()
    if (
        app.activeDocument.name != DOCUMENT_NAME
        or str(app.userInterface.activeCommand) != "SelectCommand"
    ):
        raise RuntimeError("Expected the owned active design and idle Fusion.")
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or design.rootComponent.occurrences.count != 1:
        raise RuntimeError("Owned component structure changed.")
    occurrence = design.rootComponent.occurrences.item(0)
    component = occurrence.component
    if component.bRepBodies.count > 1 or (
        component.bRepBodies.count == 1
        and component.bRepBodies.item(0).name != "Prefix 1-17 - last successful solid"
    ):
        raise RuntimeError("Unexpected existing bodies; no retry.")
    baseline = component.bRepBodies.item(0) if component.bRepBodies.count == 1 else None
    baseline_volume = baseline.volume if baseline is not None else None
    parent_path = PROJECT_ROOT / PARENT
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if (
        parent["native_attempted"] != 1
        or parent["trunk_built"] != 0
        or len(parent["sections"]) != 32
    ):
        raise RuntimeError("Frozen full-flex failure evidence changed.")
    for name, expected in parent["plan"]["source_sha256"].items():
        path = PROJECT_ROOT / "experiments/experiment_ribbon_cap_transition" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Frozen flex implementation drift; no build.")
    directory = (
        PROJECT_ROOT
        / "artifacts/verification/ribbon_cap_transition/flex_prefix_native"
        / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    fingerprints = _fingerprints()
    plan = {
        "case_id": parent["plan"]["case_id"],
        "parent_report": str(parent_path),
        "parent_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(
            (
                PROJECT_ROOT / "experiments/experiment_ribbon_cap_transition/flex_prefix_native.py"
            ).read_bytes()
        ).hexdigest(),
        "rule_and_source_sha256": fingerprints,
        "fixed_case": parent["plan"]["fixed_case"],
        "hypothesis": "Find the last solid prefix before the first native prefix failure; outcomes unknown.",
        "native_prediction": "unknown",
        "baseline_present_at_start": baseline is not None,
        "procedure": "Existing closed contour Paths in unchanged connection order; NewBody solid lofts 1-2,1-3,...; stop first failure, no retry or rerouting; retain only latest successful new prefix and historical baseline.",
        "limits": {
            "independent_cases": 1,
            "prefix_operations": 31,
            "seconds": 120,
            "rss_kib": 2097152,
            "search": 0,
            "retries": 0,
        },
        "caveat": "A partial solid adds a nonplanar end closure; its first failure need not locate the full-loft failure span.",
        "exclusions": "No full numerical re-solve, endings, post-build mechanical audits or collateral configurations.",
    }
    report: dict[str, object] = {
        "plan": plan,
        "paths": [],
        "attempts": [],
        "native_configuration_attempted": 0,
        "last_successful_prefix": None,
        "first_failed_prefix": None,
        "complete_ribbons_built": 0,
        "fully_audited": 0,
        "status": "not_attempted",
    }
    _write(directory / "plan.json", plan)
    _write(directory / "report.json", report)
    last_loft = None
    try:
        started = perf_counter()
        paths = []
        observations = []
        for number in range(1, 33):
            budget.check(f"existing_path_{number}")
            name = (
                f"Failed loft input section {number:02}"
                if number in (1, 32)
                else f"Three-anchor flex section {number:02}"
            )
            matches = [sketch for sketch in component.sketches if sketch.name == name]
            if len(matches) != 1:
                raise RuntimeError("Frozen contour missing/ambiguous.")
            sketch = matches[0]
            curves = (
                sketch.sketchCurves.sketchArcs
                if number in (1, 32)
                else sketch.sketchCurves.sketchFittedSplines
            )
            if curves.count != 42:
                raise RuntimeError("Frozen contour topology changed.")
            positions = []
            for curve in curves:
                points = (
                    (curve.startSketchPoint, curve.endSketchPoint)
                    if number in (1, 32)
                    else tuple(curve.fitPoints)
                )
                if number not in (1, 32) and len(points) != 5:
                    raise RuntimeError("Frozen contour fit-point count changed.")
                positions.append(
                    [
                        [point.worldGeometry.x, point.worldGeometry.y, point.worldGeometry.z]
                        for point in points
                    ]
                )
            collection = adsk.core.ObjectCollection.create()
            for curve in connected_curve_order(curves):
                collection.add(occurrence_curve(curve, occurrence))
            path = adsk.fusion.Path.create(
                collection, adsk.fusion.ChainedCurveOptions.noChainedCurves
            )
            if path is None or path.count != 42 or not path.isClosed:
                raise RuntimeError("Frozen contour Path incomplete/open.")
            paths.append(path)
            observations.append(
                {
                    "section": number,
                    "name": name,
                    "world_cm": positions,
                    "closed": path.isClosed,
                    "curve_count": path.count,
                }
            )
        budget.timings["existing_path_setup"] = perf_counter() - started
        report["paths"] = observations
        _write(directory / "report.json", report)
        attempts = []
        for count in range(2, 33):
            budget.check(f"prefix_1_{count}")
            if _fingerprints() != fingerprints:
                raise RuntimeError("Source/rule drift; stop before next prefix.")
            loft_input = component.features.loftFeatures.createInput(
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            if loft_input is None:
                raise RuntimeError("Loft input unavailable.")
            for path in paths[:count]:
                loft_input.loftSections.add(path)
            loft_input.isSolid = True
            attempt: dict[str, object] = {
                "last_section": count,
                "native_attempted": True,
                "built": False,
            }
            attempts.append(attempt)
            report["attempts"] = attempts
            report["native_configuration_attempted"] = 1
            _write(directory / "report.json", report)
            started = perf_counter()
            try:
                loft = component.features.loftFeatures.add(loft_input)
                if loft is None or loft.bodies.count != 1:
                    raise RuntimeError("Prefix did not produce one body.")
                body = loft.bodies.item(0)
                if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
                    raise RuntimeError("Invalid prefix solid.")
            except (RuntimeError, ValueError, TypeError, AttributeError) as error:
                attempt["error"] = str(error)
                report["first_failed_prefix"] = count
                report["status"] = "first_native_prefix_failure"
                break
            finally:
                attempt["native_seconds"] = perf_counter() - started
                budget.timings["native_prefixes"] = budget.timings.get(
                    "native_prefixes", 0.0
                ) + float(attempt["native_seconds"])
                _write(directory / "report.json", report)
            body.name = f"Flex prefix 1-{count} - last successful solid"
            body.isLightBulbOn = True
            attempt["built"] = True
            attempt["volume_cm3"] = body.volume
            report["last_successful_prefix"] = count
            previous = last_loft
            last_loft = loft
            if previous is not None and not previous.deleteMe():
                raise RuntimeError(
                    "Prior diagnostic prefix cleanup failed; retain current and stop."
                )
            _write(directory / "report.json", report)
        else:
            report["status"] = "all_prefixes_built_compliance_unmeasured"
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        report["status"] = "diagnostic_stopped"
        report["error"] = str(error)
        report["traceback"] = traceback.format_exc()
    if baseline is not None:
        baseline.isLightBulbOn = last_loft is None
    report["baseline_unchanged"] = (
        baseline.volume == baseline_volume if baseline is not None else None
    )
    report["baseline_volume_cm3"] = baseline.volume if baseline is not None else None
    report["timings_seconds"] = budget.timings
    report["memory_samples"] = budget.samples
    report["elapsed_seconds"] = perf_counter() - budget.started
    report["final_rss_kib"] = budget.memory()
    _write(directory / "report.json", report)
    _write(
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/flex-prefix-latest.json",
        {"directory": str(directory)},
    )
    app.log(f"Flex prefix diagnostic: {directory}")
