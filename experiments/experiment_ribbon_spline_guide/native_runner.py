"""
Replay changed guide-directed material plans once through the unchanged native builder.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from experiments.experiment_ribbon_fold_relaxation.native_runner import ReplaySpec, replay


def main() -> None:
    """
    Retain earlier results and separately measure native fidelity for changed cases.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = ReplaySpec(
        "artifacts/verification/ribbon_guide270/result.json",
        "guided",
        "guided",
        "271 - Spline guided construction - ",
        "Guide-directed material ribbon",
        290,
        "Endpoint spline guided initial construction",
        "Guided solve and contact",
        "Exact fold branches ranked by ordered guide agreement; unchanged physical rules",
        "Do guide-directed plans reproduce their material geometry in native solids?",
        Path(__file__).parent,
    )
    replay(spec, args.output)


if __name__ == "__main__":
    main()
