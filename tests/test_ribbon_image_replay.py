"""
Preserve complete frozen replay inputs in a portable PNG without re-encoding pixels.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from experiments.experiment_ribbon_locked_solver.tester.image_replay import (
    KEY,
    SCHEMA,
    capture_record,
    embed,
    read,
)
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification
from tests.test_ribbon_range_screenshots import PNG
from tests.test_ribbon_range_sequence import specification


def test_moved_image_replays_exact_inputs_after_original_logs_are_removed(tmp_path: Path) -> None:
    """
    Retain frozen poses, source hashes and execution policy independently of filenames or logs.
    """
    scene = Specification.parse(specification()).scene(3)
    input_path, plan_path, job = tmp_path / "case.json", tmp_path / "test.json", tmp_path / "job"
    job.mkdir()
    case = json.loads(json.dumps({"index": 3, "gym": scene.payload()}))
    plan = {
        "selection": {"id": "guide-material-v2", "settings": {"smoothing_percent": 1}},
        "sources": {"solver.py": "historical hash"},
        "label": "Original → replay",
    }
    execution = {
        "targets": case["gym"]["targets"],
        "contact_measurement_policy": "require_separation",
        "native_point_tolerance_mm": 1e-5,
        "limits": {"native_seconds": 120},
    }
    input_path.write_text(json.dumps(case))
    plan_path.write_text(json.dumps(plan))
    (job / "plan.json").write_text(json.dumps(execution))
    image = tmp_path / "case.png"
    image.write_bytes(PNG)
    record = capture_record(input_path, plan_path, str(job))
    embed(image, record)
    data = image.read_bytes()
    chunk_end = 33 + struct.unpack_from(">I", data, 33)[0] + 12
    assert data[:33] + data[chunk_end:] == PNG
    moved = image.rename(tmp_path / "renamed-problem.png")
    input_path.unlink()
    plan_path.unlink()
    (job / "plan.json").unlink()
    restored = read(moved)
    assert restored["schema"] == SCHEMA and restored["input"] == case
    assert restored["test_plan"] == plan and restored["job_plan"] == execution
    with pytest.raises(ValueError, match="already contains"):
        embed(moved, record)
    assert moved.read_bytes() == data


@pytest.mark.parametrize("fault", ("missing", "corrupt", "truncated", "schema"))
def test_incomplete_or_corrupt_replay_evidence_is_not_silently_used(
    tmp_path: Path, fault: str
) -> None:
    """
    Distinguish an original image without metadata from damaged or unsupported evidence.
    """
    path = tmp_path / "image.png"
    path.write_bytes(PNG)
    if fault != "missing":
        embed(path, {"schema": SCHEMA})
    if fault == "corrupt":
        data = bytearray(path.read_bytes())
        data[data.index(KEY) + len(KEY) + 4] ^= 1
        path.write_bytes(data)
    elif fault == "truncated":
        path.write_bytes(path.read_bytes()[:-8])
    elif fault == "schema":
        other = tmp_path / "future.png"
        other.write_bytes(PNG)
        with pytest.raises(ValueError, match="schema"):
            embed(other, {"schema": "future-v2"})
        return
    with pytest.raises(ValueError):
        read(path)
