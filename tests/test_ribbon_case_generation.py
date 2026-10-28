"""
Verify coverage,unconditioned random inputs,replay and diagnostic handoff contracts.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from devtools.ribbon_analysis import api, constraint_geometry
from devtools.ribbon_analysis.case_generation import (
    Event,
    GenerationMode,
    RandomBounds,
    candidate_for,
    fingerprint,
    generate,
    read,
    write,
)
from devtools.ribbon_analysis.case_generation.generator import known_stress
from devtools.ribbon_analysis.case_generation.recipes import BASICS, COMBINATIONS, compile_pose


def test_every_batch_preserves_inventory_and_exact_quarters() -> None:
    """
    Keep normal solos/compounds and every known stress input independent of seed.
    """
    first, second = generate(seed=17), generate(seed=18)
    assert len(first.cases) == 64
    assert [case.stratum for case in first.cases] == ["normal"] * 16 + ["stress"] * 16 + [
        "random"
    ] * 32
    assert tuple(case.events for case in first.cases[:8]) == tuple((event,) for event in BASICS)
    assert tuple(case.events for case in first.cases[8:12]) == COMBINATIONS
    assert first.cases[:32] == second.cases[:32]
    assert first.cases[32:] != second.cases[32:]
    assert first.cases[16:24] == known_stress()
    assert all(not case.events for case in first.cases[32:])


def test_random_prefix_is_stable_when_batch_size_changes() -> None:
    """
    Adding controls cannot silently shift the random challenge sequence.
    """
    small, large = generate(size=48, seed=21), generate(size=80, seed=21)
    random_small = tuple(case for case in small.cases if case.stratum == "random")
    random_large = tuple(case for case in large.cases if case.stratum == "random")
    assert random_small == random_large[: len(random_small)]
    assert small.cases[:12] == large.cases[:12]


def test_random_frames_dimensions_and_chords_cover_full_space() -> None:
    """
    Preserve finite unit frames and declared relative ranges without solve filtering.
    """
    bounds = RandomBounds(2, 40, 0.7, 1.7, 0.4, 10)
    random_cases = tuple(
        c for c in generate(size=256, seed=91, bounds=bounds).cases if c.stratum == "random"
    )
    signatures = set()
    for case in random_cases:
        target = case.targets
        assert 2 <= target.lines <= 40
        assert 0.7 <= target.diameter_mm <= 1.7
        width = target.lines * target.diameter_mm
        assert 0.4 <= magnitude(difference(target.end, target.start)) / width <= 10
        assert magnitude(target.start_tangent) == pytest.approx(1)
        assert magnitude(target.end_width) == pytest.approx(1)
        assert dot(target.end_width, target.end_tangent) == pytest.approx(0, abs=1e-12)
        signatures.add((target.start, target.end, target.start_tangent, target.end_width))
    assert len(signatures) == len(random_cases)
    for axis in ("x", "y", "z"):
        assert min(getattr(c.targets.start_tangent, axis) for c in random_cases) < -0.8
        assert max(getattr(c.targets.end_tangent, axis) for c in random_cases) > 0.8


def test_s_and_twist_intents_produce_correct_boundary_relationships() -> None:
    """
    S returns its tangent;twist changes ordered width while leaving the chord free.
    """
    s = compile_pose("S", (Event("s", 45),))
    assert s.end_tangent.x == pytest.approx(1)
    assert s.end_tangent.z == pytest.approx(0, abs=1e-12)
    assert s.end.z > 0 and s.end.x > 0
    for angle in (45, 90, 180):
        target = compile_pose("twist", (Event("twist", angle),))
        assert target.start_tangent == target.end_tangent
        assert dot(target.start_width, target.end_width) == pytest.approx(
            math.cos(math.radians(angle))
        )
    first = compile_pose("first", (Event("lateral", 90), Event("twist", 90)))
    second = compile_pose("second", (Event("twist", 90), Event("lateral", 90)))
    assert first.end_tangent != second.end_tangent


def test_largest_supported_manifest_does_not_exceed_diagnostic_dimensions() -> None:
    """
    Large quarters retain valid dimensions and mandatory inventories.
    """
    manifest = generate(size=4096, seed=1)
    assert len(manifest.cases) == 4096
    assert all(1 <= case.targets.lines <= 128 for case in manifest.cases)
    assert len({case.identifier for case in manifest.cases}) == 4096


def test_manifest_replay_is_exact_and_never_overwrites(tmp_path: Path) -> None:
    """
    Persist full floats/lineage,verify the digest and preserve prior inputs on reuse.
    """
    manifest = generate(size=48, seed=123)
    path = tmp_path / "manifest.json"
    write(manifest, path)
    original = path.read_bytes()
    assert read(path) == manifest == generate(size=48, seed=123)
    assert fingerprint(read(path)) == fingerprint(manifest)
    with pytest.raises(FileExistsError):
        write(generate(seed=55), path)
    assert path.read_bytes() == original
    changed = json.loads(original)
    changed["cases"][-1]["targets"]["end"]["x"] += 0.1
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="digest"):
        read(path)


def test_legacy_payload_and_seeded_inputs_keep_their_pre_installation_digest(
    tmp_path: Path,
) -> None:
    """
    Lock the original v1 encoding and all48input poses against the pre-change digest.

    The source digest is normalized because new source necessarily has a different
    provenance. The expected content hash was captured before adding mode/context.
    """
    manifest = replace(generate(size=48, seed=123), generator_digest="0" * 64)
    expected = "a76ee179c3711c7b29eba7234463ff89ba468595227bf048575ca821a0fb205a"
    assert manifest.version == 1 and manifest.mode == "random"
    assert fingerprint(manifest) == expected
    path = tmp_path / "legacy.json"
    write(manifest, path)
    document = json.loads(path.read_text())
    assert "mode" not in document
    assert all("installation" not in case for case in document["cases"])
    assert read(path) == manifest
    assert fingerprint(read(path)) == expected


@pytest.mark.parametrize(
    "mutation",
    (
        "version",
        "float_version",
        "cases",
        "vector",
        "event",
        "bounds",
        "boolean_scale",
        "stratum",
        "duplicate",
    ),
)
def test_malformed_manifests_fail_before_solver_handoff(tmp_path: Path, mutation: str) -> None:
    """
    Reject missing,null,wrong-shape and invalid inventory/identity payloads.
    """
    path = tmp_path / "bad.json"
    write(generate(size=48, seed=1), path)
    data = json.loads(path.read_text())
    if mutation == "version":
        data["version"] = 2
    elif mutation == "float_version":
        data["version"] = 1.0
    elif mutation == "cases":
        data["cases"] = None
    elif mutation == "vector":
        data["cases"][0]["targets"]["end"] = None
    elif mutation == "event":
        data["cases"][0]["events"] = [{"kind": "twist", "degrees": True}]
    elif mutation == "bounds":
        data["bounds"]["maximum_lines"] = False
    elif mutation == "boolean_scale":
        data["bounds"]["minimum_diameter_mm"] = True
    elif mutation == "stratum":
        data["cases"][0]["stratum"] = "random"
    else:
        data["cases"][1]["identifier"] = data["cases"][0]["identifier"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read(path)


@pytest.mark.parametrize("size", (0, 32, 47, 49, 4097, True))
def test_invalid_sizes_are_not_silently_rounded(size: int) -> None:
    """
    Exact quarter allocation cannot erase mandatory controls through rounding.
    """
    with pytest.raises(ValueError):
        generate(size=size, seed=1)


@dataclass(frozen=True)
class _Field:
    """
    Supply a neutral synthetic material field for an intentionally unconnected path.
    """

    lines: int
    diameter_mm: float
    half_width_mm: float

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Keep a regular zero-curvature material map.
        """
        return 0.0, 0.0, 0.0


@dataclass(frozen=True)
class _Path:
    """
    Preserve an unconnected diagnostic outcome instead of repairing it to the target.
    """

    field: _Field

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return the actual neutral lane and derivative,including its endpoint miss.
        """
        return Vector3(10 * u, offset_mm, 0), Vector3(10, 0, 0)


@pytest.mark.parametrize("mode", ("random", "installation"))
def test_failed_path_reaches_diagnostics_with_frozen_targets_and_provenance(
    mode: GenerationMode,
) -> None:
    """
    Carry a real target miss into shared measurements without success filtering.
    """
    manifest = generate(seed=12, mode=mode)
    case = manifest.cases[0] if mode == "random" else manifest.cases[-1]
    target = case.targets
    path = _Path(_Field(target.lines, target.diameter_mm, target.lines * target.diameter_mm / 2))
    candidate = candidate_for(manifest, case, path, solver_source="test-source-pin")
    assert candidate.targets == target
    assert fingerprint(manifest) in candidate.source
    assert f"mode:{mode}" in candidate.source
    evidence = api.analyze(candidate, intervals=16)
    panel = next(item for item in constraint_geometry.build(evidence) if item.key == "targets")
    assert dict(panel.measurements)["center_gap_mm"] > 10
    with pytest.raises(ValueError, match="dimensions"):
        candidate_for(
            manifest,
            case,
            replace(path, field=replace(path.field, lines=target.lines + 1)),
            solver_source="pin",
        )
