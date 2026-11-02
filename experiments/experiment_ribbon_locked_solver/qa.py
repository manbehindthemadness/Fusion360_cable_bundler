"""
Freeze four new gym configurations and measure cold selected-solver and native outcomes separately.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

from devtools.ribbon_analysis.gym import Config, generate
from devtools.ribbon_analysis.gym.handoff import identity
from devtools.ribbon_analysis.inspection.archive import targets_payload, write_document
from experiments.qa_orchestrator import McpClient

from .lock import ROOT, verify
from .settings import VERSION, Settings

CONFIGS = (
    Config(seed=2026110101, lines=1, diameter_mm=0.75),
    Config(seed=2026110102, lines=3, diameter_mm=1.5),
    Config(seed=2026110103, lines=6, diameter_mm=3.0),
    Config(seed=2026110104, lines=3, diameter_mm=1.5, void_percent=900, zone_percent=150),
)


def numerical(directory: Path, document_id: str) -> None:
    """
    Freeze every input before solving; preserve all finite-family failures in the denominator.
    """
    directory.relative_to(ROOT / "artifacts/verification")
    directory.mkdir(parents=True, exist_ok=False)
    pins = verify()
    settings = asdict(Settings(material_uv=True))
    cases = []
    for index, config in enumerate(CONFIGS):
        scene = generate(config)
        name = f"gym-cold-{index + 1}"
        job = directory / name
        job.mkdir()
        plan = {
            "version": VERSION,
            "result_id": "run-" + name + ":" + VERSION,
            "targets": targets_payload(scene.targets),
            "gym": scene.payload(),
            "settings": settings,
            "sources": pins,
            "document_id": document_id,
            "limits": {"numerical_seconds": 120, "native_seconds": 120, "rss_bytes": 4294967296},
            "native_prediction": "Unknown; endpoint gym geometry is not an avoidance boundary",
        }
        write_document(job / "plan.json", plan)
        cases.append(
            {
                "id": name,
                "gym_id": identity(scene.payload()),
                "config": asdict(config),
                "job": str(job.relative_to(ROOT)),
            }
        )
    write_document(
        directory / "qa-plan.json",
        {
            "version": VERSION,
            "cases": cases,
            "settings": settings,
            "sources": pins,
            "coverage": "Four new predeclared complete gym configurations; no outcome filtering or fixture tuning. Selected algorithm locked before results. No unseen reliability guarantee.",
            "limits": {
                "cases": 4,
                "numerical_seconds_per_case": 120,
                "native_seconds_per_case": 120,
                "seconds_per_phase": 600,
                "rss_bytes": 4294967296,
                "native_attempts": 4,
            },
            "stop": "First source/resource/API/harness/native fidelity failure stops affected phase; unresolved finite construction remains explicit, no retry or tolerance changes",
        },
    )
    started = perf_counter()
    report: dict[str, Any] = {
        "status": "running",
        "cases": [],
        "unattempted": [c["id"] for c in cases],
        "native_attempts": 0,
    }
    try:
        for case in cases:
            if perf_counter() - started > 600 or verify() != pins:
                raise RuntimeError("Frozen numerical phase budget/source guard")
            job = ROOT / case["job"]
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "experiments.experiment_ribbon_locked_solver.worker",
                    str(job),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=130,
                check=False,
            )
            (job / "worker.log").write_text(completed.stdout + completed.stderr)
            if completed.returncode or not (job / "manifest.json").is_file():
                raise RuntimeError("Numerical worker failed: " + case["id"])
            manifest = json.loads((job / "manifest.json").read_text())
            method = manifest["solvers"][0]
            detail = (
                json.loads((job / "numerical-result.json").read_text())
                if (job / "numerical-result.json").exists()
                else {}
            )
            row = {
                "id": case["id"],
                "status": method["status"],
                "detail": method["detail"],
                "numerical": detail,
                "worker_seconds": manifest["seconds"],
                "worker_cpu_seconds": manifest["cpu_seconds"],
                "job": case["job"],
            }
            report["cases"].append(row)
            report["unattempted"].remove(case["id"])
            print(json.dumps(row), flush=True)
            if method["status"] == "stopped":
                raise RuntimeError("Frozen numerical phase stopped: " + method["detail"])
        report["status"] = "completed"
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        report.update(status="stopped", error=str(error))
        raise
    finally:
        report["elapsed_seconds"] = perf_counter() - started
        write_document(directory / "numerical-results.json", report)


def native(directory: Path) -> None:
    """
    Attempt accepted cases once in Fusion, retaining every unresolved/skipped configuration.
    """
    plan = json.loads((directory / "qa-plan.json").read_text())
    numerical_report = json.loads((directory / "numerical-results.json").read_text())
    if numerical_report["status"] != "completed" or plan["sources"] != verify():
        raise RuntimeError(
            "Native QA requires completed numerical phase and unchanged locked sources"
        )
    destination = directory / "native-results.json"
    if destination.exists():
        raise RuntimeError("Native phase already recorded; no automatic retry")
    started = perf_counter()
    report: dict[str, Any] = {
        "status": "running",
        "cases": [],
        "unattempted": [c["id"] for c in plan["cases"]],
    }
    client = McpClient("http://127.0.0.1:27182/mcp", 180)
    client.initialize()
    try:
        for index, case in enumerate(plan["cases"]):
            if perf_counter() - started > 600 or plan["sources"] != verify():
                raise RuntimeError("Frozen native phase budget/source guard")
            job = ROOT / case["job"]
            if not (job / "route.json").is_file():
                report["cases"].append(
                    {
                        "id": case["id"],
                        "status": "unattempted_numerical_unresolved",
                        "native_attempted": 0,
                        "built": 0,
                        "full_physical_audit": 0,
                    }
                )
                report["unattempted"].remove(case["id"])
                continue
            job_plan = json.loads((job / "plan.json").read_text())
            script = (
                "def run(context):\n from pathlib import Path\n from experiments.experiment_ribbon_locked_solver.native import NativeOwner\n NativeOwner("
                + repr(job_plan["document_id"])
                + ", "
                + repr(650 + index * 30)
                + ").build(Path("
                + repr(str(job))
                + "))\n"
            )
            response = client.call_tool(
                "fusion_mcp_execute",
                {"featureType": "script", "object": {"script": script, "readOnly": False}},
            )
            write_document(job / "native-response.json", response)
            if not (job / "native-result.json").is_file():
                raise RuntimeError("Missing native result: " + json.dumps(response)[:2000])
            row = json.loads((job / "native-result.json").read_text())
            report["cases"].append(
                {
                    "id": case["id"],
                    **{k: v for k, v in row.items() if k not in {"audit", "rss_samples"}},
                }
            )
            report["unattempted"].remove(case["id"])
            print(json.dumps(report["cases"][-1]), flush=True)
            if row["status"] != "built_and_named_fidelity_checks_pass":
                raise RuntimeError("Native selected-solver QA stopped: " + case["id"])
        report["status"] = "completed"
    except (OSError, RuntimeError, ValueError) as error:
        report.update(status="stopped", error=str(error))
        raise
    finally:
        report["elapsed_seconds"] = perf_counter() - started
        write_document(destination, report)


def main() -> None:
    """
    Run one explicit frozen phase; never silently enlarge a stopped batch.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("numerical", "native"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--document-id", default="86e5d125-ed43-4b89-b175-dcca0966fae6")
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.relative_to(ROOT / "artifacts/verification")
    numerical(directory, args.document_id) if args.phase == "numerical" else native(directory)


if __name__ == "__main__":
    main()
