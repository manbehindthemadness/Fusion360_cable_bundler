"""
Verify that reflected flat guidance keeps witness identity while selecting its axis at the working pose.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import flat_separation
from experiments.experiment_ribbon_terminal_hardware.flat_separation import FlatSeparation
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("scale", (1.0, 2.0, 10.0))
@pytest.mark.parametrize("bank", (-0.4, 0.0, 0.3))
def test_initial_axis_uses_reflected_placement_without_reinterpreting_source_regions(
    monkeypatch: pytest.MonkeyPatch, scale: float, bank: float
) -> None:
    """
    Match a directly measured working-pose axis with one SAT selection and unchanged complete coverage.
    """
    source = _route(
        (
            Straight(3 * scale),
            fold(2 * scale, 1.2, 1.3, bank, scale),
            Straight(4 * scale),
            fold(2 * scale, 1.2, -0.8, -0.2, scale),
            Straight(2 * scale),
        )
    )
    witness = Penetration((0, 4), (0.5, 0.0, 0.0), (0.5, 0.0, 0.0), Vector3(0, 0, 0))
    model = IncidentJoints(source, 0)
    reflected = model.route(model.initial)
    assert reflected is not None and len(reflected.pieces) == len(source.pieces)
    original = MaterialConstraint.from_witness(model, source, witness)
    expected = MaterialConstraint.from_witness(model, reflected, witness)
    assert original is not None and expected is not None
    prism = Mock(wraps=flat_separation.flat_prism)
    monkeypatch.setitem(vars(flat_separation), "flat_prism", prism)
    actual = MaterialConstraint.from_witness(model, source, witness, axis_values=model.initial)
    assert actual is not None and isinstance(actual.bound, FlatSeparation)
    assert prism.call_count == 2
    assert actual.pair == original.pair == expected.pair
    assert actual.parts == original.parts == expected.parts
    assert all(
        part.low_q == -source.half_width_mm and part.high_q == source.half_width_mm
        for part in actual.parts
    )
    assert all(part.half_height > source.targets.diameter_mm / 2 for part in actual.parts)
    assert actual.bound.axis == expected.bound.axis
    for side in Side:
        assert actual.gap(model.initial, side) == expected.gap(model.initial, side)


def test_unspecified_working_pose_keeps_original_axis_selection() -> None:
    """
    Later measured contacts and default source-frame callers retain their original deterministic axis.
    """
    source = _route((Straight(3), fold(2, 1.2, 1.3, 0.3, 1), Straight(2)))
    model = IncidentJoints(source, 0)
    witness = Penetration((0, 2), (0.5, 0.0, 0.0), (0.5, 0.0, 0.0), Vector3(0, 0, 0))
    direct = FlatSeparation.create(
        model, source, witness, extent=flat_separation.ProfileExtent.COMPLETE
    )
    default = MaterialConstraint.from_witness(model, source, witness)
    assert direct is not None and default is not None and default.bound == direct
