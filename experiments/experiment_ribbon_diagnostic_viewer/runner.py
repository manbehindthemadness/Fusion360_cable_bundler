"""
Author a diagnostic reference or recover archived search history, without discovery.

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

from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    RuleObservation,
    read_document,
    snapshot_payload,
    targets_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.capture import (
    load_history_path,
    read_history,
)
from devtools.ribbon_analysis.inspection.geometry import freeze_curve
from devtools.ribbon_analysis.inspection.measurements import observations

from .fixture import SpatialSBend
from .procedures import DISCOVERY_REMOVED, source_pins

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


def run(output: Path) -> Path:
    """
    Author one fixed reference with explicit unavailable historical methods.

    No endpoint discovery, seeded fitting, numerical search or native work runs.
    """
    output.mkdir(parents=True, exist_ok=False)
    began = perf_counter()
    fixture = SpatialSBend()
    case = fixture.targets()
    pins = source_pins()
    plan: dict[str, Any] = {
        "question": "Display an authored reference after retirement of path discovery.",
        "cases": [targets_payload(case)],
        "independent_configurations": 1,
        "fixture": asdict(fixture.tightness),
        "analytic_peak_utilization": fixture.curvature(0) * fixture.tightness.minimum_radius_mm,
        "authoring": "Forward-authored compound S with pitch reversal and 90-degree lateral yaw over the same curve; development reference, not a solved holdout.",
        "algorithm": "Reference authoring only; path search and seed-based discovery removed.",
        "rules": "Retained single-circle radius >=3D. Wide-ribbon ratio/scalar/flex unresolved. No self-collision acceptance from legacy sampled screens.",
        "budgets": {"search_evaluations": 0, "native_attempts": 0, "retries": 0},
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
                "detail": DISCOVERY_REMOVED,
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
    manifest = {
        "schema": SCHEMA,
        "targets": targets_payload(case),
        "solvers": methods,
        "plan": "plan.json",
        "sources": pins,
        "independent_cases": {
            "planned": 1,
            "numerically_evaluated": 0,
            "native_attempted": 0,
            "built": 0,
            "fully_audited": 0,
            "unresolved": 1,
        },
        "timings": {"search_seconds": 0.0},
        "overall_seconds": perf_counter() - began,
        "search_evaluations": 0,
        "discovery_available": False,
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
