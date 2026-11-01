"""
Replay the four frozen curvature-eased material plans through the unchanged constructor.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from experiments.experiment_ribbon_fold_relaxation.native_runner import ReplaySpec, replay


def main() -> None:
    """
    Replay unchanged296routes after297transaction rollback and299missing-body stop.

    Calibration's successful297kernel/audit was rolled back by a subsequent review
    error;300read-only inspection confirms no297/299components remain. This is one
    renewed calibration build and the first three gym builds, not four first attempts.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    replay(
        ReplaySpec(
            numerical_path="artifacts/verification/ribbon_aesthetic296/result.json",
            route_suffix="eased",
            changed_status="eased",
            component_prefix="302 - Aesthetic fold easing - ",
            body_name="Curvature-eased joint material route",
            display_x_cm=450,
            review_title="Curvature easing after joint first pass",
            pass_label="Aesthetic curvature pass",
            method_note="At most5%length growth; fixed ordered caps and folds; no physical-rule relaxation",
            question="Renewal after297review metadata error rolled back its successful calibration build/audit,299reuse found no body,300read-onlyinspection confirmed absence. Same296geometry: one renewed calibration build and first Gym1..3builds; missing baselinefoldmetadata derived from fixed285plans before any kernel call. Do all four retain native material fidelity?",
            source_directory=Path(__file__).parent,
            fidelity_audit="experiments/experiment_ribbon_joint_route/fidelity.py",
            baseline_routes=tuple(
                (name, f"artifacts/verification/ribbon_joint285/{name}-joint.json")
                for name in ("calibration", "gym-1", "gym-2", "gym-3")
            ),
        ),
        args.output,
    )


if __name__ == "__main__":
    main()
