"""
Generate replayable gym cases independently of every solver outcome.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from devtools.ribbon_analysis.gym.placement import allowed_pairs
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene

from .ranges import FIELDS, NumericRange
from .screenshots import ScreenshotSettings


@dataclass(frozen=True)
class Specification:
    """
    Freeze input ranges, scheduling order and explicit stop controls for a user-run tester.
    """

    ranges: dict[str, NumericRange]
    mode: str
    seed: int
    stop_on_warnings: bool
    maximum_cases: int
    screenshots: ScreenshotSettings = ScreenshotSettings()
    avoid_adjacent_zones: bool | None = None
    keep_awake: bool = False

    @classmethod
    def parse(cls, payload: Any) -> Specification:
        """
        Validate the complete range plan and existence of distinct endpoint zones before launch.
        """
        if not isinstance(payload, dict) or set(payload) - {
            "screenshots",
            "avoid_adjacent_zones",
            "keep_awake",
        } != {
            "ranges",
            "mode",
            "seed",
            "stop_on_warnings",
            "maximum_cases",
        }:
            raise ValueError("Supply ranges, mode, seed, stop_on_warnings and maximum_cases.")
        ranges = payload["ranges"]
        if not isinstance(ranges, dict) or set(ranges) != {field.name for field in FIELDS}:
            raise ValueError("Supply all ten gym input ranges.")
        parsed = {field.name: NumericRange.parse(ranges[field.name]) for field in FIELDS}
        for field in FIELDS:
            field.validate(parsed[field.name])
        if payload["mode"] not in ("systematic", "random"):
            raise ValueError("Choose systematic or seeded random testing.")
        if type(payload["seed"]) is not int or not 0 <= payload["seed"] <= 2**32 - 1:
            raise ValueError("Test seed must be an integer in 0..4294967295.")
        if type(payload["stop_on_warnings"]) is not bool:
            raise ValueError("Choose explicitly whether native accuracy warnings stop testing.")
        if "avoid_adjacent_zones" in payload and type(payload["avoid_adjacent_zones"]) is not bool:
            raise ValueError("Choose explicitly whether to avoid adjacent cubicles.")
        if "keep_awake" in payload and type(payload["keep_awake"]) is not bool:
            raise ValueError("Choose explicitly whether to keep the Mac awake during testing.")
        if (
            type(payload["maximum_cases"]) is not int
            or not 0 <= payload["maximum_cases"] <= 1_000_000
        ):
            raise ValueError(
                "Case limit must be 0 (until a problem) or an integer up to 1,000,000."
            )
        result = cls(
            parsed,
            payload["mode"],
            payload["seed"],
            payload["stop_on_warnings"],
            payload["maximum_cases"],
            ScreenshotSettings.parse(payload.get("screenshots")),
            payload.get("avoid_adjacent_zones"),
            payload.get("keep_awake", False),
        )
        if not result.zone_pairs:
            if result.avoid_adjacent_zones:
                raise ValueError(
                    "No non-adjacent cubicle pairs in these ranges. "
                    "Broaden zone ranges or disable Avoid adjacent cubicles."
                )
            raise ValueError("A and B need at least one pair of different zones.")
        Config(
            0,
            int(parsed["lines"].maximum),
            float(parsed["diameter_mm"].maximum),
            float(parsed["void_percent"].maximum),
            float(parsed["zone_percent"].maximum),
        )
        return result

    @cached_property
    def zone_pairs(self) -> tuple[tuple[int, int], ...]:
        """
        Apply the frozen placement policy before any solver outcome or case attempt.
        """
        a, b = self.ranges["a_zone"], self.ranges["b_zone"]
        return tuple(
            (first + 1, second + 1)
            for first, second in allowed_pairs(
                tuple(int(a.value(i)) - 1 for i in range(a.count)),
                tuple(int(b.value(j)) - 1 for j in range(b.count)),
                avoid_adjacent_zones=bool(self.avoid_adjacent_zones),
            )
        )

    @cached_property
    def combinations(self) -> int:
        """
        Count one complete systematic pass without constructing the Cartesian product.
        """
        return math.prod(
            values.count for name, values in self.ranges.items() if name not in ("a_zone", "b_zone")
        ) * len(self.zone_pairs)

    def scene(self, index: int) -> Scene:
        """
        Select each input solely from the frozen plan and zero-based case index.

        Systematic mode advances conductor count fastest and repeats its grid with
        continuing gym seeds. Random mode independently samples reachable stepped
        values using a per-case seeded generator. Neither mode retries failed cases.
        """
        if type(index) is not int or index < 0:
            raise ValueError("Case index must be a nonnegative integer.")
        rng = random.Random(f"ribbon-range-tester-v1:{self.seed}:{index}")
        remaining = index % self.combinations
        values: dict[str, int | float] = {}
        for field in FIELDS:
            if field.name in ("a_zone", "b_zone"):
                continue
            span = self.ranges[field.name]
            digit = rng.randrange(span.count) if self.mode == "random" else remaining % span.count
            remaining //= span.count
            values[field.name] = span.value(digit)
        pairs = self.zone_pairs
        zone_index = rng.randrange(len(pairs)) if self.mode == "random" else remaining % len(pairs)
        a_zone, b_zone = pairs[zone_index]
        gym_seed = rng.getrandbits(32) if self.mode == "random" else (self.seed + index) % 2**32
        config = Config(
            gym_seed,
            int(values["lines"]),
            float(values["diameter_mm"]),
            float(values["void_percent"]),
            float(values["zone_percent"]),
        )
        return Scene(
            config,
            Goal.from_degrees(a_zone - 1, int(values["a_face"]) - 1, int(values["a_roll"])),
            Goal.from_degrees(b_zone - 1, int(values["b_face"]) - 1, int(values["b_roll"])),
        )

    def payload(self) -> dict[str, Any]:
        """
        Serialize the replayable settings without counts or generated geometry.
        """
        result = {
            "ranges": {name: values.payload() for name, values in self.ranges.items()},
            "mode": self.mode,
            "seed": self.seed,
            "stop_on_warnings": self.stop_on_warnings,
            "maximum_cases": self.maximum_cases,
            "screenshots": self.screenshots.payload(),
            "keep_awake": self.keep_awake,
        }
        if self.avoid_adjacent_zones is not None:
            result["avoid_adjacent_zones"] = self.avoid_adjacent_zones
        return result


def defaults(scene: Scene) -> dict[str, Any]:
    """
    Start from current dimensions/selections, varying only conductor count until edited.
    """
    values = {
        "lines": scene.config.lines,
        "diameter_mm": scene.config.diameter_mm,
        "void_percent": scene.config.void_percent,
        "zone_percent": scene.config.zone_percent,
        "a_zone": scene.a.zone + 1,
        "a_face": scene.a.face + 1,
        "a_roll": scene.a.degrees,
        "b_zone": scene.b.zone + 1,
        "b_face": scene.b.face + 1,
        "b_roll": scene.b.degrees,
    }
    ranges = {
        name: {"min": str(value), "max": str(value), "step": "1"} for name, value in values.items()
    }
    ranges["lines"] = {"min": "1", "max": str(max(6, scene.config.lines)), "step": "1"}
    return {
        "ranges": ranges,
        "mode": "systematic",
        "seed": scene.config.seed,
        "stop_on_warnings": True,
        "maximum_cases": 0,
        "keep_awake": sys.platform == "darwin",
        "screenshots": ScreenshotSettings().payload(),
        "avoid_adjacent_zones": True,
    }
