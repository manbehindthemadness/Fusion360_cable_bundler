"""
Replay the frozen joint radius/travel allocations through the shared Fusion host.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from experiments.experiment_ribbon_fold_relaxation.native_runner import ReplaySpec, replay


def main() -> None:
    """
    Build each changed267configuration once, retaining all earlier geometry.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = ReplaySpec(
        numerical_path="artifacts/verification/ribbon_radius267/result.json",
        route_suffix="allocated",
        changed_status="allocated",
        component_prefix="268 - Joint radius allocation - ",
        body_name="Gentler bends with jointly allocated straight travel",
        display_x_cm=210,
        review_title="Joint bend-radius and straight allocation",
        pass_label="Linear allocation and contact",
        method_note="Angles/creases fixed; radii grow; first-pass linear optimum subject to contact",
        question="Do larger-radius allocations retain native material fidelity without increasing total material length?",
        source_directory=Path(__file__).parent,
    )
    replay(spec, args.output)


if __name__ == "__main__":
    main()
