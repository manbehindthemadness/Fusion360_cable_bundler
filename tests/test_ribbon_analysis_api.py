"""
Verify reusable analysis needs neither experiment state nor Fusion imports.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis import provenance
from devtools.ribbon_analysis.api import Candidate, analyze
from devtools.ribbon_analysis.contracts import Targets


@dataclass(frozen=True)
class StraightField:
    """
    Supply a small independent regular-map control for the public protocol.
    """

    lines: int = 3
    diameter_mm: float = 1.0
    half_width_mm: float = 1.6
    curvature: float = 0.0

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Return zero intrinsic bending and ruling gradient.
        """
        if not 0 <= u <= 1:
            raise ValueError("Normalized material fraction required.")
        return self.curvature, 0.0, 0.0


@dataclass
class StraightPath:
    """
    Make solver mutation observable without any dependency on director experiments.
    """

    field: StraightField
    shift: float = 0.0

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return a straight fixed-offset lane and its actual normalized derivative.
        """
        return Vector3(12 * u + self.shift, offset_mm, 0), Vector3(12, 0, 0)


def _candidate() -> Candidate:
    """
    Create explicit path/target inputs without a live ledger or numbered fixture.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    targets = Targets("independent", Vector3(0, 0, 0), Vector3(12, 0, 0), x, x, y, y, 3, 1)
    return Candidate(
        "standalone-control", StraightPath(StraightField()), targets, "independent-fixture-v1"
    )


def test_evidence_is_stable_after_solver_mutation() -> None:
    """
    Keep measured positions,curve guides,targets and fingerprint frozen together.
    """
    candidate = _candidate()
    evidence = analyze(candidate, intervals=32)
    original = evidence.inspect(kind="material J", trace_number=1)
    assert isinstance(candidate.path, StraightPath)
    candidate.path.shift = 100
    assert evidence.inspect(kind="material J", trace_number=1) == original
    assert evidence.guides[0].controls[0] == Vector3(0, 1.6, 0)
    assert evidence.targets.end == Vector3(12, 0, 0)
    assert original["red_kinds"] == []
    extrema = original["series_extrema"]
    assert isinstance(extrema, list)
    assert extrema[0]["minimum"]["value"] == 1
    assert len(evidence.fingerprint) == 64


def test_distinct_provenance_and_geometry_produce_distinct_snapshots() -> None:
    """
    Do not conflate updated solver output with an earlier shared view.
    """
    candidate = _candidate()
    first = analyze(candidate, intervals=16)
    second = analyze(
        Candidate(candidate.identifier, candidate.path, candidate.targets, "revision2"),
        intervals=16,
    )
    assert first.fingerprint != second.fingerprint
    assert isinstance(candidate.path, StraightPath)
    candidate.path.shift = 1
    third = analyze(candidate, intervals=16)
    assert third.fingerprint != first.fingerprint


def test_mismatched_fixed_dimensions_reject_before_measurement() -> None:
    """
    Refuse candidate/target mismatches instead of rendering misleading correspondence.
    """
    candidate = _candidate()
    wrong = Candidate(
        candidate.identifier,
        StraightPath(StraightField(lines=4)),
        candidate.targets,
        candidate.source,
    )
    with pytest.raises(ValueError, match="dimensions"):
        analyze(wrong)


def test_nonfinite_geometry_cannot_become_clean_evidence() -> None:
    """
    Reject invalid coordinates even when the intrinsic scalar metrics look safe.
    """
    candidate = _candidate()
    assert isinstance(candidate.path, StraightPath)
    candidate.path.shift = float("nan")
    with pytest.raises(ValueError, match="finite"):
        analyze(candidate, intervals=16)


def test_cached_module_guard_detects_source_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Refuse stale source reuse without refreshing modules or discarding evidence.
    """
    monkeypatch.setattr(provenance, "_loaded", {})
    module = tmp_path / "candidate_adapter.py"
    module.write_text("version = 1\n", encoding="utf-8")
    provenance.mark_loaded(str(module))
    provenance.verify_loaded()
    module.write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Stale ribbon analysis module"):
        provenance.verify_loaded()
