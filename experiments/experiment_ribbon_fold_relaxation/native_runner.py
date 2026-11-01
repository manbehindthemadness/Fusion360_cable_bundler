"""
Replay only changed coupled-contraction routes using the retained material constructor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.runner import ROOT, restore
from experiments.qa_orchestrator import McpClient


@dataclass(frozen=True)
class ReplaySpec:
    """
    Describe one frozen material-route replay without changing the native builder.
    """

    numerical_path: str
    route_suffix: str
    changed_status: str
    component_prefix: str
    body_name: str
    display_x_cm: float
    review_title: str
    pass_label: str
    method_note: str
    question: str
    source_directory: Path
    fidelity_audit: str = "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py"
    baseline_routes: tuple[tuple[str, str], ...] = ()


def replay(spec: ReplaySpec, output: Path) -> None:
    """
    Pin at most four native attempts, preserving all baselines and stopped evidence.
    """
    run = output.resolve()
    run.relative_to(ROOT / "artifacts/verification")
    run.mkdir(parents=True, exist_ok=False)
    numerical_path = spec.numerical_path
    numerical = json.loads((ROOT / numerical_path).read_text())
    if numerical["status"] != "completed":
        raise RuntimeError("Numerical batch is not complete")
    original_numerical_path = numerical_path
    baseline_paths = dict(spec.baseline_routes)
    if baseline_paths:
        for item in numerical["cases"]:
            source = restore(json.loads((ROOT / baseline_paths[item["id"]]).read_text()))
            item["baseline_folds"] = fold_count(source)
        review_path = run / "numerical-review.json"
        review_path.write_text(json.dumps(numerical, indent=2))
        numerical_path = str(review_path.relative_to(ROOT))
    required = {
        "id",
        "status",
        "baseline_folds",
        "final_folds",
        "baseline_length_mm",
        "final_length_mm",
        "reduction_seconds",
    }
    if any(not required.issubset(item) for item in numerical["cases"]):
        raise RuntimeError("Native review metadata incomplete; stop before construction")
    cases = [
        {
            "id": item["id"],
            "contracted": str(
                Path(original_numerical_path).parent / f"{item['id']}-{spec.route_suffix}.json"
            ),
            "baseline_native": f"artifacts/verification/ribbon_fidelity221/{item['id']}-native.json",
        }
        for item in numerical["cases"]
        if item["status"] == spec.changed_status
    ]
    if len(cases) > 4:
        raise RuntimeError("At most four changed native cases in this comparison")
    audit_paths = {ROOT / spec.fidelity_audit}
    if spec.fidelity_audit != "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py":
        audit_paths.update((ROOT / spec.fidelity_audit).parent.glob("*.py"))
    paths = {
        *Path(__file__).parent.glob("*.py"),
        *spec.source_directory.glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_contraction").glob("*.py"),
        *(ROOT / "experiments/experiment_ribbon_fold_route").glob("*.py"),
        ROOT / "experiments/experiment_ribbon_bend_reduction/review.py",
        ROOT / "experiments/experiment_ribbon_bend_reduction/closure.py",
        ROOT / "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py",
        *audit_paths,
        ROOT / "experiments/experiment_optional_appearance/host.py",
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        ROOT / "devtools/ribbon_analysis/end_profiles.py",
        ROOT / "devtools/ribbon_analysis/budget.py",
        ROOT / numerical_path,
        ROOT / original_numerical_path,
        ROOT / Path(original_numerical_path).with_name("plan.json"),
        *(ROOT / p for p in baseline_paths.values()),
        *(ROOT / item[key] for item in cases for key in ("contracted", "baseline_native")),
        ROOT / "experiment_testing_rules.txt",
        ROOT / "rollback_end_loft_notes.txt",
    }
    plan = {
        "root": str(ROOT),
        "cases": cases,
        "started": time.time(),
        "numerical_results": numerical_path,
        "original_numerical_results": original_numerical_path,
        "baseline_routes": spec.baseline_routes,
        "transactions": "Native construction/audit commits in a separate MCP call before guide/panel review; a review error cannot roll back a successfully committed body.",
        "component_prefix": spec.component_prefix,
        "body_name": spec.body_name,
        "display_x_cm": spec.display_x_cm,
        "review_title": spec.review_title,
        "pass_label": spec.pass_label,
        "method_note": spec.method_note,
        "question": spec.question,
        "fidelity_audit": spec.fidelity_audit,
        "unchanged_not_rebuilt": [
            item["id"] for item in numerical["cases"] if item["status"] == "unchanged"
        ],
        "scope": "Four examined development inputs, each changed result attempted once;0newsolves/refinements/retries in Fusion. Keep originals and all earlier variants. Shared material builder/profile unchanged; named audit recorded explicitly. New bodies visible, hidden original guides/cap profiles retained.",
        "limits": {
            "case_seconds": 120,
            "batch_seconds": 600,
            "native_attempts": 4,
            "rss_kib": 4194304,
            "launch_rss_kib": 3984588,
            "review_seconds_per_case": 45,
        },
        "prediction": "Unknown kernel/fidelity outcomes; numerical contact separated. No complete physical or universal construction guarantee.",
        "stop": "First source/API/resource/kernel/fidelity/review error stops remaining cases. Preserve failed/partial evidence and all unattempted configurations; no automatic retry/refinement.",
        "sources": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        },
    }
    (run / "plan.json").write_text(json.dumps(plan, indent=2))
    for relative in plan["sources"]:
        copied = run / "sources" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((ROOT / relative).read_bytes())
    client = McpClient("http://127.0.0.1:27182/mcp", 180)
    client.initialize()
    summary = {
        "status": "running",
        "cases": [],
        "unattempted": [item["id"] for item in cases],
        "unchanged_not_rebuilt": plan["unchanged_not_rebuilt"],
    }
    try:
        for entry in cases:
            script = (
                "def run(context):\n import importlib\n from experiments.experiment_ribbon_contraction import native\n importlib.reload(native)\n native.build("
                + repr(str(run))
                + ", "
                + repr(entry["id"])
                + ")\n"
            )
            response = client.call_tool(
                "fusion_mcp_execute",
                {"featureType": "script", "object": {"script": script, "readOnly": False}},
            )
            (run / f"{entry['id']}-response.json").write_text(json.dumps(response))
            path = run / f"{entry['id']}-native.json"
            if not path.exists():
                raise RuntimeError("Missing native result: " + json.dumps(response)[:3000])
            row = json.loads(path.read_text())
            if row["status"] == "built_and_named_fidelity_checks_pass":
                review_script = (
                    "def run(context):\n import importlib\n from experiments.experiment_ribbon_bend_reduction import review\n importlib.reload(review)\n review.show_case("
                    + repr(str(run))
                    + ", "
                    + repr(entry["id"])
                    + ")\n"
                )
                review_response = client.call_tool(
                    "fusion_mcp_execute",
                    {
                        "featureType": "script",
                        "object": {"script": review_script, "readOnly": False},
                    },
                )
                (run / f"{entry['id']}-review-response.json").write_text(
                    json.dumps(review_response)
                )
            summary["cases"].append(
                {
                    key: value
                    for key, value in row.items()
                    if key not in {"audit", "rss_samples", "kernel_outcome"}
                }
            )
            summary["unattempted"].remove(entry["id"])
            print(json.dumps(summary["cases"][-1]), flush=True)
            if (
                row["status"] != "built_and_named_fidelity_checks_pass"
                or not (run / f"{entry['id']}-review.json").exists()
            ):
                raise RuntimeError(
                    "Native build/audit/review stopped: " + json.dumps(response)[:3000]
                )
        summary["status"] = "completed"
    except (OSError, RuntimeError, ValueError) as error:
        summary.update(status="stopped", error=str(error))
        raise
    finally:
        summary["elapsed_seconds"] = time.time() - plan["started"]
        (run / "result.json").write_text(json.dumps(summary, indent=2))


def main() -> None:
    """
    Replay the original265coupled-contraction comparison with its preserved defaults.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = ReplaySpec(
        "artifacts/verification/ribbon_relax265/result.json",
        "relaxed",
        "contracted",
        "266 - Coupled fold relaxation - ",
        "Straight-contracted ribbon with relaxed fold angles",
        190,
        "Straight contraction with fold relaxation",
        "Coupled contraction",
        "Fixed crease directions and radii; bounded descent, no global optimum claim",
        "Do the changed straight-contracted/fold-relaxed plans retain native material fidelity?",
        Path(__file__).parent,
    )
    replay(spec, args.output)


if __name__ == "__main__":
    main()
