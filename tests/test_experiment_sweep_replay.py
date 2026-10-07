"""
Verify exact six-case provenance and preserve signed winding without Fusion.
"""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from experiments.experiment_ribbon_cap_transition.array_limits import scaled_case
from experiments.experiment_ribbon_cap_transition.faith_fixtures import faith_fixtures
from experiments.experiment_ribbon_cap_transition.planning import (
    ShortConnectionFixture,
    freeze_targets,
)
from experiments.experiment_ribbon_cap_transition.screen import _fits
from experiments.experiment_ribbon_cap_transition.sweep_replay import frozen_sweep_fixtures

PARENT = (
    Path(__file__).resolve().parents[1]
    / "artifacts/verification/ribbon_cap_transition/faith_native/435bedfe25f245cc86db435fc01dddf0/plan.json"
)


@pytest.fixture
def runtime_parent(tmp_path: Path) -> Path:
    """
    Author unit-test provenance with this runtime's floating-point operations.

    Retained selection scales are reused; this synthetic unit fixture is not
    the historical native plan. Exact historical replay is checked in Fusion.
    """
    if not PARENT.is_file():
        pytest.skip("Requires retained local six-case experiment provenance.")
    plan = json.loads(PARENT.read_text(encoding="utf-8"))
    originals = faith_fixtures()
    plan["parents"] = [asdict(item) for item in originals]
    inputs = []
    for item, selection in zip(originals, plan["selections"]):
        case = scaled_case(item.case, selection["scale"])
        fits = _fits(case)
        targets = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        inputs.append(
            {
                "fixture": asdict(replace(item, case=case)),
                "caps": [asdict(f) for f in fits],
                "targets": asdict(targets),
            }
        )
    plan["inputs"] = inputs
    path = tmp_path / "runtime-parent.json"
    path.write_text(json.dumps(plan, default=str), encoding="utf-8")
    return path


def test_original_packed_six_and_signed_winding(runtime_parent: Path) -> None:
    """
    Reuse original selected geometry and restore full winding rather than modulo it.
    """
    fixtures = frozen_sweep_fixtures(runtime_parent)
    assert tuple(f.twist_degrees for f in fixtures) == (0, 90, -90, 180, -180, -360)
    assert len({f.case.route.cable_id for f in fixtures}) == 6
    assert all(
        (f.case.lines, f.case.diameter_mm, f.case.end_boundary.diameter_mm) == (19, 1.5, 114)
        for f in fixtures
    )
    assert fixtures == frozen_sweep_fixtures(runtime_parent)


@pytest.mark.parametrize("damage", ("missing_selection", "changed_scale", "changed_target"))
def test_drift_rejected_before_authoring(tmp_path: Path, runtime_parent: Path, damage: str) -> None:
    """
    Never reauthor a different selection or move a connection target for a replay.
    """
    plan = json.loads(runtime_parent.read_text(encoding="utf-8"))
    if damage == "missing_selection":
        plan["selections"].pop()
    elif damage == "changed_scale":
        plan["selections"][0]["scale"] *= 1.01
    else:
        plan["inputs"][0]["targets"] = {}
    path = tmp_path / "parent.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete|provenance"):
        frozen_sweep_fixtures(path)
