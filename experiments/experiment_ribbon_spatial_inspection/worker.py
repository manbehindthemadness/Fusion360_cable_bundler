"""
Run inspection analysis or its one recorded probe only in the configured cold subprocess.
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path


def main() -> None:
    """
    Dispatch one bounded operation and retain any failure without automatic retry.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("capture", "probe"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "capture":
            from .preparation import freeze_job

            result = freeze_job(args.directory)
        else:
            from .ledger import Ledger

            result = Ledger(args.directory).run_probe()
        print(
            json.dumps(
                {key: value for key, value in result.items() if key != "after"}, allow_nan=False
            )
        )
    except (ArithmeticError, OSError, RuntimeError, ValueError, KeyError, TypeError):
        path = args.directory / (args.operation + "-worker-error.txt")
        with path.open("x") as stream:
            stream.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
