"""
Freeze and run73's source-pinned SDK-only generalization checks.

Requires the configured project SDK and retained67/69SDK artifacts. No Fusion
connection or native builds occur here. Run as a module with freeze,regression or
fresh. Failures and partial ledgers are written once under ignored artifacts;
resource/source errors stop the phase,while declared search exhaustion retains
an unresolved case and permits remaining preplanned independent inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .generalization_cases import fresh, reserved

if TYPE_CHECKING:
    from .broad_search import SearchLedger

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "artifacts/verification/ribbon_cap_transition/generalization73"
HISTORY = ROOT / "artifacts/verification/ribbon_cap_transition/compatible28"
RETAINED = (3, 17, 38, 12, 8, 7, 11, 13)


def _digest(path: Path) -> str:
    """
    Fingerprint exact file bytes without consulting a remote or changing sources.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources() -> dict[str, str]:
    """
    Capture the numerical experiment and shared analysis implementations.
    """
    paths = [
        path
        for directory in (
            ROOT / "experiments/experiment_ribbon_route_discovery",
            ROOT / "experiments/experiment_ribbon_cap_transition",
            ROOT / "devtools/ribbon_analysis",
        )
        for path in directory.glob("*.py")
    ]
    paths.extend(
        ROOT / name for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt")
    )
    return {str(path): _digest(path) for path in paths}


def _write(path: Path, payload: dict[str, Any]) -> None:
    """
    Preserve a new phase artifact rather than overwriting a prior attempt.
    """
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream)


def _case(data: dict[str, Any]) -> EndpointCase:
    """
    Reconstruct fixed serialized boundary vectors,letting malformed fields fail closed.
    """
    vectors = {"start", "end", "start_tangent", "end_tangent", "start_width", "end_width"}
    if not isinstance(data, dict) or not vectors <= data.keys():
        raise ValueError("Missing boundary vectors.")
    return EndpointCase(
        **{key: Vector3(**value) if key in vectors else value for key, value in data.items()}
    )


def freeze() -> None:
    """
    Freeze all boundary inputs,source bytes and historical comparison snapshots.
    """
    started = perf_counter()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    old_inputs = json.loads((HISTORY / "autonomous49-ledger.json").read_text())["inputs"]
    baselines = {
        str(number): str(
            HISTORY
            / ("autonomous67-ledger.json" if number == 13 else f"autonomous69-{number}-ledger.json")
        )
        for number in RETAINED
    }
    plan = dict(
        revision="73 extracted67;unchanged arithmetic",
        sources=_sources(),
        python=platform.python_version(),
        retained={str(number): old_inputs[str(number)] for number in RETAINED},
        baselines=baselines,
        baseline_pins={path: _digest(Path(path)) for path in baselines.values()},
        fresh=[asdict(case) for case in fresh()],
        reserved=[asdict(case) for case in reserved()],
        case_seconds=16.052295,
        phase_seconds=150.0,
        aggregate_seconds=600.0,
        rss_kib=2097152,
        native_attempts_here=0,
        freeze_seconds=perf_counter() - started,
    )
    _write(DIRECTORY / "plan.json", plan)
    print(json.dumps(dict(plan=str(DIRECTORY / "plan.json"), retained=8, fresh=8, reserved=4)))


def _verify(plan: dict[str, Any]) -> None:
    """
    Reject source or historical evidence drift before another complete case starts.
    """
    if _sources() != plan["sources"]:
        raise RuntimeError("Numerical source drift;preserve this phase and renew its plan.")
    if any(_digest(Path(path)) != pin for path, pin in plan["baseline_pins"].items()):
        raise RuntimeError("Historical baseline drift.")


def _timeless(value: Any) -> Any:
    """
    Compare serialized numerical decisions while excluding explicitly nested timers.
    """
    if isinstance(value, dict):
        return {
            key: _timeless(item)
            for key, item in value.items()
            if key not in ("seconds", "total_seconds", "pair_seconds")
        }
    if isinstance(value, (tuple, list)):
        return [_timeless(item) for item in value]
    return value


def _regression(number: str, ledger: SearchLedger, plan: dict[str, Any]) -> bool:
    """
    Read fitted historical values only AFTER cold search,solely to compare evidence.
    """
    expected = json.loads(Path(plan["baselines"][number]).read_text())
    candidate = ledger.candidate
    if candidate is None:
        return False
    chosen = expected["chosen"]
    decisions = [
        dict(seed=trial.seed.index, phase=trial.phase, metrics=_timeless(trial.metrics))
        for trial in ledger.trials
    ]
    prior = [
        dict(seed=row["seed"], phase=row["phase"], metrics=_timeless(row["metrics"]))
        for row in expected["records"]
    ]
    return (
        list(ledger.selected_short) == expected["selected_short"]
        and ledger.selected_deep == expected["selected_deep"]
        and decisions == prior
        and list(candidate.metrics["coordinates"]) == chosen["metrics"]["coordinates"]
        and _timeless(candidate.path.states) == chosen["states"]
        and _timeless(candidate.path.rates) == chosen["rates"]
    )


def run(phase: str) -> None:
    """
    Evaluate a frozen matrix with per-case/phase/RSS stops and partial-path retention.
    """
    phase_started = perf_counter()
    from devtools.ribbon_analysis import api, budget, constraint_geometry

    from .broad_search import SearchLedger, solve

    plan = json.loads((DIRECTORY / "plan.json").read_text())
    output = DIRECTORY / f"{phase}.json"
    if output.exists():
        raise RuntimeError("Preserve existing phase output.")
    _verify(plan)
    if phase == "fresh":
        regression = json.loads((DIRECTORY / "regression.json").read_text())
        if regression["stop"] or len(regression["rows"]) != 8:
            raise RuntimeError("Retained-case regression phase is incomplete.")
    inputs = (
        list(plan["retained"].items())
        if phase == "regression"
        else [(str(index + 1), data) for index, data in enumerate(plan["fresh"])]
    )
    setup_seconds = perf_counter() - phase_started
    started = phase_started
    case_started = started
    last_memory = started
    rows: list[dict[str, Any]] = []
    stop = None

    def checkpoint() -> None:
        """
        Enforce scheduling limits without hiding a resource failure as infeasibility.
        """
        nonlocal last_memory
        now = perf_counter()
        if now - case_started >= plan["case_seconds"] or now - started >= plan["phase_seconds"]:
            raise RuntimeError("Numerical time cap.")
        if now - last_memory >= 1:
            if budget.resident_kib() >= plan["rss_kib"]:
                raise RuntimeError("RSS cap.")
            last_memory = now

    for number, data in inputs:
        case_started = perf_counter() - (setup_seconds if not rows else 0.0)
        ledger = SearchLedger()
        row: dict[str, Any] = dict(number=number, input=data, native_attempted=False)
        rows.append(row)
        try:
            _verify(plan)
            if budget.resident_kib() >= plan["rss_kib"]:
                raise RuntimeError("RSS cap.")
            case = _case(data)
            solve(case, checkpoint, ledger)
            candidate = ledger.candidate
            if phase == "regression":
                row["arithmetic_match"] = _regression(number, ledger, plan)
                if not row["arithmetic_match"]:
                    raise RuntimeError("Retained-case arithmetic regression.")
            row["eligible"] = False
            if candidate is not None:
                evidence = api.analyze(
                    api.Candidate(f"{phase}73-{number}", candidate.path, case, plan["revision"]),
                    checkpoint,
                    intervals=512,
                )
                panels = {
                    item.key: dict(item.measurements)
                    for item in constraint_geometry.build(evidence)
                }
                intrinsic = any(region.severity == "red" for region in evidence.regions) or any(
                    panels[key].get("utilization", 0) > 1 for key in ("center_bend", "lane_bend")
                )
                row.update(
                    eligible=not intrinsic,
                    panels=panels,
                    chosen=dict(
                        states=candidate.path.states,
                        rates=candidate.path.rates,
                        metrics=candidate.metrics,
                        contact=candidate.contact,
                    ),
                )
                if intrinsic:
                    raise RuntimeError("New intrinsic/cubic finding on a pose/contact handoff.")
            checkpoint()
        except (RuntimeError, ValueError, OSError) as exc:
            # Preserve known experiment/resource failures;unexpected programming errors propagate.
            row["error"] = str(exc)
            stop = str(exc)
        row.update(
            seconds=perf_counter() - case_started,
            stage=ledger.stage,
            selected_short=ledger.selected_short,
            selected_deep=ledger.selected_deep,
            trials=[
                dict(
                    seed=t.seed.index,
                    phase=t.phase,
                    metrics=t.metrics,
                    contact=t.contact,
                    rank=t.rank,
                )
                for t in ledger.trials
            ],
        )
        print(
            json.dumps(
                {
                    key: row.get(key)
                    for key in ("number", "eligible", "arithmetic_match", "seconds", "error")
                }
            ),
            flush=True,
        )
        if stop:
            break
    _write(
        output,
        dict(
            phase=phase,
            plan_pin=_digest(DIRECTORY / "plan.json"),
            rows=rows,
            stop=stop,
            unattempted=[number for number, _ in inputs[len(rows) :]],
            total_seconds=perf_counter() - started,
            rss_kib=budget.resident_kib(),
        ),
    )


def main() -> None:
    """
    Select one declared phase without implicitly rerunning an earlier experiment.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "regression", "fresh"))
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze()
    else:
        run(args.phase)


if __name__ == "__main__":
    main()
