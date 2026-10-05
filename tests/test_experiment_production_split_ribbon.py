"""
Verify unedited source provenance, isolated bindings, and the public build adapter.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from cable_bundler.domain import CableGroupDefinition, RibbonBodyType
from experiments.experiment_production_split_ribbon.sources import (
    SOURCES,
    load_sources,
    verify_sources,
)
from tests.fusion_ui_support import _PaletteLifecycleModule


def test_copies_are_byte_identical_to_pinned_production() -> None:
    """
    Keep all six source files unedited, executable, and tied to production hashes.
    """
    assert verify_sources() == {source.name: source.sha256 for source in SOURCES}
    directory = (
        Path(__file__).resolve().parents[1]
        / "experiments/experiment_production_split_ribbon/snapshot"
    )
    for source in SOURCES:
        ast.parse((directory / f"{source.name}.py.source").read_text(encoding="utf-8"))


def test_production_drift_is_not_silently_compared(tmp_path: Path) -> None:
    """
    Refuse a stale copy when even the first production dependency has changed.
    """
    path = tmp_path / "cable_bundler/routing/ribbon.py"
    path.parent.mkdir(parents=True)
    path.write_text("changed production source\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source drift"):
        verify_sources(tmp_path)


def test_copied_dependencies_do_not_replace_production_or_secured_bindings(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Execute copies through private modules while leaving both existing stacks intact.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts import ribbon_builder
    from cable_bundler.routing import ribbon, ribbon_bank, ribbon_shape
    from experiments.experiment_production_split_ribbon.live import _harness
    from experiments.experiment_secure_discrete_ribbon import live as secured

    originals = (
        ribbon.ribbon_frames,
        ribbon_bank.bank_ribbon_frames,
        ribbon_shape.solve_ribbon_shape,
        ribbon_builder.build_discrete_ribbon_solid,
        secured._build_folded_loft,
    )
    modules = load_sources()
    harness = _harness(modules)
    assert harness is not secured
    assert harness.ribbon_frames is modules["frames"].ribbon_frames
    assert harness.solve_ribbon_shape is modules["shape"].solve_ribbon_shape
    assert harness.build_ribbon_exit_loft is modules["exits"].build_ribbon_exit_loft
    assert modules["shape"].ribbon_lane_points is modules["frames"].ribbon_lane_points
    assert modules["exits"]._lane_section_point is modules["builder"]._lane_section_point
    assert modules["builder"].build_discrete_ribbon_solid.__code__.co_filename.endswith(
        "builder.py.source"
    )
    assert originals == (
        ribbon.ribbon_frames,
        ribbon_bank.bank_ribbon_frames,
        ribbon_shape.solve_ribbon_shape,
        ribbon_builder.build_discrete_ribbon_solid,
        secured._build_folded_loft,
    )


def test_main_adapter_calls_public_production_builder(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Exercise the full public entry point rather than only its fitted loft helper.
    """
    del addin_module
    from experiments.experiment_production_split_ribbon.live import _build_main, _landmarks
    from experiments.experiment_secure_discrete_ribbon.audits import AuditFailure

    section = Mock(name="section")
    section.name = "Host-renamed section"
    guide = Mock(name="guide")
    guide.name = "Cable-end A"
    component = Mock()
    component.sketches = (guide, section)
    builder = Mock()
    body = builder.build_discrete_ribbon_solid.return_value
    result = (Mock(), (section,), ())
    original = Mock(return_value=result)
    builder._build_folded_loft = original
    group = CableGroupDefinition(uuid4(), (uuid4(), uuid4()))
    shape, transform, route, design = Mock(), Mock(), Mock(), Mock()
    notices: list[str] = []
    observations: dict[str, object] = {}

    def build_public(*_args: object, **_kwargs: object) -> Mock:
        """
        Model the public entry delegating to its copied fitted loft unchanged.
        """
        returned = builder._build_folded_loft(
            component, None, shape, group, transform, (None, None)
        )
        assert returned is result
        return body

    builder.build_discrete_ribbon_solid.side_effect = build_public
    output, sections, planes = _build_main(
        component,
        None,
        shape,
        group,
        transform,
        (None, None),
        builder=builder,
        route=route,
        notices=notices,
        observations=observations,
        design=design,
    )
    assert output.bodies.item(0) is body
    assert sections == (section,) and planes == ()
    assert builder.build_discrete_ribbon_solid.call_count == 1
    arguments, keywords = builder.build_discrete_ribbon_solid.call_args
    assert arguments[:7] == (component, group, 0, route, shape, (None, None), transform)
    assert arguments[9:] == (design, "production_split_experiment")
    assert group.ribbon_body_type is RibbonBodyType.SPLIT
    assert keywords == {"notices": notices}
    assert builder._build_folded_loft is original
    original.assert_called_once_with(component, None, shape, group, transform, (None, None))
    assert observations == {"loft_section_count": 1, "loft_section_names": ["Host-renamed section"]}
    with pytest.raises(IndexError):
        output.bodies.item(1)
    with pytest.raises(AuditFailure, match="no fitted interior"):
        _landmarks(body, sections, 3)

    builder.build_discrete_ribbon_solid.side_effect = RuntimeError("API failure")
    with pytest.raises(RuntimeError, match="API failure"):
        _build_main(
            component,
            None,
            shape,
            group,
            transform,
            (None, None),
            builder=builder,
            route=route,
            notices=notices,
            observations=observations,
            design=design,
        )
    assert builder._build_folded_loft is original
