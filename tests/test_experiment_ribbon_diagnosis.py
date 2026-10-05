"""
Verify diagnostic isolation, continuation after rejection, and retained evidence.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase, stress_cases
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon
from experiments.experiment_secure_discrete_ribbon.policy import ExperimentPolicy, exception_chain
from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.mark.parametrize("outcome", ("success", "false", "missing", "empty", "exception"))
def test_archive_required_before_scratch_close(
    addin_module: _PaletteLifecycleModule, tmp_path: Path, outcome: str
) -> None:
    """
    Never discard a scratch when native export fails or produces no durable bytes.
    """
    del addin_module
    from experiments.experiment_ribbon_diagnosis.storage import archive_and_close

    document = Mock()
    path = tmp_path / "geometry.f3d"

    def export(_options: object) -> bool:
        """
        Model successful and failed host export outcomes.
        """
        document.close.assert_not_called()
        if outcome == "exception":
            raise RuntimeError("kernel export failed")
        if outcome in ("success", "empty"):
            path.write_bytes(b"native archive" if outcome == "success" else b"")
        return outcome != "false"

    document.design.exportManager.execute.side_effect = export
    if outcome == "success":
        archive_and_close(document, path)
        document.close.assert_called_once_with(False)
        assert path.read_bytes() == b"native archive"
    else:
        with pytest.raises(RuntimeError):
            archive_and_close(document, path)
        document.close.assert_not_called()


@pytest.mark.parametrize("case", stress_cases(), ids=lambda case: case.name)
def test_analytic_caps_are_independent_of_section_sampling(case: RibbonStressCase) -> None:
    """
    The controlled cap-authoring comparison preserves endpoints and exact normals.
    """
    from cable_bundler.routing.geometry import dot, unit
    from experiments.experiment_ribbon_diagnosis.inputs import analytic_guide_frame

    for start in (True, False):
        curve = case.route.curves[0] if start else case.route.curves[-1]
        parameter = 0 if start else 1
        frame = analytic_guide_frame(case, start)
        assert frame.origin == curve.point(parameter)
        assert dot(frame.tangent, unit(curve.derivative(parameter))) == pytest.approx(1)
        assert dot(frame.width, frame.tangent) == pytest.approx(0, abs=1e-12)
        case.end_boundary.require_contains(
            tuple(
                frame.origin.translated(frame.width, sign * case.lines * case.diameter_mm / 2)
                for sign in (-1, 1)
            )
        )


@pytest.mark.parametrize("policy", tuple(ExperimentPolicy))
def test_diagnostic_policy_attempts_curvature_rejections_and_retains_failure(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch, policy: ExperimentPolicy
) -> None:
    """
    Normal validation deletes failed cases; observation continues and keeps evidence.
    """
    del addin_module
    from experiments.experiment_secure_discrete_ribbon import live

    monkeypatch.setitem(vars(live.adsk.core), "Matrix3D", Mock())
    design = Mock()
    occurrence = design.rootComponent.occurrences.addNewComponent.return_value
    occurrence.isValid = True
    component = occurrence.component
    component.bRepBodies.count = 0
    component.sketches = ()
    certificate = Mock(side_effect=UnsafeRibbon("rejected input"))
    frames = Mock(side_effect=RuntimeError("frame stage reached"))
    monkeypatch.setitem(vars(live), "certify_curvature", certificate)
    monkeypatch.setitem(vars(live), "ribbon_frames", frames)
    case = stress_cases()[0]
    row = live._case(design, case, policy=policy)
    assert row["input_curvature_accepted"] is False
    if policy is ExperimentPolicy.OBSERVE:
        frames.assert_called_once()
        occurrence.deleteMe.assert_not_called()
        assert row["error"] == "frame stage reached"
        assert row["retained_solid_count"] == 0
    else:
        frames.assert_not_called()
        occurrence.deleteMe.assert_called_once()
        assert row["status"] == "unexpected_rejection"


def test_exception_chain_retains_native_cause_and_stops_cycles() -> None:
    """
    Preserve the kernel error under a generic loft wrapper without looping.
    """
    cause = RuntimeError("ASM failure")
    outer = RuntimeError("loft unavailable")
    outer.__cause__ = cause
    cause.__context__ = outer
    assert exception_chain(outer) == ["RuntimeError: loft unavailable", "RuntimeError: ASM failure"]


def test_diagnostic_query_failure_preserves_original_audit_verdict(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A failed native containment query cannot turn an audit failure into another outcome.
    """
    del addin_module
    from experiments.experiment_ribbon_diagnosis.audit_probe import SectionAuditProbe
    from experiments.experiment_secure_discrete_ribbon.audits import AuditFailure

    error = AuditFailure("Cubic 1/5 station 3/40 has 0 local contours; expected one.")
    probe = SectionAuditProbe(Mock(side_effect=error))
    monkeypatch.setattr(probe, "_witness", Mock(side_effect=RuntimeError("query unavailable")))
    with pytest.raises(AuditFailure) as caught:
        probe(Mock(), Mock(), 8)
    assert caught.value is error
    assert probe.findings[0]["probe_error"] == "query unavailable"


@pytest.mark.parametrize("frame_planes", (False, True))
@pytest.mark.parametrize("raises", (False, True))
def test_observer_changes_only_requested_plane_and_restores_private_bindings(
    addin_module: _PaletteLifecycleModule, frame_planes: bool, raises: bool
) -> None:
    """
    The baseline forwards identical inputs; the comparison changes one interior plane.
    """
    del addin_module
    from cable_bundler.routing import RibbonFrame, Vector3
    from experiments.experiment_ribbon_diagnosis.observations import PlanePolicy, SectionObserver

    builder = Mock()
    original_section = builder._add_section
    original_point = builder._lane_section_point
    frame = RibbonFrame(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
    result = (Mock(), Mock())
    result[0].profiles.count = 1
    result[0].sketchCurves.sketchArcs = ()
    original_section.return_value = result
    if raises:
        original_section.side_effect = RuntimeError("profile failed")
    observer = SectionObserver(builder, PlanePolicy.FRAME if frame_planes else PlanePolicy.PATH)
    component, path, group, transform = Mock(), Mock(), Mock(), Mock()
    centers, normals = (frame.origin,), (frame.thickness,)
    observer.install()
    try:
        if raises:
            with pytest.raises(RuntimeError, match="profile failed"):
                builder._add_section(
                    component,
                    path,
                    frame,
                    group,
                    transform,
                    lane_centers=centers,
                    lane_normals=normals,
                )
        else:
            assert (
                builder._add_section(
                    component,
                    path,
                    frame,
                    group,
                    transform,
                    lane_centers=centers,
                    lane_normals=normals,
                )
                is result
            )
    finally:
        observer.restore()
    assert builder._add_section is original_section
    assert builder._lane_section_point is original_point
    args, kwargs = original_section.call_args
    assert args == (component, path, frame, group, transform)
    assert kwargs["lane_centers"] is centers
    assert kwargs["lane_normals"] is normals
    if frame_planes:
        assert kwargs["guide_plane"].origin == frame.origin
        assert kwargs["guide_plane"].normal == frame.tangent
    else:
        assert kwargs["guide_plane"] is None
    assert observer.current is None
    assert observer.records[0].error == ("profile failed" if raises else None)
