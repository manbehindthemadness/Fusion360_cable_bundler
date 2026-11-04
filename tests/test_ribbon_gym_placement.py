"""
Verify gym placement limits, opt-out and historical replay without route construction.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.placement import adjacent, allowed_pairs, generate_layout
from devtools.ribbon_analysis.gym.scene import ZONES, Config, Goal, Scene, generate
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification, defaults
from tests.fusion_ui_support import _PaletteLifecycleModule
from tests.test_ribbon_range_sequence import specification


@pytest.mark.parametrize("other", ((-1, -1, 0), (-1, 0, 0), (0, 0, -1)))
def test_face_edge_and_corner_contact_are_adjacent(other: tuple[int, int, int]) -> None:
    """
    Apply one scale-independent cell rule to each kind of contact.
    """
    first, second = ZONES.index((-1, -1, -1)), ZONES.index(other)
    assert adjacent(first, second) and adjacent(second, first)
    assert not adjacent(first, ZONES.index((1, -1, -1)))


@pytest.mark.parametrize("zone", (-1, 26, True, 1.5, None))
def test_invalid_cell_indices_reject(zone: Any) -> None:
    """
    Reject malformed external values before indexing the cell lattice.
    """
    with pytest.raises(ValueError, match="indices"):
        adjacent(zone, 0)
    with pytest.raises(ValueError, match="indices"):
        allowed_pairs((zone,), (0,), avoid_adjacent_zones=False)


def test_direct_pair_selection_and_disabled_seed_mapping() -> None:
    """
    Generate only separated pairs while retaining exact legacy output when disabled.
    """
    zones = tuple(range(26))
    pairs = allowed_pairs(zones, zones, avoid_adjacent_zones=True)
    expected = tuple(
        (a, b)
        for a in zones
        for b in zones
        if any(abs(ZONES[a][axis] - ZONES[b][axis]) == 2 for axis in range(3))
    )
    assert pairs == expected
    assert len(allowed_pairs(zones, zones, avoid_adjacent_zones=False)) == 26 * 25
    for seed in range(32):
        config = Config(seed, 3, 0.75, 300, 300)
        scene = generate_layout(config)
        assert (scene.a.zone, scene.b.zone) in pairs
        assert generate_layout(config) == scene
        assert generate_layout(config, avoid_adjacent_zones=False) == generate(config)


@pytest.mark.parametrize("mode", ("systematic", "random"))
def test_range_schedule_uses_only_allowed_pairs_and_freezes_preference(mode: str) -> None:
    """
    Filter the finite pair list before counting or sampling, preserving replay order.
    """
    payload = specification()
    payload.update(mode=mode, avoid_adjacent_zones=True)
    for name in ("a_zone", "b_zone"):
        payload["ranges"][name] = {"min": 1, "max": 26, "step": 1}
    payload["ranges"]["lines"] = {"min": 1, "max": 1, "step": 1}
    spec = Specification.parse(payload)
    expected = allowed_pairs(tuple(range(26)), tuple(range(26)), avoid_adjacent_zones=True)
    assert spec.zone_pairs == tuple((a + 1, b + 1) for a, b in expected)
    assert spec.combinations == len(expected)
    replay = Specification.parse(spec.payload())
    for index in (0, 1, 17, spec.combinations - 1, spec.combinations):
        scene = spec.scene(index)
        assert not adjacent(scene.a.zone, scene.b.zone)
        assert replay.scene(index) == scene
    assert spec.payload()["avoid_adjacent_zones"] is True


def test_adjacent_only_ranges_reject_and_legacy_plans_replay_unchanged() -> None:
    """
    Explain empty allowed ranges and keep historical input choices and payloads intact.
    """
    payload = specification()
    payload["ranges"]["a_zone"] = {"min": "1", "max": "1", "step": "1"}
    payload["ranges"]["b_zone"] = {"min": "2", "max": "2", "step": "1"}
    payload["avoid_adjacent_zones"] = True
    with pytest.raises(ValueError, match="Broaden zone ranges or disable"):
        Specification.parse(payload)
    payload["avoid_adjacent_zones"] = False
    disabled = Specification.parse(payload)
    assert disabled.zone_pairs == ((1, 2),)
    assert disabled.payload()["avoid_adjacent_zones"] is False
    del payload["avoid_adjacent_zones"]
    legacy = Specification.parse(payload)
    assert legacy.payload() == payload
    assert [legacy.scene(i) for i in range(8)] == [disabled.scene(i) for i in range(8)]
    assert defaults(legacy.scene(0))["avoid_adjacent_zones"] is True


@pytest.mark.parametrize("value", (None, 0, 1, "false"))
def test_placement_preference_requires_a_boolean(value: Any) -> None:
    """
    Never interpret strings or integers as permission to enable or disable the policy.
    """
    payload = specification()
    payload["avoid_adjacent_zones"] = value
    with pytest.raises(ValueError, match="explicitly"):
        Specification.parse(payload)
    with pytest.raises(ValueError, match="explicitly"):
        generate_layout(avoid_adjacent_zones=value)


def test_interactive_policy_rejects_edits_without_moving_existing_geometry(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Toggle without redrawing historical inputs; enforce only subsequent user edits.
    """
    del addin_module
    module = importlib.import_module("devtools.ribbon_analysis.gym.view")
    view: Any = object.__new__(module.GymView)
    view.scene = Scene(Config(), Goal(0, 0), Goal(2, 0))
    view.avoid_adjacent_zones = True
    view.palette = view.open_diagnostics = view.performance = None
    view._draw, view._record = Mock(), Mock()
    view.revision = 0
    original = view.scene
    state = view.dispatch("ready", {})
    assert 1 not in state["eligible_b_zones"] and 2 in state["eligible_b_zones"]
    with pytest.raises(ValueError, match="non-adjacent"):
        view.dispatch("select", {"role": "b", "zone": 1, "face": 0, "roll": 0})
    assert view.scene is original and view.revision == 0
    view.dispatch("placement", {"avoid_adjacent_zones": False})
    view._draw.assert_not_called()
    view.dispatch("select", {"role": "b", "zone": 1, "face": 0, "roll": 0})
    historical = view.scene
    assert historical.b.zone == 1 and view.revision == 1
    view._draw.reset_mock()
    view.dispatch("placement", {"avoid_adjacent_zones": True})
    assert view.scene is historical and view.revision == 1
    assert view.dispatch("ready", {})["avoid_adjacent_zones"] is True
    view._draw.assert_not_called()
