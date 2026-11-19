"""
Capture one bounded endpoint-only terminal construction, with no saved route initialization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.construction.journal import Journal
from devtools.ribbon_analysis.construction.resources import budget
from devtools.ribbon_analysis.construction.view import export
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_constrained_construction.disjunction import Work
from experiments.experiment_ribbon_constrained_construction.envelopes import constraints
from experiments.experiment_ribbon_constrained_construction.frontier import Case, Frontier
from experiments.experiment_ribbon_constrained_construction.linear import Problem, Row
from experiments.experiment_ribbon_constrained_construction.terminal_approaches import (
    chains,
    corridors,
)
from experiments.experiment_ribbon_constrained_construction.timing import DiagnosticClock
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware

from .origin import OriginTrace

ROOT = Path(__file__).resolve().parents[2]


def write(path: Path, value: Any) -> None:
    """
    Retain an exclusive finite receipt without overwriting historical evidence.
    """
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def main() -> None:
    """
    Execute exactly once with existing finite limits and observed, append-only origin history.

    Input must contain only targets and radius. This replay supplies diagnostic
    evidence, never fresh-layout or native/physical qualification credit.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source, directory = args.input.resolve(), args.output.resolve()
    source.relative_to(ROOT / "artifacts/verification")
    directory.relative_to(ROOT / "artifacts/verification")
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"targets", "radius_mm"}:
        raise ValueError("Endpoint-only targets and radius required; no route accepted")
    target = Targets.capture(
        Targets(
            **{
                key: Vector3(**item) if isinstance(item, dict) else item
                for key, item in value["targets"].items()
            }
        )
    )
    boundary = Boundary(target, value["radius_mm"])
    directory.mkdir(parents=True, exist_ok=False)
    write(
        directory / "plan.json",
        {
            "scope": "one retained gym E layout, from endpoint-only input; tracing only, no algorithm change",
            "input": str(source.relative_to(ROOT)),
            "limits": {
                "preparation_wall_seconds": 10,
                "allocation_wall_seconds": 2,
                "outer_wall_seconds": 30,
                "lp_nodes": 64,
                "intersections": 4096,
                "maximum_roots": 8,
                "maximum_folds": 6,
                "cpu_target_seconds": 0.4,
                "cpu_action": "record overrun, continue bounded capture",
                "rss_gib": 4,
                "launch_rss_gib": 3.8,
                "minimum_free_percent": 10,
            },
            "stops": "source/resource/cancellation/recorder errors propagate with prefix retained; no retries",
            "native_attempts": 0,
            "independent_physical_audits": 0,
            "fresh_coverage": 0,
        },
    )
    outer = budget(30)

    def check() -> None:
        """
        Enforce actual memory, finite outer wall and explicit cancellation during numerical work.
        """
        if (directory / "cancel").exists():
            raise RuntimeError("Origin capture cancelled")
        outer.check("endpoint-only origin construction")

    paths: set[Path] = set()
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if isinstance(filename, str):
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT) and path.suffix == ".py":
                paths.add(path)
    paths.update(
        path
        for path in (ROOT / "devtools/ribbon_analysis/construction").glob("*.*")
        if path.is_file()
    )
    paths.update(
        (
            source,
            directory / "plan.json",
            ROOT / "experiment_testing_rules.txt",
            ROOT / "rollback_end_loft_notes.txt",
        )
    )
    pins = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    write(directory / "source-pins.json", pins)
    log = Journal(
        directory / "trace.jsonl",
        "Endpoint-only construction · E origin",
        {
            "sources": pins,
            "input_scope": "endpoint-only; historical gym diagnostic",
            "physical_qualification": "not attempted",
        },
    )
    observer = OriginTrace(log, boundary)
    work = Work()
    hardware = Hardware.create(target, Dimensions.scaled(target))
    preparation = DiagnosticClock(check, maximum_wall_seconds=10)
    try:
        derived = chains(boundary, preparation.check, trace=observer)
        cases = []
        for chain in derived:
            preparation.check()
            model = Model(boundary, chain.topology)
            columns, right = model.straight_equations()
            problem = Problem(
                (1.0,) * len(columns),
                tuple(
                    Row("endpoint " + axis, tuple(column[i] for column in columns), right[i])
                    for i, axis in enumerate("xyz")
                ),
                corridors(model, chain, preparation.check),
            )
            exclusions = constraints(model, hardware, preparation.check)
            observer.prepared(model, problem, exclusions)
            cases.append(
                Case(
                    str(chain.roots),
                    problem,
                    exclusions,
                    target.diameter_mm,
                    sum(fold.material_length_mm for fold in chain.topology.folds),
                )
            )
        prepared_timing = preparation.timing()
        frontier = Frontier(tuple(cases), work, trace=observer)
        clock = DiagnosticClock(check, maximum_wall_seconds=2)
        stop = None
        try:
            frontier.run(clock.check)
        except TimeoutError as error:
            stop = str(error)
        timing = clock.timing()
        choice = frontier.best or frontier.inspection
        if choice is not None:
            model = observer.models[choice.root]
            coordinates = tuple(
                choice.values[i // 2] if i % 2 == 0 else 0.0 for i in range(model.size)
            )
            route = FoldRoute(target, model.pieces(coordinates), boundary.radius_mm)
            write(directory / "route.json", snapshot(route))
            log.emit(
                "output",
                "Selected complete allocation; independent physical qualification unattempted",
                "unresolved",
                "observed",
                observer.context + observer.scene(choice.root, choice.values),
                {
                    "root": choice.root,
                    "material_length_mm": route.material_length_mm,
                    "frontier_status": frontier.status,
                    "stop": stop,
                    "meets_supplied_rows": frontier.best is not None,
                    "native": "unattempted",
                    "independent_physical_audit": "unattempted",
                },
            )
        else:
            log.emit(
                "output",
                "No complete allocation available",
                "unresolved",
                "observed",
                observer.context,
                {"frontier_status": frontier.status, "stop": stop},
            )
    finally:
        log.close()
    check()
    export(log.path, directory / "viewer.html")
    if any(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected
        for name, expected in pins.items()
    ):
        raise RuntimeError("Origin capture source drift")
    cpu = prepared_timing.cpu_seconds + timing.cpu_seconds
    receipt = {
        "preparation": asdict(prepared_timing),
        "allocation": asdict(timing),
        "cpu_seconds_including_observer": cpu,
        "cpu_overrun_seconds": max(0.0, cpu - 0.4),
        "hook_capture_cpu_seconds": observer.cpu_seconds,
        "hook_capture_wall_seconds": observer.wall_seconds,
        "roots": len(cases),
        "roots_relaxed": frontier.roots_relaxed,
        "frontier_status": frontier.status,
        "stop": stop,
        "work": asdict(work),
        "steps": log.steps,
        "points": log.points,
        "bytes": log.bytes,
        "selected_root": choice.root if choice else None,
        "material_length_mm": choice.length_mm if choice else None,
        "native_attempts": 0,
        "physical_audits": 0,
        "fresh_coverage": 0,
        "samples": outer.samples,
    }
    write(directory / "capture.json", receipt)
    print(
        json.dumps({key: item for key, item in receipt.items() if key not in ("samples", "work")})
    )


if __name__ == "__main__":
    main()
