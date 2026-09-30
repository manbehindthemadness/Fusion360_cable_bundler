"""
Verify Fusion open-guide sampling without a live design session.
"""

from __future__ import annotations

import math
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace
from uuid import UUID

import pytest

from cable_bundler.domain import CableGroupType, HarnessDefinition, OpenGuideAlignment
from cable_bundler.routing import RibbonEndFit, RibbonFrame, RoutePreview, Vector3, ribbon_frames
from tests.fusion_ui_support import _PaletteLifecycleModule


def _vector(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
    """
    Supply a Fusion-like point or vector in centimeter model coordinates.
    """
    return SimpleNamespace(x=x, y=y, z=z)


@pytest.mark.parametrize("line_count", (3, 40))
@pytest.mark.parametrize("curvature", (0.0, 0.01))
def test_center_alignment_samples_ordered_guide_curve(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    line_count: int,
    curvature: float,
) -> None:
    """
    Keep all conductor centers on the actual curve for small and broad ribbons.
    """
    ribbon = import_module("cable_bundler.fusion.ribbon_geometry")
    evaluator = SimpleNamespace(
        getParameterExtents=lambda: (True, 0.0, 10.0),
        getLengthAtParameter=lambda _start, _end: (True, 10.0),
        getParameterAtLength=lambda _start, length: (True, length),
        getPointAtParameter=lambda parameter: (
            True,
            _vector(parameter, curvature * (parameter - 5.0) ** 2),
        ),
        getFirstDerivative=lambda parameter: (
            True,
            _vector(1.0, 2.0 * curvature * (parameter - 5.0)),
        ),
    )
    plane = object()
    sketch = SimpleNamespace(
        isParametric=True,
        referencePlane=plane,
        origin=_vector(5.0, 0.0),
        xDirection=_vector(1.0, 0.0),
        yDirection=_vector(0.0, 1.0),
    )
    curve = SimpleNamespace(
        isValid=True,
        parentSketch=sketch,
        worldGeometry=SimpleNamespace(evaluator=evaluator),
    )
    monkeypatch.setitem(
        vars(ribbon.adsk.fusion), "SketchCurve", SimpleNamespace(cast=lambda entity: entity)
    )
    design = SimpleNamespace(findEntityByToken=lambda _token: (curve,))
    frame = RibbonFrame(Vector3(50, 0, 0), Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))

    fit, resolved_plane = ribbon._guide_fit(
        design, "guide", OpenGuideAlignment.CENTER, frame, line_count, 1.5
    )

    assert resolved_plane.reference_plane is plane
    assert resolved_plane.origin == Vector3(50, 0, 0)
    assert len(fit.centers) == line_count
    assert all(
        math.isclose(point.y, curvature * (point.x / 10.0 - 5.0) ** 2 * 10.0)
        for point in fit.centers
    )
    assert all(right.x > left.x for left, right in zip(fit.centers, fit.centers[1:]))


@pytest.mark.parametrize("alignment", (OpenGuideAlignment.LEFT, OpenGuideAlignment.RIGHT))
def test_end_alignment_reports_insufficient_guide_span(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    alignment: OpenGuideAlignment,
) -> None:
    """
    Do not extrapolate a ribbon beyond a finite open guide to claim exact fit.
    """
    ribbon = import_module("cable_bundler.fusion.ribbon_geometry")
    evaluator = SimpleNamespace(
        getParameterExtents=lambda: (True, 0.0, 10.0),
        getLengthAtParameter=lambda _start, _end: (True, 10.0),
        getParameterAtLength=lambda _start, length: (True, length),
        getPointAtParameter=lambda parameter: (True, _vector(parameter, 0.0)),
        getFirstDerivative=lambda _parameter: (True, _vector(1.0, 0.0)),
    )
    curve = SimpleNamespace(
        isValid=True,
        parentSketch=SimpleNamespace(
            isParametric=True,
            referencePlane=object(),
            origin=_vector(0.0, 0.0),
            xDirection=_vector(1.0, 0.0),
            yDirection=_vector(0.0, 1.0),
        ),
        worldGeometry=SimpleNamespace(evaluator=evaluator),
    )
    monkeypatch.setitem(
        vars(ribbon.adsk.fusion), "SketchCurve", SimpleNamespace(cast=lambda entity: entity)
    )
    design = SimpleNamespace(findEntityByToken=lambda _token: (curve,))
    frame = RibbonFrame(Vector3(0, 0, 0), Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))

    with pytest.raises(ValueError, match="too short"):
        ribbon._guide_fit(design, "guide", alignment, frame, 3, 1.5)


def test_nonparametric_guide_never_reads_reference_plane(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve fit samples when Fusion rejects referencePlane for a direct sketch.
    """
    ribbon = import_module("cable_bundler.fusion.ribbon_geometry")

    class DirectSketch:
        """
        Reproduce the dcSketch error from Pathway_001's two guides.
        """

        isParametric = False
        origin = _vector(0.0, 0.0, 2.0)
        xDirection = _vector(1.0, 0.0)
        yDirection = _vector(0.0, 1.0)

        @property
        def referencePlane(self) -> object:
            """
            Fail if the direct-sketch-only API boundary is crossed.
            """
            raise RuntimeError("2 : InternalValidationError : dcSketch")

    evaluator = SimpleNamespace(
        getParameterExtents=lambda: (True, 0.0, 10.0),
        getLengthAtParameter=lambda _start, _end: (True, 10.0),
        getParameterAtLength=lambda _start, length: (True, length),
        getPointAtParameter=lambda parameter: (True, _vector(parameter, 0.0, 2.0)),
        getFirstDerivative=lambda _parameter: (True, _vector(1.0, 0.0)),
    )
    curve = SimpleNamespace(
        isValid=True,
        parentSketch=DirectSketch(),
        worldGeometry=SimpleNamespace(evaluator=evaluator),
    )
    monkeypatch.setitem(
        vars(ribbon.adsk.fusion), "SketchCurve", SimpleNamespace(cast=lambda entity: entity)
    )
    frame = RibbonFrame(Vector3(50, 0, 20), Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))

    fit, guide_plane = ribbon._guide_fit(
        SimpleNamespace(findEntityByToken=lambda _token: (curve,)),
        "guide",
        OpenGuideAlignment.CENTER,
        frame,
        3,
        1.5,
    )

    assert fit.centers[1] == Vector3(50, 0, 20)
    assert guide_plane.origin == Vector3(0, 0, 20)
    assert guide_plane.normal == Vector3(0, 0, 1)
    assert guide_plane.reference_plane is None


def test_fixed_guide_pitch_warning_preserves_fitted_end_samples(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Report an overwide guide without discarding its physical end anchors.
    """
    ribbon = import_module("cable_bundler.fusion.ribbon_geometry")
    route = RoutePreview(UUID(int=91), "Guide", (Vector3(0, 0, 0), Vector3(0, 0, 100)))
    start_id, end_id = UUID(int=92), UUID(int=93)
    start_fit = RibbonEndFit(
        (Vector3(-1.62, 0, 0), Vector3(0, 0, 0), Vector3(1.62, 0, 0)),
        (Vector3(0, 1, 0),) * 3,
    )
    end_fit = RibbonEndFit(
        (Vector3(-1.5, 0, 100), Vector3(0, 0, 100), Vector3(1.5, 0, 100)),
        (Vector3(0, 1, 0),) * 3,
    )
    plane = ribbon.RibbonGuidePlane(Vector3(0, 0, 0), Vector3(0, 0, 1))
    monkeypatch.setitem(
        vars(ribbon),
        "ribbon_route_frames",
        lambda _design, _definition, _leg, _route, maximum_sections=32: ribbon_frames(
            route, Vector3(1, 0, 0), Vector3(1, 0, 0), maximum_sections=maximum_sections
        ),
    )
    monkeypatch.setitem(
        vars(ribbon),
        "_guide_fit",
        lambda _design, token, _alignment, _frame, _count, _diameter: (
            start_fit if token == "start" else end_fit,
            plane,
        ),
    )
    definition = SimpleNamespace(
        connections=(
            SimpleNamespace(
                connection_id=start_id,
                member_tokens=("start",),
                resolved_member_alignments=(OpenGuideAlignment.CENTER,),
            ),
            SimpleNamespace(
                connection_id=end_id,
                member_tokens=("end",),
                resolved_member_alignments=(OpenGuideAlignment.CENTER,),
            ),
        )
    )
    leg = SimpleNamespace(start_connection_id=start_id, end_connection_id=end_id)

    fitted = ribbon.ribbon_route_shape(object(), definition, leg, route, 3, 1.5)

    assert fitted.shape.start_fit == start_fit
    assert fitted.shape.end_fit == end_fit
    assert tuple(lane[0] for lane in fitted.shape.lanes) == start_fit.centers
    assert tuple(lane[-1] for lane in fitted.shape.lanes) == end_fit.centers
    assert fitted.shape.maximum_pitch_ratio >= 1.08
    assert fitted.fit_warnings == (
        "fixed guide ends exceed the 3% adjacent-line pitch target; anchors preserved",
    )


def test_terminal_profile_uses_sampled_guide_edges(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Place each lobe valley on its sampled curve edge before lofting.
    """
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    monkeypatch.setattr(
        "cable_bundler.fusion.cable_solid_parts.ribbon_builder.fusion_point",
        lambda point, _transform: point,
    )
    sketch = SimpleNamespace(modelToSketchSpace=lambda point: point)
    frame = RibbonFrame(Vector3(0, 0, 0), Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))
    fit = RibbonEndFit(
        (Vector3(-1.5, 0.1, 0), Vector3(0, 0, 0), Vector3(1.5, 0.1, 0)),
        (Vector3(0, 1, 0),) * 3,
        (
            Vector3(-2.25, 0.3, 0),
            Vector3(-0.75, 0.025, 0),
            Vector3(0.75, 0.025, 0),
            Vector3(2.25, 0.3, 0),
        ),
        (Vector3(0, 1, 0),) * 4,
    )

    point = builder._lane_section_point(
        sketch, frame, fit.centers, fit.normals, fit, -0.75, 0.45, 1.5, object()
    )

    assert point.x == -0.75
    assert point.y == pytest.approx(0.475)
    assert point.z == 0.0


@pytest.mark.parametrize("parametric", (False, True))
def test_terminal_section_uses_the_available_guide_plane_kind(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
    parametric: bool,
) -> None:
    """
    Define direct guide planes by geometry and parametric ones by reference.
    """
    ribbon = import_module("cable_bundler.fusion.ribbon_geometry")
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    calls: list[str] = []
    reference = object() if parametric else None
    guide = ribbon.RibbonGuidePlane(Vector3(0, 0, 0), Vector3(0, 0, 1), reference)
    plane_input = SimpleNamespace(
        setByPlane=lambda _plane: calls.append("direct") or True,
        setByOffset=lambda _plane, _distance: calls.append("parametric") or True,
    )
    plane = SimpleNamespace(name="", isLightBulbOn=True)
    section = SimpleNamespace(
        name="",
        isLightBulbOn=True,
        modelToSketchSpace=lambda point: point,
        sketchCurves=SimpleNamespace(
            sketchArcs=SimpleNamespace(addByThreePoints=lambda _start, _middle, _end: object())
        ),
        profiles=SimpleNamespace(count=1),
    )
    component = SimpleNamespace(
        constructionPlanes=SimpleNamespace(
            createInput=lambda: plane_input,
            add=lambda _input: plane,
        ),
        sketches=SimpleNamespace(add=lambda _plane: section),
    )
    monkeypatch.setitem(
        vars(builder.adsk.core), "ValueInput", SimpleNamespace(createByReal=lambda value: value)
    )
    monkeypatch.setattr(
        "cable_bundler.fusion.cable_solid_parts.ribbon_builder.fusion_point",
        lambda point, _transform: _vector(point.x / 10, point.y / 10, point.z / 10),
    )
    monkeypatch.setitem(
        vars(builder.adsk.core),
        "Vector3D",
        SimpleNamespace(
            create=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z, normalize=lambda: True)
        ),
    )
    monkeypatch.setitem(
        vars(builder.adsk.core), "Plane", SimpleNamespace(create=lambda _origin, _normal: object())
    )
    group = replace(valid_harness.cable_groups[0], group_type=CableGroupType.RIBBON)
    frame = RibbonFrame(Vector3(0, 0, 0), Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))

    created_section, created_plane = builder._add_section(
        component, object(), frame, group, object(), guide_plane=guide
    )

    assert (created_section, created_plane) == (section, plane)
    assert calls == (["parametric"] if parametric else ["direct"])
