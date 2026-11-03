"""
Validate optional viewport exports and retain a unique PNG for each prepared test case.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable

from cable_bundler.routing.geometry import Vector3

DEFAULT_DIRECTORY = "~/Pictures/testxyz"


def frame(extent_mm: float, points: Iterable[Vector3]) -> tuple[Vector3, float]:
    """
    Bound the current gym cube and supplied local ribbon points, excluding unrelated host content.

    Return a local millimeter center and maximum axis span for viewport framing only.
    This display bound is not a geometric clearance or route acceptance measurement.
    """
    lower = [-extent_mm / 2] * 3
    upper = [extent_mm / 2] * 3
    for point in points:
        for axis, value in enumerate((point.x, point.y, point.z)):
            lower[axis] = min(lower[axis], value)
            upper[axis] = max(upper[axis], value)
    center = Vector3(*((a + b) / 2 for a, b in zip(lower, upper)))
    return center, max(b - a for a, b in zip(lower, upper))


@dataclass(frozen=True)
class ScreenshotSettings:
    """
    Keep screenshot export opt-in and independent of numerical input generation.
    """

    enabled: bool = False
    directory: str = DEFAULT_DIRECTORY

    @classmethod
    def parse(cls, payload: Any) -> ScreenshotSettings:
        """
        Accept omitted legacy settings or an explicit toggle and absolute/home-relative folder.
        """
        if payload is None:
            return cls()
        if not isinstance(payload, dict) or set(payload) != {"enabled", "directory"}:
            raise ValueError("Screenshot settings need enabled and directory.")
        directory = payload["directory"]
        if type(payload["enabled"]) is not bool or not isinstance(directory, str):
            raise ValueError("Choose a screenshot toggle and folder path.")
        if not directory.strip() or len(directory) > 4096 or any(ord(c) < 32 for c in directory):
            raise ValueError(
                "Screenshot folder must be a nonempty path without control characters."
            )
        result = cls(payload["enabled"], directory)
        if not result.folder.is_absolute():
            raise ValueError("Screenshot folder must be absolute or start with ~/.")
        return result

    @property
    def folder(self) -> Path:
        """
        Expand the home directory without creating or inspecting any output files.
        """
        return Path(self.directory).expanduser()

    def payload(self) -> dict[str, Any]:
        """
        Retain the user's toggle and folder spelling in the frozen test plan.
        """
        return asdict(self)


class Screenshots:
    """
    Reserve unique per-run filenames and verify each requested native PNG export once.
    """

    def __init__(
        self, settings: ScreenshotSettings, run: str, capture: Callable[[Path], None]
    ) -> None:
        """
        Create the requested output folder before any geometry work starts.
        """
        self.folder, self.run, self.capture = settings.folder, run, capture
        self.folder.mkdir(parents=True, exist_ok=True)

    def save(self, case: str) -> dict[str, Any]:
        """
        Export once without overwriting existing images; propagate failures to stop scheduling.

        A failed/partial export is retained for diagnosis and is never silently retried.
        The caller supplies only journal-generated run/case identifiers.
        """
        path = self.folder / f"{self.run}-{case}.png"
        started = perf_counter()
        with path.open("xb"):
            pass
        self.capture(path)
        with path.open("rb") as stream:
            header = stream.read(24)
        if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise RuntimeError(f"Viewport export did not produce a PNG: {path}")
        return {
            "path": str(path),
            "seconds": perf_counter() - started,
            "bytes": path.stat().st_size,
        }
