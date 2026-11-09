"""
Require fresh seed and physical-layout novelty before any validation solve.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification, defaults
from experiments.experiment_ribbon_regression import fresh
from experiments.experiment_ribbon_regression.fresh import FreshRegistry, layout_fingerprint


@pytest.fixture
def specification() -> Specification:
    """
    Author three synthetic input-only layouts without solving historical fixtures.
    """
    scene = Scene(Config(17, 3, 0.75, 300, 300), Goal(0, 0), Goal(25, 0))
    payload = defaults(scene)
    payload["maximum_cases"] = 3
    return Specification.parse(payload)


def test_seed_reuse_is_rejected_and_whole_schedules_are_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, specification: Specification
) -> None:
    """
    Keep every planned layout unique across runs, including a stopped run's unattempted tail.
    """
    seeds = iter((41, 41, 42))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_regression.fresh.randbits", lambda bits: next(seeds)
    )
    registry = FreshRegistry(tmp_path / "novelty.sqlite3")
    first = registry.prepare(specification, "first", {})
    second = registry.prepare(specification, "second", {})
    assert first.specification.seed == 41 and second.specification.seed == 42
    assert second.seed_proposals == 2
    assert len(set(first.fingerprints + second.fingerprints)) == 6
    assert first.fingerprints == tuple(
        layout_fingerprint(first.specification.scene(i).targets) for i in range(3)
    )
    assert specification.seed == 17
    with sqlite3.connect(registry.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM layouts").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
    with pytest.raises(ValueError, match="identifier cannot be reused"):
        registry.prepare(specification, "first", {})


def test_duplicate_geometry_rejects_the_seed_before_any_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, specification: Specification
) -> None:
    """
    A new seed cannot turn duplicate physical inputs into novel layouts or create a partial reservation.
    """
    monkeypatch.setattr(fresh, "layout_fingerprint", lambda targets: "a" * 64)
    registry = FreshRegistry(tmp_path / "novelty.sqlite3")
    with pytest.raises(RuntimeError, match="sixteen seed proposals"):
        registry.prepare(specification, "duplicates", {})
    with sqlite3.connect(registry.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM layouts").fetchone()[0] == 0


def test_known_layouts_and_seed_hashes_survive_a_registry_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, specification: Specification
) -> None:
    """
    Historical rollup retains only novelty identifiers and does not permit relabeling a known layout.
    """
    path = tmp_path / "novelty.sqlite3"
    registry = FreshRegistry(path)
    rejected = replace(specification, seed=43)
    registry.remember([layout_fingerprint(rejected.scene(0).targets)], seed=42)
    seeds = iter((42, 43, 44))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_regression.fresh.randbits", lambda bits: next(seeds)
    )
    actual = FreshRegistry(path).prepare(specification, "next", {})
    assert actual.seed_proposals == 3 and actual.specification.seed == 44


def test_fingerprint_uses_geometry_instead_of_labels_and_does_not_round_inputs(
    specification: Specification,
) -> None:
    """
    Ignore names and last-bit aliases in the novelty index while preserving actual authored coordinates.
    """
    target = specification.scene(0).targets
    point = target.start
    alias = replace(target, name="Another label", start=Vector3(point.x + 1e-12, point.y, point.z))
    moved = replace(target, start=Vector3(point.x + 0.001, point.y, point.z))
    assert layout_fingerprint(target) == layout_fingerprint(alias)
    assert layout_fingerprint(target) != layout_fingerprint(moved)
    assert alias.start.x == point.x + 1e-12 and target.start is point


@pytest.mark.parametrize("mode,limit", (("systematic", 3), ("random", 0), ("random", 10001)))
def test_fresh_campaign_requires_a_bounded_random_schedule(
    tmp_path: Path, specification: Specification, mode: str, limit: int
) -> None:
    """
    Reject unbounded preparation and replay modes before reserving seeds or geometry.
    """
    registry = FreshRegistry(tmp_path / "novelty.sqlite3")
    with pytest.raises(ValueError, match="finite"):
        registry.prepare(replace(specification, mode=mode, maximum_cases=limit), "invalid", {})


def test_statistics_are_immutable_and_contain_no_reference_case_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, specification: Specification
) -> None:
    """
    Finalize aggregate counts once while keeping reserved seeds hashed and case coordinates absent.
    """
    monkeypatch.setattr("experiments.experiment_ribbon_regression.fresh.randbits", lambda bits: 123)
    registry = FreshRegistry(tmp_path / "novelty.sqlite3")
    metadata = {"population": "fresh_unique_first_attempts"}
    registry.prepare(specification, "run", metadata)
    registry.record("run", metadata, {"attempted": 2, "passed": 1})
    assert registry.statistics() == [
        {"identifier": "run", "metadata": metadata, "summary": {"attempted": 2, "passed": 1}}
    ]
    with pytest.raises(ValueError, match="overwritten"):
        registry.record("run", metadata, {"attempted": 2, "passed": 2})
    with sqlite3.connect(registry.path) as connection:
        seed_hash = connection.execute("SELECT seed_hash FROM runs").fetchone()[0]
        assert len(seed_hash) == 64 and seed_hash != "123"
        assert "targets" not in json.dumps(connection.execute("SELECT * FROM runs").fetchall())


def test_input_authoring_deadline_does_not_leave_a_partial_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, specification: Specification
) -> None:
    """
    Exhausted input preparation stops before solving and rolls back its novelty transaction.
    """
    clock = iter((0.0, 31.0))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_regression.fresh.monotonic", lambda: next(clock)
    )
    registry = FreshRegistry(tmp_path / "novelty.sqlite3")
    with pytest.raises(TimeoutError, match="thirty-second"):
        registry.prepare(specification, "timeout", {})
    assert registry.statistics() == []
    with sqlite3.connect(registry.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
