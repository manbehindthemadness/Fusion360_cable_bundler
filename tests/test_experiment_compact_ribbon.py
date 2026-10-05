"""
Check compact fixture feasibility and native cloth-length audit classification.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_diagnosis.compact import compact_cases, route_evidence
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase, audit_end_boundary
from experiments.experiment_secure_discrete_ribbon.contract import (
    certify_curvature,
    discrete_profile_reach,
)
from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.mark.parametrize("case", compact_cases(), ids=lambda case: case.name)
def test_compact_inputs_have_bounded_shortest_gap_and_equal_translated_sides(
    case: RibbonStressCase,
) -> None:
    """
    Certify input curvature and the sphere without disguising approximate optimality.
    """
    assert audit_end_boundary(case)["status"] == "contained"
    certificate = certify_curvature(
        case.route, discrete_profile_reach(case.lines, case.diameter_mm)
    )
    assert certificate.maximum_ratio <= 0.8
    evidence = route_evidence(case)
    assert 0 < evidence["relative_optimality_gap_upper"] < 0.0011
    assert evidence["exact_shortest_proven"] is False
    assert evidence["input_side_length_difference_mm"] == 0
    assert all(
        point.y == 0
        for curve in case.route.curves
        for point in (curve.start, curve.control_a, curve.control_b, curve.end)
    )


def test_missing_native_rails_cannot_pass(addin_module: _PaletteLifecycleModule) -> None:
    """
    An absent or unrecognized rail measurement is never equal-length success.
    """
    del addin_module
    from experiments.experiment_ribbon_diagnosis.cloth import side_lengths

    body = Mock(edges=())
    assert side_lengths(body, compact_cases()[0])["status"] == "unmeasured"


@pytest.mark.parametrize(
    "start,end",
    (
        (-1.5220255084494627, -8.250765640793423e-17),
        (-8.250765640793423e-17, -1.5220255084494627),
        (-1e308, 1e308),
        (1.0, math.nextafter(1.0, 2.0)),
        (0.0, 0.0),
    ),
)
def test_native_samples_stay_within_exact_extents(
    addin_module: _PaletteLifecycleModule, start: float, end: float
) -> None:
    """
    Preserve exact endpoints and keep all queries in range despite cancellation.
    """
    del addin_module
    from experiments.experiment_ribbon_diagnosis.cloth import side_lengths

    parameters: list[float] = []

    def point(parameter: float) -> tuple[bool, SimpleNamespace]:
        """
        Reject the out-of-range input that triggers Fusion's native exception.
        """
        assert math.isfinite(parameter)
        assert min(start, end) <= parameter <= max(start, end)
        parameters.append(parameter)
        return True, SimpleNamespace(x=0, y=0, z=0)

    evaluator = Mock()
    evaluator.getParameterExtents.return_value = (True, start, end)
    evaluator.getPointAtParameter.side_effect = point
    result = side_lengths(Mock(edges=(Mock(evaluator=evaluator),)), compact_cases()[0])
    assert parameters[0] == start
    assert parameters[-1] == end
    assert len(parameters) == 9
    assert result["status"] == "unmeasured"


@pytest.mark.parametrize("end", (math.inf, math.nan))
def test_nonfinite_native_extents_are_rejected(
    addin_module: _PaletteLifecycleModule, end: float
) -> None:
    """
    Clamping must not disguise invalid parameter bounds as valid geometry.
    """
    del addin_module
    from experiments.experiment_ribbon_diagnosis.cloth import side_lengths

    evaluator = Mock()
    evaluator.getParameterExtents.return_value = (True, 0.0, end)
    with pytest.raises(RuntimeError, match="parameter range"):
        side_lengths(Mock(edges=(Mock(evaluator=evaluator),)), compact_cases()[0])
    evaluator.getPointAtParameter.assert_not_called()


@pytest.mark.parametrize(
    "length_factor, expected", ((1.0, "passed"), (1.009, "passed"), (1.02, "failed"))
)
def test_native_length_limit_is_enforced(
    addin_module: _PaletteLifecycleModule, length_factor: float, expected: str
) -> None:
    """
    Compare corresponding physical rails, not inner and outer bend radii.
    """
    del addin_module
    from experiments.experiment_ribbon_diagnosis.cloth import side_lengths

    case = compact_cases()[0]
    radius = discrete_profile_reach(case.lines, case.diameter_mm) / 0.8 * 1.001
    edges = []
    for side in (-1, 1):
        for band in (-1, 1):
            rail_radius = radius + band * 0.3

            def point(
                parameter: float, r: float = rail_radius, s: int = side
            ) -> tuple[bool, SimpleNamespace]:
                """
                Model a native circular seam evaluator in Fusion centimeters.
                """
                return True, SimpleNamespace(
                    x=r * math.sin(parameter) / 10,
                    y=s * 1.5 / 10,
                    z=(radius - r * math.cos(parameter)) / 10,
                )

            evaluator = Mock()
            evaluator.getParameterExtents.return_value = (True, 0, math.pi / 2)
            evaluator.getPointAtParameter.side_effect = point
            edges.append(
                Mock(
                    evaluator=evaluator,
                    length=rail_radius * math.pi / 20 * (length_factor if side == 1 else 1),
                )
            )
    assert side_lengths(Mock(edges=edges), case)["status"] == expected
