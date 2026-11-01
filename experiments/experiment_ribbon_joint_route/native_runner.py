"""
Build changed joint first-pass plans once with the retained material native constructor.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from experiments.experiment_ribbon_fold_relaxation.native_runner import ReplaySpec, replay


def main() -> None:
    """
    Keep the last successful bodies while separately auditing each changed first pass.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = ReplaySpec(
        "artifacts/verification/ribbon_joint285/result.json",
        "joint",
        "joint",
        "286 - Joint first-pass route - ",
        "Joint position and orientation material route",
        370,
        "Joint first-pass position and orientation",
        "First-pass allocation and contact",
        "Distributed orientation; joint travel/radius; no reset modules or attraction",
        "Do the new joint first-pass plans retain native material fidelity?",
        Path(__file__).parent,
    )
    replay(spec, args.output)


if __name__ == "__main__":
    main()
