"""
Write or inspect a replayable test-case manifest without touching a Fusion scene.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from . import fingerprint, generate, read, write


def main() -> None:
    """
    Generate one non-overwritten manifest or verify a previously frozen batch.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("generate")
    create.add_argument("--count", type=int, default=64)
    create.add_argument("--seed", type=int)
    create.add_argument(
        "--mode",
        choices=("random", "installation"),
        default="random",
        help="Choose arbitrary endpoint poses (default) or coupled board/panel installations.",
    )
    create.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            manifest = generate(size=args.count, seed=args.seed, mode=args.mode)
            write(manifest, args.output)
        else:
            manifest = read(args.manifest)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            dict(
                seed=manifest.seed,
                mode=manifest.mode,
                count=len(manifest.cases),
                strata=dict(Counter(case.stratum for case in manifest.cases)),
                installation_families=dict(
                    Counter(
                        case.installation.family
                        for case in manifest.cases
                        if case.installation is not None
                    )
                ),
                fingerprint=fingerprint(manifest),
                generator_digest=manifest.generator_digest,
                solver_calls=0,
                native_attempts=0,
            )
        )
    )


if __name__ == "__main__":
    main()
