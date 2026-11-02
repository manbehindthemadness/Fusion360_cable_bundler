"""
Isolate branch selection on all twelve retained424gym layouts without new route construction.
"""

from __future__ import annotations

import json
import resource
import sys
from dataclasses import asdict
from functools import partial
from pathlib import Path
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_locked_solver.lock import ROOT, verify
from experiments.experiment_ribbon_spline_guide.guide import Guide

from .selection import Branch, select
from .validation import digest


def _certify(candidate: Branch, *, outcome: dict[str, Any], checkpoint: Callable[[], None]) -> bool:
    """
    Retain conservative contact and timing for one explicitly bound case.
    """
    checkpoint()
    started = perf_counter()
    contact = inspect_contact(candidate.route, maximum_pairs=1024, checkpoint=checkpoint)
    outcome["contacts"].append(
        {"roots": candidate.roots, "contact": asdict(contact), "seconds": perf_counter() - started}
    )
    return contact.status == "separated"


def main() -> None:
    """
    Replay frozen branches with unchanged contact limits and retain every case, including regressions.
    """
    source = ROOT / "artifacts/verification/ribbon_holdout424"
    original = json.loads((source / "result.json").read_text())
    if original["status"] != "completed":
        raise RuntimeError("Completed424baseline required")
    out = ROOT / "artifacts/verification/ribbon_selection428"
    out.mkdir(exist_ok=False)
    ids = ["gym424-08", "gym424-02", "gym424-05", "gym424-09"]
    ids.extend(row["id"] for row in original["cases"] if row["id"] not in ids)
    paths = (
        *Path(__file__).parent.glob("*.py"),
        source / "plan.json",
        source / "result.json",
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
        *(source / f"{name}-trials.jsonl" for name in ids),
        *(source / f"{name}-input.json" for name in ids),
    )
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    pins = verify()
    plan = {
        "question": "Does certified-baseline dominance selection reduce excursions without spending more than two contact certificates or worsening routing preferences?",
        "revision_of": "427stopped after9/12cases:08improved but07shortened while RMS worsened. Remaining10/11/12unattempted. Preserve427and its frozen source.428does not trade length for guide agreement: certify original first midpoint-ranked branch; if safe, use the spare certificate only for one strictly shorter branch with non-increasing guide RMS/direction. Retain safe baseline if alternative rejects. If original first fails, certify original second, unchanged. No new geometry/parameters or larger contact budget.",
        "cases": ids,
        "sources": pins,
        "experiment_sources": hashes,
        "procedure": "Restore every feature_branch/closed geometry from424ledgers. Apply selection.select certified-baseline dominance rule, at most two unchanged1024pair contact certificates. Exact same precomputed branches/guide/material/cap contract; no construction, allocation, angular, radius, station, smoothing or seed changes. Trigger08and collateral02/05/09first, remaining retained cases afterward. Whole-guide metric uses existing65ordered stations; no global optimum guarantee.",
        "baseline": "Exact424numerical outcomes and geometry, same2contact limit. Rechecking selected branches is an experiment expense; excludes original construction and is not an end-to-end speed benchmark.",
        "acceptance": "No route until thick contact separates; caps<=1e-7/material metric<=1e-10 and snapshot target/radius contract unchanged. Quality gain=shorter material with non-increasing whole-guide RMS/direction versus424accepted route. Lesser quality or lost feasibility reported separately, never masked by aggregate gains. Previously unresolved inputs have unknown feasibility.",
        "limits": {
            "case_seconds": 4,
            "phase_seconds": 48,
            "rss_bytes": 4294967296,
            "contact_attempts": 2,
            "contact_pairs": 1024,
            "new_constructions": 0,
            "native_attempts": 0,
        },
        "coverage": "12examined development configurations, not fresh holdouts.08trigger;02gentle3conductor,05shallow-zone8conductor,09spatial12conductor collateral mechanics. Invalid-oracle accuracy and full physical audit unmeasured.",
        "stop": "First source/input/resource/harness/accepted-gate failure stops remaining work. Lost previously accepted feasibility or worsened length/guide quality stops after retaining its disposition. No source/tolerance/budget changes or automatic refinement. Contact-unresolved is not physical impossibility.",
        "later_native": "No native build authorized by this phase. Review numerical results first; any later native validation requires separately frozen source/input scope, no reuse of424native fidelity for changed routes.",
    }
    (out / "plan.json").write_text(json.dumps(plan, indent=2))
    for path in Path(__file__).parent.glob("*.py"):
        (out / (path.name + ".frozen")).write_bytes(path.read_bytes())
    phase, cpu = perf_counter(), process_time()
    report: dict[str, Any] = {
        "status": "running",
        "cases": [],
        "unattempted": ids.copy(),
        "native_attempts": 0,
        "new_constructions": 0,
        "full_physical_audits": 0,
    }
    try:
        for name in ids:
            started, case_cpu = perf_counter(), process_time()
            last_sources = started

            def checkpoint(case_started: float = started) -> None:
                """
                Bound replay and source/input verification without renewing any experiment limit.
                """
                nonlocal last_sources
                now = perf_counter()
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss = peak if sys.platform == "darwin" else peak * 1024
                if now - case_started > 4 or now - phase > 48 or rss >= 4294967296:
                    raise TimeoutError("Frozen428budget")
                if now - last_sources >= 0.5:
                    if verify() != pins or any(digest(ROOT / p) != h for p, h in hashes.items()):
                        raise RuntimeError("428source/input drift")
                    last_sources = now

            baseline = next(row for row in original["cases"] if row["id"] == name)
            row: dict[str, Any] = {
                "id": name,
                "baseline": baseline,
                "contacts": [],
                "native": "not_attempted",
            }
            report["cases"].append(row)
            report["unattempted"].remove(name)
            branches = []
            with (source / f"{name}-trials.jsonl").open() as stream:
                for line in stream:
                    checkpoint()
                    event = json.loads(line)
                    if event["stage"] == "feature_branch" and event["status"] == "closed":
                        route = restore(event["route"])
                        branches.append(
                            Branch.measure(
                                tuple(event["roots"]),
                                route,
                                Guide.create(route.targets),
                                event["site_error_mm2"],
                            )
                        )
            branches.sort(key=lambda item: item.priority)
            row["ranked"] = [
                {
                    "roots": b.roots,
                    "length_mm": b.route.material_length_mm,
                    "guide": asdict(b.guide),
                }
                for b in branches
            ]
            row["status"] = "no_separated_chain" if branches else "no_fixed_radius_closure"
            branch = select(branches, partial(_certify, outcome=row, checkpoint=checkpoint))
            if branch is not None:
                route = branch.route
                if cap_error(route) > 1e-7 or material_error(route) > 1e-10:
                    raise ArithmeticError("428accepted physical gate failure")
                row.update(
                    status="separated",
                    roots=branch.roots,
                    length_mm=route.material_length_mm,
                    guide=asdict(branch.guide),
                    cap_error=cap_error(route),
                    material_metric=material_error(route),
                )
                (out / f"{name}-route.json").write_text(json.dumps(snapshot(route), indent=2))
            row["quality"] = "previously_unresolved"
            if baseline["status"] == "separated":
                if row["status"] != "separated":
                    row["quality"] = "lost_numerical_feasibility"
                elif (
                    row["length_mm"] > baseline["length_mm"] + 1e-8
                    or row["guide"]["rms_mm"] > baseline["guide"]["rms_mm"] + 1e-8
                    or row["guide"]["mean_direction_loss"]
                    > baseline["guide"]["mean_direction_loss"] + 1e-8
                ):
                    row["quality"] = "quality_regression"
                else:
                    row["quality"] = (
                        "compact_improvement"
                        if row["length_mm"] < baseline["length_mm"] - 1e-8
                        else "retained"
                    )
            checkpoint()
            row.update(seconds=perf_counter() - started, cpu_seconds=process_time() - case_cpu)
            (out / f"{name}-result.json").write_text(json.dumps(row, indent=2))
            print(
                json.dumps({k: v for k, v in row.items() if k not in ("baseline", "ranked")}),
                flush=True,
            )
            if row["quality"] in ("lost_numerical_feasibility", "quality_regression"):
                raise RuntimeError("428regression stop: " + name)
        if verify() != pins or any(digest(ROOT / p) != h for p, h in hashes.items()):
            raise RuntimeError("428final source/input drift")
        report["status"] = "completed"
    except (
        ArithmeticError,
        KeyError,
        OSError,
        RuntimeError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as error:
        report.update(status="stopped", error=str(error))
        raise
    finally:
        report.update(seconds=perf_counter() - phase, cpu_seconds=process_time() - cpu)
        (out / "result.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
