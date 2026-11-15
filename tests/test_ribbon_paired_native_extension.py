"""
Verify orientation-ready extension uses existing charged work before positional closure.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_paired_return import continuation
from experiments.experiment_ribbon_paired_return.ledger import Ledger
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_pair_family_motion import _route


def _open_source(orientation_matches: bool) -> FoldRoute:
    """
    Recompose real material with a tiny positive lead and an explicitly open positional target.
    """
    original = _route(1, 1)
    shapes = (Straight(1e-8), *(p.geometry for p in original.pieces[1:]))
    pose = original.pieces[0].pose
    pieces = []
    for shape in shapes:
        piece = PlacedPiece(pose, shape, "Analytical native extension")
        pieces.append(piece)
        pose = piece.end_pose()
    targets = replace(
        original.targets,
        end=pose.origin.translated(original.targets.start_tangent, 1e-4),
        end_tangent=pose.tangent,
        end_width=pose.width
        if orientation_matches
        else Vector3(-pose.width.x, -pose.width.y, -pose.width.z),
    )
    return replace(original, pieces=tuple(pieces), targets=targets)


@pytest.mark.parametrize("orientation_matches", [True, False])
def test_open_sliver_extension_requires_orientation_and_spends_one_original_newton(
    monkeypatch: pytest.MonkeyPatch,
    orientation_matches: bool,
) -> None:
    """
    Extend positive material without waiting for position closure; orientation mismatch cannot enter.

    The projector deliberately declines, so this is an ordering/accounting test,
    never a proof of solved geometry or hardware clearance.
    """
    source = _open_source(orientation_matches)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    ledger = Ledger(Work(1, 2048, 0.35, 2, 1), 0, lambda: None)
    ledger.start_action()
    monkeypatch.setitem(
        vars(continuation), "constraints", Mock(return_value=(lambda coordinates: -1.0,))
    )
    projected = Mock(return_value=None)
    monkeypatch.setitem(vars(continuation), "redistributed_step", projected)
    events = []
    if orientation_matches:
        result = continuation.correct_started(
            source, source, (), (), (), hardware, 3e-5, ledger, events.append
        )
        assert result is None
    else:
        # This deliberately sub-native source is not an admissible derivative base.
        with pytest.raises(ArithmeticError, match="material domain"):
            continuation.correct_started(
                source, source, (), (), (), hardware, 3e-5, ledger, events.append
            )
    assert (ledger.updates, ledger.newton_steps, ledger.roots) == (1, 1, 0)
    extensions = [event for event in events if event["stage"] == "paired_native"]
    assert len(extensions) == int(orientation_matches)
    assert projected.called == orientation_matches
    if orientation_matches:
        model = projected.call_args.args[0].model
        assert model.native_pins
        values = projected.call_args.args[1]
        assert all(values[index] * model.scale > 3e-5 for index in model.native_pins)
        assert all(values[index] > 0 for index in model.native_pins)
        assert extensions[0]["newton"] == 1
