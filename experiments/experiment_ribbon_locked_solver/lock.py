"""
Fingerprint the selected solver's complete executable policy without remote dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .versions import DEFAULT_VERSION, METHODS

ROOT = Path(__file__).resolve().parents[2]
LOCK = Path(__file__).with_name("solver-lock.json")


def sources() -> dict[str, str]:
    """
    Hash maintained numerical, native and coordinate implementations required by this version.
    """
    paths = {*Path(__file__).parent.glob("*.py")}
    paths.update((Path(__file__).parent / "tester").glob("*.py"))
    analysis = ROOT / "devtools/ribbon_analysis"
    paths.update(analysis.rglob("*.py"))
    paths.update(analysis.rglob("*.html"))
    paths.update(analysis.rglob("*.js"))
    for package in (
        "experiment_ribbon_fold_route",
        "experiment_ribbon_joint_route",
        "experiment_ribbon_aesthetic",
        "experiment_ribbon_radius_allocation",
        "experiment_ribbon_bend_reduction",
        "experiment_ribbon_bend_relocation",
        "experiment_ribbon_fold_relaxation",
        "experiment_ribbon_contraction",
        "experiment_ribbon_diagnostic_viewer",
        "experiment_ribbon_feature_insertion",
        "experiment_ribbon_terminal_hardware",
    ):
        paths.update((ROOT / "experiments" / package).glob("*.py"))
    paths.update(
        ROOT / p
        for p in (
            "experiments/experiment_optional_appearance/material.py",
            "experiments/experiment_ribbon_spline_guide/guide.py",
            "experiments/experiment_ribbon_reduced_joints/kinematics.py",
            "experiments/experiment_optional_appearance/host.py",
            "experiments/experiment_ribbon_test_gym/workspace.py",
            "cable_bundler/routing/geometry.py",
            "devtools/ribbon_analysis/contracts.py",
            "devtools/ribbon_analysis/isometric_fold.py",
            "devtools/ribbon_analysis/pinch.py",
            "devtools/ribbon_analysis/budget.py",
            "devtools/ribbon_analysis/end_profiles.py",
            "devtools/ribbon_analysis/provenance.py",
            "devtools/ribbon_analysis/gym/handoff.py",
            "devtools/ribbon_analysis/gym/scene.py",
            "devtools/ribbon_analysis/inspection/archive.py",
            "devtools/ribbon_analysis/inspection/geometry.py",
        )
    )
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }


def verify() -> dict[str, str]:
    """
    Reject changed executable policy before a fresh numerical or native gym operation.
    """
    payload = json.loads(LOCK.read_text())
    current = sources()
    if (
        not isinstance(payload, dict)
        or payload.get("version") != DEFAULT_VERSION
        or payload.get("methods") != [entry.identifier for entry in METHODS]
        or payload.get("sources") != current
    ):
        raise RuntimeError(
            "Selected solver source differs from its lock; review and freeze a new version before running"
        )
    return current


def main() -> None:
    """
    Freeze only on an explicit--write invocation; ordinary invocation verifies the lock.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        LOCK.write_text(
            json.dumps(
                {
                    "version": DEFAULT_VERSION,
                    "methods": [entry.identifier for entry in METHODS],
                    "scope": "Selected gym solver baseline; development fidelity required; not a general physical certificate",
                    "sources": sources(),
                },
                indent=2,
            )
            + "\n"
        )
    else:
        verify()


if __name__ == "__main__":
    main()
