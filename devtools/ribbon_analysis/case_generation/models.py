"""
Represent fixed case-generation inputs without a solver or Fusion dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property
from types import MappingProxyType
from typing import Literal, Mapping

from ..contracts import Targets

Kind = Literal["u", "s", "lateral", "twist"]
Stratum = Literal["normal", "stress", "random"]


@dataclass(frozen=True)
class Event:
    """
    Describe scenario intent;endpoint-only solvers do not enforce interior events.
    """

    kind: Kind
    degrees: float

    def __post_init__(self) -> None:
        """
        Reject malformed labels and angles before compiling endpoint frames.
        """
        if isinstance(self.degrees, bool) or not isinstance(self.degrees, (int, float)):
            raise ValueError("Event angles must be numeric.")
        if self.kind not in ("u", "s", "lateral", "twist") or not math.isfinite(self.degrees):
            raise ValueError("Events need a known kind and finite angle.")
        if not 0 < abs(self.degrees) <= 180 or (self.kind == "u" and abs(self.degrees) != 180):
            raise ValueError("Event angles must be nonzero and at most180degrees;U uses180.")


@dataclass(frozen=True)
class RandomBounds:
    """
    Bound random inputs relative to nominal width,not the solver's accepted outputs.
    """

    minimum_lines: int = 1
    maximum_lines: int = 64
    minimum_diameter_mm: float = 0.5
    maximum_diameter_mm: float = 1.5
    minimum_chord_widths: float = 0.25
    maximum_chord_widths: float = 12.0

    def __post_init__(self) -> None:
        """
        Validate finite positive ranges and the diagnostic system's conductor bound.
        """
        if any(
            isinstance(v, bool) or not isinstance(v, int)
            for v in (self.minimum_lines, self.maximum_lines)
        ):
            raise ValueError("Conductor bounds must be integers.")
        if not 1 <= self.minimum_lines <= self.maximum_lines <= 128:
            raise ValueError("Diagnostic conductor bounds are1..128.")
        for low, high in (
            (self.minimum_diameter_mm, self.maximum_diameter_mm),
            (self.minimum_chord_widths, self.maximum_chord_widths),
        ):
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (low, high)):
                raise ValueError("Random scale bounds must be numeric.")
            if not math.isfinite(low) or not math.isfinite(high) or not 0 < low <= high:
                raise ValueError("Random scale ranges must be positive,finite and ordered.")


@dataclass(frozen=True)
class Case:
    """
    Preserve a fixed boundary challenge,its stratum and scenario/source lineage.

    Events describe intent only. No witness geometry or fitted initialization is
    provided. Feasibility is unknown until evaluated;normal controls express a
    regression expectation,not an independent physical certificate.
    """

    identifier: str
    stratum: Stratum
    targets: Targets
    events: tuple[Event, ...]
    reference: str
    note: str

    def __post_init__(self) -> None:
        """
        Reject invalid fixed poses or empty reporting/provenance identities.
        """
        if self.stratum not in ("normal", "stress", "random"):
            raise ValueError("Unknown case stratum.")
        if (
            not isinstance(self.targets, Targets)
            or not isinstance(self.events, tuple)
            or any(not isinstance(e, Event) for e in self.events)
        ):
            raise ValueError("Cases require frozen Targets and an event tuple.")
        if any(
            not isinstance(v, str) or not v.strip()
            for v in (self.identifier, self.reference, self.note)
        ):
            raise ValueError("Cases need identity,reference and interpretation.")
        Targets.capture(self.targets)
        if self.targets.start == self.targets.end:
            raise ValueError("Endpoint challenges need a nonzero chord.")


@dataclass(frozen=True)
class Manifest:
    """
    Freeze an ordered25/25/50matrix with its replay seed and random-input domain.
    """

    version: int
    seed: int
    bounds: RandomBounds
    cases: tuple[Case, ...]
    generator_digest: str

    def __post_init__(self) -> None:
        """
        Enforce full inventory coverage and exact quarter allocation before solving.
        """
        if self.version != 1 or isinstance(self.version, bool) or not isinstance(self.version, int):
            raise ValueError("Unsupported case-generator version.")
        if (
            not isinstance(self.bounds, RandomBounds)
            or not isinstance(self.cases, tuple)
            or any(not isinstance(c, Case) for c in self.cases)
        ):
            raise ValueError("Manifest needs frozen bounds and a case tuple.")
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or not 0 <= self.seed < 2**64
        ):
            raise ValueError("Seed must be an unsigned64-bit integer.")
        size = len(self.cases)
        if not 48 <= size <= 4096 or size % 4:
            raise ValueError(
                "Choose48..4096cases in multiples of4;the normal inventory needs12slots."
            )
        quarter = size // 4
        strata = ("normal",) * quarter + ("stress",) * quarter + ("random",) * (2 * quarter)
        if tuple(case.stratum for case in self.cases) != strata:
            raise ValueError("Cases must preserve ordered25/25/50strata.")
        if len({case.identifier for case in self.cases}) != size:
            raise ValueError("Case identities must be unique.")
        if (
            not isinstance(self.generator_digest, str)
            or len(self.generator_digest) != 64
            or any(c not in "0123456789abcdef" for c in self.generator_digest)
        ):
            raise ValueError("Manifest needs a generator-source SHA256digest.")
        from .recipes import BASICS, COMBINATIONS

        required = tuple((event,) for event in BASICS) + COMBINATIONS
        if tuple(case.events for case in self.cases[:12]) != required:
            raise ValueError("Every batch needs all eight solos and four common combinations.")

    @cached_property
    def content_digest(self) -> str:
        """
        Hash immutable inputs once so per-candidate handoff stays constant work.
        """
        from .codec import compute_digest

        return compute_digest(self)

    @cached_property
    def by_identifier(self) -> Mapping[str, Case]:
        """
        Build a read-only index once rather than scan the batch for every handoff.
        """
        return MappingProxyType({case.identifier: case for case in self.cases})
