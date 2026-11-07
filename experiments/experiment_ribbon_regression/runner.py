"""
Run a bounded, source-pinned numerical regression with one isolated process per frozen gym case.

Invoke with --output artifacts/... and optionally --baseline artifacts/... .
Fusion is not required. Native construction and physical audits are never attempted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_locked_solver.lock import ROOT, verify
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve

from .corpus import CORPUS, load, targets


def _write(path: Path, payload: dict[str, Any]) -> None:
    """
    Create immutable JSON evidence; replacing an earlier result is an error.
    """
    with path.open("x") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _pins() -> dict[str, str]:
    """
    Pin the solver plus the replay implementation and exact corpus bytes.
    """
    pins = verify()
    for path in (CORPUS, Path(__file__), Path(__file__).with_name("corpus.py")):
        pins[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def _length(route: Any) -> float | None:
    """
    Reject malformed result lengths before comparing numerical acceptance or quality.
    """
    if route is None:
        return None
    if not isinstance(route, dict):
        raise ValueError("Regression route needs a structured snapshot")
    value = route.get("material_length_mm")
    if type(value) not in (int, float):
        raise ValueError("Regression route needs a positive finite material length")
    number = cast(float, value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Regression route needs a positive finite material length")
    return float(number)


def _worker(directory: Path, identity: str) -> None:
    """
    Retain mathematical rejection and harness exceptions separately, with every emitted proposal.
    """
    plan = json.loads((directory / "plan.json").read_text())
    case = next(case for case in plan["cases"] if case["id"] == identity)
    if _pins() != plan["sources"]:
        raise RuntimeError("Regression source drift before solve")
    started, last_check = perf_counter(), perf_counter()

    def checkpoint() -> None:
        """
        Enforce unchanged source, cancellation,15wall seconds and4GiB sampled peak RSS.
        """
        nonlocal last_check
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss = peak if sys.platform == "darwin" else peak * 1024
        if (directory / "cancel").exists() or perf_counter() - started > 15 or rss >= 4294967296:
            raise TimeoutError("Regression execution resource/cancellation gate")
        if perf_counter() - last_check >= 0.5:
            if _pins() != plan["sources"]:
                raise RuntimeError("Regression source drift during solve")
            last_check = perf_counter()

    def record(event: dict[str, Any]) -> None:
        """
        Flush proposals immediately so a killed worker still leaves its diagnostic evidence.
        """
        with (directory / f"{identity}-trials.jsonl").open("a") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")

    payload: dict[str, Any] = {"case": identity, "route": None, "first_pass": None}
    try:
        result = solve(
            targets(case["targets"]),
            Settings.parse(case["settings"]),
            checkpoint,
            record,
            native_point_tolerance_mm=case["native_point_tolerance_mm"],
        )
        payload.update(
            detail=result.detail,
            route=snapshot(result.route) if result.route else None,
            first_pass=snapshot(result.first_pass) if result.first_pass else None,
        )
        if result.route is not None and result.detail.get("contact") != "separated":
            raise ArithmeticError("Strict regression accepted uncertified geometry")
        if _pins() != plan["sources"]:
            raise RuntimeError("Regression source drift after solve")
    except (ArithmeticError, OSError, RuntimeError, TimeoutError, TypeError, ValueError) as error:
        # A harness/resource error halts the parent; it is never a numerical rejection or pass.
        payload["error"] = f"{type(error).__name__}: {error}"
    payload.update(
        wall_seconds=perf_counter() - started,
        peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        native_construction="unattempted",
        native_fidelity="unmeasured",
        full_physical_audit="unmeasured",
    )
    _write(directory / f"{identity}.json", payload)


def run(directory: Path, baseline: Path | None = None) -> dict[str, Any]:
    """
    Freeze all cases before execution; stop on the first regression, hard error or phase limit.

    Each phase permits 73 executions, 120 wall seconds, with no launch after 103 seconds.
    Baseline numerical rejections are retained while later cases are measured.
    Candidate acceptance loss or increased length above1e-7mm stops the phase;
    unsuccessful and unattempted cases remain in the result. No automatic retry occurs.
    """
    corpus = load()
    if len(corpus["cases"]) > 73:
        raise ValueError("A larger corpus requires a newly reviewed execution budget")
    pins = _pins()
    baseline_pins = None
    if baseline is not None:
        previous = json.loads((baseline / "plan.json").read_text())
        completed = json.loads((baseline / "result.json").read_text())
        if previous["cases"] != corpus["cases"] or completed.get("stop"):
            raise ValueError("Baseline needs the same complete frozen corpus")
        baseline_pins = hashlib.sha256((baseline / "result.json").read_bytes()).hexdigest()
    directory.mkdir(parents=True, exist_ok=False)
    _write(
        directory / "plan.json",
        {
            "question": "Compare compact construction and recovery across the complete archived gym development corpus, preserving physical gates and finite work budgets. Fixed targets; solver may reroute. No native work or fresh holdout claim.",
            "sources": pins,
            "cases": corpus["cases"],
            "baseline": str(baseline) if baseline else None,
            "baseline_result_sha256": baseline_pins,
            "limits": {
                "executions": len(corpus["cases"]),
                "per_execution_seconds": 15,
                "subprocess_seconds": 17,
                "phase_seconds": 120,
                "launch_cutoff_seconds": 103,
                "rss_bytes": 4294967296,
                "native_attempts": 0,
            },
            "stop": "First accepted-control loss, length regression, source/resource/harness error or cancellation. Preserve all outcomes and unattempted inputs. No retries or budget increases.",
        },
    )
    started = perf_counter()
    rows: list[dict[str, Any]] = []
    stopped = None
    for case in corpus["cases"]:
        identity = case["id"]
        if perf_counter() - started >= 103 or (directory / "cancel").exists():
            stopped = "Phase scheduling/cancellation gate"
            break
        try:
            if _pins() != pins:
                raise RuntimeError("Regression source drift before worker launch")
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "experiments.experiment_ribbon_regression.runner",
                    "--worker",
                    str(directory),
                    identity,
                ],
                capture_output=True,
                text=True,
                timeout=17,
                cwd=ROOT,
                check=False,
            )
            if process.returncode:
                (directory / f"{identity}.log").write_text(process.stdout + process.stderr)
                raise RuntimeError(f"Regression worker exited {process.returncode}")
            result = json.loads((directory / f"{identity}.json").read_text())
            route = result.get("route")
            length = _length(route)
            row = {
                "case": identity,
                "accepted": route is not None and "error" not in result,
                "length_mm": length,
                "cpu_seconds": result.get("detail", {}).get("cpu_seconds"),
                "error": result.get("error"),
            }
            if baseline:
                before = json.loads((baseline / f"{identity}.json").read_text())
                old_route = before.get("route")
                old_length = _length(old_route)
                row.update(
                    baseline_accepted=old_route is not None and "error" not in before,
                    baseline_length_mm=old_length,
                    route_equal=route == old_route,
                    regression=old_length is not None
                    and (length is None or not row["accepted"] or length > old_length + 1e-7),
                )
            rows.append(row)
            if row["error"] or row.get("regression"):
                stopped = f"{identity}: {row['error'] or 'representative regression'}"
                break
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            rows.append({"case": identity, "accepted": False, "error": str(error)})
            stopped = f"{identity}: {error}"
            break
    try:
        if _pins() != pins:
            stopped = "Regression source drift at phase completion"
    except RuntimeError as error:
        stopped = str(error)
    if perf_counter() - started > 120:
        stopped = "Phase wall-time limit"
    result = {
        "planned": len(corpus["cases"]),
        "evaluated": len(rows),
        "accepted": sum(row["accepted"] for row in rows),
        "rows": rows,
        "unattempted": [case["id"] for case in corpus["cases"][len(rows) :]],
        "stop": stopped,
        "wall_seconds": perf_counter() - started,
        "native_attempts": 0,
        "native_failure_rate": "unmeasured",
        "full_physical_audits": 0,
    }
    _write(directory / "result.json", result)
    return result


def main() -> None:
    """
    Run one explicit bounded phase or one internal isolated worker, never a range tester.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--worker", nargs=2, metavar=("DIRECTORY", "CASE"))
    args = parser.parse_args()
    if args.worker:
        _worker(Path(args.worker[0]), args.worker[1])
    elif args.output:
        result = run(args.output, args.baseline)
        print(json.dumps({key: value for key, value in result.items() if key != "rows"}))
        if result["stop"]:
            raise SystemExit(1)
    else:
        parser.error("Supply --output")


if __name__ == "__main__":
    main()
