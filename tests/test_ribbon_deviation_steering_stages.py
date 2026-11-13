"""
Preserve the actual deviation headings without spending roots on a zero-slope midpoint.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_spline_guide.guide import Guide
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_construction as construction,
)
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from tests.test_ribbon_adaptive_events import _source
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("scale", (0.1, 1.0, 10.0))
def test_midpoint_erases_deviation_heading_while_analytic_stations_preserve_it(
    scale: float,
) -> None:
    """
    An independent derivative comparison identifies the two required steering regions at every scale.
    """
    targets = _targets(scale)
    base = Guide.create(targets)
    guide = DeviationGuide.deviated(targets, Vector3(0, 0, 3 * scale))
    assert magnitude(difference(guide.sample(0.5)[1], base.sample(0.5)[1])) == 0
    first, last = DeviationGuide.stations()
    assert 0 < first < 0.5 < last < 1
    for parameter in (first, last):
        assert magnitude(difference(guide.sample(parameter)[1], base.sample(parameter)[1])) > scale


@pytest.mark.parametrize("deviated", (False, True))
def test_constructor_uses_one_geometry_derived_stage_sequence_without_spending_more_roots(
    deviated: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A failed family cannot renew itself with another midpoint/offset stage enumeration.
    """
    source, _, _ = _source()
    window = Window(source, 0, 1)
    targets = window.route.targets
    offset = Vector3(0, 0, 3)
    guide = DeviationGuide.deviated(targets, offset) if deviated else Guide.create(targets)
    proposal = Proposal(window, Frames.from_guide(targets, guide), offset)
    derive = Mock(return_value=())
    monkeypatch.setitem(vars(construction), "chains", derive)
    roots = construction.Roots(attempted=7)
    assert construction.construct(proposal, 1e-5, roots, lambda: None, Mock()) is None
    derive.assert_called_once()
    assert derive.call_args.args[2] == (DeviationGuide.stations() if deviated else (0.5,))
    assert roots.attempted == 7 and roots.newton_steps == 0
