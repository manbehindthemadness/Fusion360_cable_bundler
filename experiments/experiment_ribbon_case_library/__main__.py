"""
Bookmark selected finished cases or export labelled endpoint-only diagnostics without running a solver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from devtools.ribbon_analysis.inspection.values import json_object

from .library import CaseLibrary
from .recipe import from_plan

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = ROOT / "artifacts/verification/ribbon-case-library/cases.sqlite3"


def _object(path: Path) -> dict[str, Any]:
    """
    Require structured original metadata rather than guessing through null or malformed files.
    """
    return json_object(json.loads(path.read_text()))


def _path(value: Any) -> Path:
    """
    Reject absent or malformed original evidence locations before accessing another file.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Retain an original evidence path")
    return Path(value)


def save_finished(library: CaseLibrary, identifier: str, run: Path, ordinal: int) -> None:
    """
    Bookmark one explicitly selected completed ordinal using original immutable receipts only.
    """
    run_plan = _object(run / "plan.json")
    started = _object(run / "started.json")
    if started.get("identifier") != run_plan.get("identifier"):
        raise ValueError("Original run identity disagrees")
    journal = _path(started.get("journal"))
    rows = [
        json_object(json.loads(line)) for line in (journal / "cases.jsonl").read_text().splitlines()
    ]
    matches = [
        row for row in rows if row.get("event") == "case_finished" and row.get("case") == ordinal
    ]
    if len(matches) != 1:
        raise ValueError("Select one finished original case ordinal")
    row = matches[0]
    job = _path(row.get("job")).resolve()
    evidence = str(job.relative_to(ROOT))
    original = _object(job / "plan.json")
    numerical = _object(job / "numerical-result.json")
    sources = json_object(original.get("sources"))
    if not sources or sources != run_plan.get("sources"):
        raise ValueError("Original case source disagrees with its run")
    source_json = json.dumps(sources, sort_keys=True, separators=(",", ":"), allow_nan=False)
    provenance: dict[str, Any] = {
        "run_id": run_plan.get("identifier"),
        "run_seed": json_object(run_plan.get("specification")).get("seed"),
        "ordinal": ordinal,
        "original_outcome": "passed"
        if row.get("problem") is None
        else "unresolved"
        if numerical.get("status") == "unresolved"
        else "failed",
        "sources_sha256": hashlib.sha256(source_json.encode()).hexdigest(),
        "evidence": evidence,
    }
    library.save(identifier, from_plan(original), provenance)


def main() -> None:
    """
    Keep catalogue commands explicit and disconnected from fresh campaigns and solver execution.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    actions = parser.add_subparsers(dest="action", required=True)
    save = actions.add_parser("save", help="Bookmark a selected finished case; no replay")
    save.add_argument("identifier")
    save.add_argument("run_directory", type=Path)
    save.add_argument("ordinal", type=int)
    actions.add_parser("list", help="List selected diagnostic recipes")
    export = actions.add_parser(
        "export", help="Recreate endpoint-only inspection JSON; no solve/build"
    )
    export.add_argument("identifier")
    export.add_argument("destination", type=Path)
    args = parser.parse_args()
    library = CaseLibrary(args.database)
    if args.action == "save":
        save_finished(library, args.identifier, args.run_directory, args.ordinal)
        print(json.dumps({"saved": args.identifier, "fresh_validation": False}))
    elif args.action == "export":
        library.export(args.identifier, args.destination)
        print(
            json.dumps(
                {
                    "exported": str(args.destination),
                    "fresh_validation": False,
                    "solves": 0,
                    "native_builds": 0,
                }
            )
        )
    else:
        print(
            json.dumps(
                [
                    {"identifier": key, **library.load(key)["provenance"]}
                    for key in library.identifiers()
                ]
            )
        )


if __name__ == "__main__":
    main()
