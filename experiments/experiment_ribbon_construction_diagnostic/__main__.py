"""
Capture existing frozen route/journal evidence once; requires project SDK, no Fusion or solver execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter, process_time

from devtools.ribbon_analysis.construction.journal import Journal
from devtools.ribbon_analysis.construction.resources import budget
from devtools.ribbon_analysis.construction.view import export
from experiments.experiment_ribbon_contraction.runner import restore

from .adapter import EventBridge, assembly, inputs

ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    """
    Identify current source/input bytes without importing or executing archived code.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """
    Preserve bounded display-only replay and explicitly separate saved runs and evidence bases.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", type=Path, required=True)
    parser.add_argument("--events", type=Path, nargs="*", default=[])
    parser.add_argument(
        "--chain",
        required=True,
        help="Explicit unchanged-topology identity, never guessed across different constructions",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.relative_to(ROOT / "artifacts")
    paths = [args.route.resolve(), *(path.resolve() for path in args.events)]
    for path in paths:
        path.relative_to(ROOT)
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Frozen input exceeds32MiB display allowance")
    directory.mkdir(parents=True, exist_ok=False)
    started, cpu = perf_counter(), process_time()
    sources = [
        *Path(__file__).parent.glob("*.py"),
        *(ROOT / "devtools/ribbon_analysis/construction").glob("*.*"),
        ROOT / "experiments/experiment_ribbon_fold_route/geometry.py",
        ROOT / "devtools/ribbon_analysis/isometric_fold.py",
        *paths,
    ]
    pins = {str(path.relative_to(ROOT)): digest(path) for path in sources if path.is_file()}
    guard = budget(10)
    log = Journal(
        directory / "trace.jsonl",
        "Construction inspection · " + args.chain,
        {
            "scope": "one saved gym layout; no new solve/build/audit or validation credit",
            "sources": pins,
            "topology_identity": args.chain,
            "missing_native_stage": "native construction was not recorded in these inputs",
        },
    )
    try:
        route = restore(json.loads(paths[0].read_text()))
        context = inputs(log, route)
        assembly(log, route, args.chain, context)
        for journal_path in paths[1:]:
            guard.check("read archived execution journal")
            log.emit(
                "input",
                "Saved execution journal: " + journal_path.parent.name,
                "reference",
                "observed",
                context,
                {
                    "journal": str(journal_path.relative_to(ROOT)),
                    "warning": "Separate saved execution; no material snapshot carried across journal boundaries.",
                },
            )
            bridge = EventBridge(log, context, stable_chain=args.chain)
            with journal_path.open() as stream:
                for line in stream:
                    guard.check("capture recorded construction event")
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("Archived solver event must be an object")
                    bridge(event)
        log.emit(
            "output",
            "Native construction / complete qualification not captured",
            "unavailable",
            "unavailable",
            [],
            {
                "reason": "No native build, output translation or qualification event exists in supplied journals. No geometry created to fill this gap."
            },
        )
    finally:
        log.close()
    guard.check("export construction viewer")
    export(log.path, directory / "viewer.html")
    if any(digest(ROOT / name) != expected for name, expected in pins.items()):
        raise RuntimeError("Construction capture source/input drift")
    receipt = {
        "steps": log.steps,
        "points": log.points,
        "bytes": log.bytes,
        "wall_seconds": perf_counter() - started,
        "cpu_seconds": process_time() - cpu,
        "samples": guard.samples,
        "new_solves": 0,
        "native_attempts": 0,
        "new_physical_audits": 0,
        "fresh_configurations": 0,
        "sources": pins,
    }
    with (directory / "capture.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
    print(
        json.dumps(
            {key: value for key, value in receipt.items() if key not in ("sources", "samples")}
        )
    )


if __name__ == "__main__":
    main()
