"""
Build only changed layout-relative aesthetic plans with existing material-fidelity checks.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from experiments.experiment_ribbon_fold_relaxation.native_runner import ReplaySpec, replay


def main() -> None:
    """
    Replay changed307plans once, preserving302/305and earlier geometry for comparison.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--numerical", default="artifacts/verification/ribbon_layout307/result.json"
    )
    parser.add_argument("--component-prefix", default="308 - Layout-relative fold easing - ")
    parser.add_argument("--display-x-cm", type=float, default=530)
    args = parser.parse_args()
    replay(
        ReplaySpec(
            numerical_path=args.numerical,
            route_suffix="eased",
            changed_status="eased",
            component_prefix=args.component_prefix,
            body_name="Layout-relative eased material route",
            display_x_cm=args.display_x_cm,
            review_title="Layout-relative easing into straight runway",
            pass_label="Layout easing and compatible turn merging",
            method_note="Angles/banks/radii relax together; straightaways are runway; original5%length ceiling",
            question="Do the explicitly recorded layout-scaled plans retain native material fidelity? No further solver passes in Fusion. For310continuation:308calibrationfailed the unchanged1e-6mmsurface gate; keep that failure, exclude its new body, retain302calibration, and make only the remaining Gym1/Gym3first attempts.310has an explicit frozen exclusion ledger; no radius/rule/tolerance changes or calibration retry.",
            source_directory=Path(__file__).parent,
            fidelity_audit="experiments/experiment_ribbon_joint_route/fidelity.py",
        ),
        args.output,
    )


if __name__ == "__main__":
    main()
