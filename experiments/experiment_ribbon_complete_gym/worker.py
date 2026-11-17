"""
Run one complete gym diagnostic in the project-local SDK subprocess.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .job import run

if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
