"""
Guard first-party source files against silently becoming new monoliths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LIMITS = {
    ".py": 800,
    ".js": 700,
    ".cjs": 700,
    ".css": 400,
    ".html": 400,
}
EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "F360CableGenerator",
    "artifacts",
    "experiments",
    "reference",
    "standards",
}
FILE_LIMIT_OVERRIDES = {
    Path("cable_bundler/domain/codec.py"): 900,
}


def _source_files(extension: str) -> tuple[Path, ...]:
    """
    Return maintained project sources for one guarded extension.
    """
    return tuple(
        path
        for path in ROOT.rglob(f"*{extension}")
        if not EXCLUDED_DIRECTORIES.intersection(path.relative_to(ROOT).parts)
    )


@pytest.mark.parametrize(("extension", "default_limit"), SOURCE_LIMITS.items())
def test_source_files_stay_within_reviewable_size(
    extension: str,
    default_limit: int,
) -> None:
    """
    Require an explicit architectural decision before a source file grows unchecked.
    """
    oversized: list[str] = []
    for path in _source_files(extension):
        relative_path = path.relative_to(ROOT)
        limit = FILE_LIMIT_OVERRIDES.get(relative_path, default_limit)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > limit:
            oversized.append(f"{relative_path}: {line_count} lines (limit {limit})")
    assert not oversized, "Oversized source files:\n" + "\n".join(sorted(oversized))
