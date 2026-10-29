"""
Freeze one bounded diagnostic recording before numerical search, with no native solids.

Run locally with the project SDK:
uv run python -m experiments.experiment_ribbon_diagnostic_viewer.runner --output artifacts/verification/<new-directory>
Fusion is needed only to replay the resulting manifest through DiagnosticViewer.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from devtools.ribbon_analysis.budget import resident_kib
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    RuleObservation,
    read_document,
    snapshot_payload,
    targets_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.capture import (
    CaptureLimits,
    SearchRecorder,
    load_history_path,
    read_history,
)
from devtools.ribbon_analysis.inspection.geometry import freeze_curve, freeze_path
from devtools.ribbon_analysis.inspection.measurements import observations
from experiments.experiment_ribbon_bend_redistribution.refinement import redistribute
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_route_discovery import generalized
from experiments.experiment_ribbon_route_discovery.broad_search import SearchLedger
from experiments.experiment_ribbon_tangent_tightening.field import TangentTightening
from experiments.experiment_ribbon_tangent_tightening.refinement import tighten

from .fixture import SpatialSBend
from .procedures import source_pins

INVENTORY = (
    (
        "generalized",
        "Generalized cold search",
        "experiments/experiment_ribbon_route_discovery/generalized.py",
    ),
    (
        "ordinary",
        "Ordinary warm continuation",
        "experiments/experiment_ribbon_tangent_tightening/refinement.py",
    ),
    (
        "redistribution",
        "Bend redistribution",
        "experiments/experiment_ribbon_bend_redistribution/refinement.py",
    ),
    (
        "tightening",
        "Terminal tangent tightening",
        "experiments/experiment_ribbon_tangent_tightening/refinement.py",
    ),
    (
        "combined",
        "Redistribution + terminal tightening",
        "experiments/experiment_ribbon_bend_redistribution/refinement.py",
    ),
    (
        "quintic",
        "Endpoint quintic / material frames",
        "experiments/experiment_ribbon_cap_transition/solver.py",
    ),
    (
        "target-shooting",
        "Target shooting",
        "experiments/experiment_ribbon_cap_transition/target_shooting.py",
    ),
    (
        "tube",
        "Prescribed-twist tube",
        "experiments/experiment_ribbon_cap_transition/tube_solver.py",
    ),
    (
        "director",
        "Director shooting (policy variants)",
        "experiments/experiment_ribbon_cap_transition/director_shooting.py",
    ),
    (
        "compatible",
        "Compatible shooting",
        "experiments/experiment_ribbon_cap_transition/compatible_shooting.py",
    ),
    (
        "discovery",
        "Historical family/contact-guided search",
        "experiments/experiment_ribbon_route_discovery/solver.py",
    ),
    (
        "broad",
        "Broad search (generalized delegate)",
        "experiments/experiment_ribbon_route_discovery/broad_search.py",
    ),
)


class SchedulingStop(RuntimeError):
    """
    Distinguish recorded resource stops from numerical or harness failures.
    """


def run(output: Path) -> Path:
    """
    Record one fixed reference and up to five current search variants under frozen caps.

    All warm arms start from the same completed cold result, never an interrupted
    probe. Resource, source and harness failures stop subsequent arms. Histories
    survive exceptions; all unrun methods remain explicit in the final manifest.
    """
    output.mkdir(parents=True, exist_ok=False)
    began = perf_counter()
    fixture = SpatialSBend()
    case = fixture.targets()
    pins = source_pins()
    limits = CaptureLimits(paths=1600, control_points=1_500_000, bytes=192 * 1024 * 1024)
    plan: dict[str, Any] = {
        "question": "Can every transported search proposal and distinct section be replayed without physical PASS claims?",
        "cases": [targets_payload(case)],
        "independent_configurations": 1,
        "fixture": asdict(fixture.tightness),
        "analytic_peak_utilization": fixture.curvature(0) * fixture.tightness.minimum_radius_mm,
        "authoring": "Forward-authored compound S with pitch reversal and 90-degree lateral yaw over the same curve; development reference, not a solved holdout.",
        "algorithm": "Unchanged generalized cold search, then ordinary/redistribution/terminal/combined warm arms from the same completed cold coordinates. Original solver can reroute the centre.",
        "rules": "Retained single-circle radius >=3D. Wide-ribbon ratio/scalar/flex unresolved. No self-collision acceptance from legacy sampled screens.",
        "budgets": {
            "cold_seconds": 16.052295,
            "warm_seconds_each": 8,
            "warm_fit_transports_each": 158,
            "aggregate_seconds": 90,
            "capture_per_method": asdict(limits),
            "rss_kib": 4 * 1024 * 1024,
            "launch_headroom_kib": int(3.8 * 1024 * 1024),
            "native_attempts": 0,
            "retries": 0,
        },
        "stops": "Any resource, source or harness error latches the run. Missing completed cold path leaves all warm methods not run. No target, tolerance, budget or solver modification during execution.",
        "sources": pins,
    }
    write_document(output / "plan.json", plan)
    reference = freeze_curve("S001-reference", fixture, case.diameter_mm)
    rules = list(observations(reference, case, fixture.tightness.minimum_radius_mm))
    rules.insert(
        1,
        RuleObservation(
            "Analytic reference tightness",
            "measured",
            "Analytic reference reaches the declared 3D radius at both ends. Frozen cubic and native measurements remain separate.",
            fixture.curvature(0) * fixture.tightness.minimum_radius_mm,
            1.0,
        ),
    )
    methods: list[dict[str, Any]] = [
        {
            "id": "reference",
            "label": "Authored compound S reference",
            "status": "reference",
            "detail": "One circular conductor, D=1.5mm; declared minimum radius 4.5mm. Pitch reverses while lateral heading turns 90 degrees. This is fixture authoring, not solver success.",
            "source": "experiments/experiment_ribbon_diagnostic_viewer/fixture.py",
            "snapshot": snapshot_payload(reference),
            "rules": [asdict(rule) for rule in rules],
        }
    ]
    for identifier, label, source in INVENTORY:
        methods.append(
            {
                "id": identifier,
                "label": label,
                "source": source,
                "status": "not_run",
                "detail": "Not scheduled: historical solver retained in the inventory; no result or physical success inferred.",
                "rules": [
                    asdict(
                        RuleObservation(
                            "Result / physical audit",
                            "unmeasured",
                            "This method has not been evaluated on this fixed case.",
                        )
                    )
                ],
            }
        )
    write_document(
        output / "reference.json",
        {"schema": SCHEMA, "targets": targets_payload(case), "solvers": methods, "sources": pins},
    )
    original: CompatiblePath | None = None
    coordinates: tuple[float, ...] | None = None
    stopped: str | None = None
    timings: dict[str, float] = {}
    maximum_rss = 0
    last_memory_check = -1.0
    for method in methods[1:6]:
        if stopped is not None:
            method["detail"] = f"Not run after latched stop: {stopped}"
            continue
        if method["id"] != "generalized" and (original is None or coordinates is None):
            method["detail"] = (
                "Not run: cold search returned no completed fit for a shared warm start."
            )
            continue
        started = perf_counter()
        cap = (
            plan["budgets"]["cold_seconds"]
            if method["id"] == "generalized"
            else plan["budgets"]["warm_seconds_each"]
        )

        def checkpoint(
            method_started: float = started,
            seconds_limit: float = cap,
            solver_id: str = method["id"],
        ) -> None:
            """
            Latch the affected search before launching additional work beyond its caps.
            """
            nonlocal maximum_rss, last_memory_check
            elapsed = perf_counter() - method_started
            if elapsed >= seconds_limit or perf_counter() - began >= 90:
                raise SchedulingStop(f"Time scheduling cap before further work in {solver_id}.")
            if perf_counter() - last_memory_check >= 0.25:
                last_memory_check = perf_counter()
                rss = resident_kib()
                maximum_rss = max(maximum_rss, rss)
                if rss >= 4 * 1024 * 1024:
                    raise SchedulingStop("4GiB sampled RSS ceiling.")

        recorder: SearchRecorder | None = None
        try:
            if resident_kib() >= int(3.8 * 1024 * 1024):
                raise SchedulingStop("3.8GiB launch headroom.")
            if source_pins() != pins:
                raise SchedulingStop("Source fingerprints changed after the frozen plan.")
            history = output / f"{method['id']}.jsonl"
            active_recorder = SearchRecorder(history, method["id"], checkpoint, limits)
            recorder = active_recorder
            method["history"] = history.name
            with active_recorder.recording():
                if method["id"] == "generalized":
                    ledger = SearchLedger()
                    handoff = generalized.solve(case, checkpoint, ledger)
                    selected = (
                        min(ledger.trials, key=lambda trial: trial.rank) if ledger.trials else None
                    )
                    path = (
                        handoff.path
                        if handoff is not None
                        else selected.path
                        if selected is not None
                        else None
                    )
                    metrics = (
                        handoff.metrics
                        if handoff is not None
                        else selected.metrics
                        if selected is not None
                        else {}
                    )
                    if path is not None:
                        original, coordinates = path, tuple(metrics["coordinates"])
                else:
                    assert original is not None and coordinates is not None
                    if method["id"] in ("redistribution", "combined"):
                        path, metrics = redistribute(
                            case,
                            original,
                            coordinates,
                            checkpoint,
                            tightening=TangentTightening() if method["id"] == "combined" else None,
                        )
                    else:
                        path, metrics = tighten(
                            case,
                            coordinates,
                            checkpoint,
                            tightening=TangentTightening()
                            if method["id"] == "tightening"
                            else None,
                        )
            if source_pins() != pins:
                raise SchedulingStop("Source fingerprints changed during the recorded search.")
            if path is not None:
                snapshot = freeze_path(
                    f"S001-{method['id']}-result", path, intervals=512, sections=33
                )
                method.update(
                    snapshot=snapshot_payload(snapshot),
                    rules=[
                        asdict(rule)
                        for rule in observations(
                            snapshot, case, fixture.tightness.minimum_radius_mm
                        )
                    ],
                )
            method.update(
                status="unresolved",
                detail=f"Numerical method completed; {active_recorder.count} transported paths stored. Endpoint and sampled-rule results are diagnostic; physical acceptance remains unresolved.",
                metrics=metrics,
            )
        except (SchedulingStop, RuntimeError, ValueError, TypeError, OSError) as error:
            stopped = f"{type(error).__name__}: {error}"
            method.update(status="stopped", detail=stopped)
            if recorder is not None and recorder.last is not None:
                method["snapshot"] = snapshot_payload(recorder.last)
                method["rules"] = [
                    asdict(
                        RuleObservation(
                            "Interrupted search",
                            "unmeasured",
                            "Last stored path may be a probe or rejected proposal, not a fitted result.",
                        )
                    )
                ]
        finally:
            timings[method["id"]] = perf_counter() - started
            method["recording"] = {
                "paths": recorder.count if recorder else 0,
                "bytes": recorder.bytes if recorder else 0,
                "capture_seconds_subset": recorder.seconds if recorder else 0,
            }
    manifest = {
        "schema": SCHEMA,
        "targets": targets_payload(case),
        "solvers": methods,
        "plan": "plan.json",
        "sources": pins,
        "independent_cases": {
            "planned": 1,
            "numerically_evaluated": 1,
            "native_attempted": 0,
            "built": 0,
            "fully_audited": 0,
            "unresolved": 1,
        },
        "timings": timings,
        "overall_seconds": perf_counter() - began,
        "maximum_sampled_rss_kib": maximum_rss,
        "stopped": stopped,
    }
    destination = output / "manifest.json"
    write_document(destination, manifest)
    return destination


def recover(output: Path) -> Path:
    """
    Recover flushed complete path events after interruption without rerunning a solver.

    Preserve an incomplete final line in place. Earlier malformed complete events
    still reject. The recovered manifest declares partial paths unaudited and
    writes a new file; it never alters the original plan, history or dispositions.
    """
    manifest = read_document(output / "reference.json")
    for method in manifest["solvers"]:
        history = output / f"{method['id']}.jsonl"
        if not history.is_file():
            continue
        records = read_history(history, allow_interrupted_tail=True)
        method.update(
            history=history.name,
            status="stopped",
            detail="Recovered interrupted recording. Complete flushed proposals retained; incomplete tail ignored and preserved. No fitted-result or physical acceptance claim.",
        )
        if records:
            snapshot = load_history_path(history, records[-1])
            method["snapshot"] = snapshot_payload(snapshot)
        method["rules"] = [
            asdict(
                RuleObservation(
                    "Interrupted search",
                    "unmeasured",
                    "Recovered proposal may be an initial path, derivative probe or rejected trial.",
                )
            )
        ]
    manifest["recovery"] = (
        "Read-only recovery from reference.json and complete JSONL events; no numerical search or native construction."
    )
    destination = output / f"recovered-{uuid4().hex}.json"
    write_document(destination, manifest)
    return destination


def main() -> None:
    """
    Require an unused output directory so every interrupted attempt is retained.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--output", type=Path)
    selection.add_argument("--recover", type=Path)
    args = parser.parse_args()
    print(recover(args.recover) if args.recover is not None else run(args.output))


if __name__ == "__main__":
    main()
