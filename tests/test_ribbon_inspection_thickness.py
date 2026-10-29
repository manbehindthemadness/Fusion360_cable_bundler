"""
Verify true-scale continuous thickness shells preserve the recorded diagnostic route.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import difference, dot, magnitude
from devtools.ribbon_analysis.inspection.archive import snapshot_payload
from devtools.ribbon_analysis.inspection.geometry import PathSnapshot
from devtools.ribbon_analysis.inspection.session import Session
from devtools.ribbon_analysis.inspection.thickness import build
from experiments.experiment_ribbon_diagnostic_viewer import examples


@pytest.fixture(params=("single", "ribbon"))
def session(request: pytest.FixtureRequest, tmp_path: Path) -> Session:
    """
    Use both existing authored examples without running any solver.
    """
    return Session(examples.create(tmp_path / "example", request.param, lambda: None))


def _snapshot(session: Session) -> PathSnapshot:
    """
    Require frozen reference geometry for these display-only checks.
    """
    snapshot = session.snapshot
    assert snapshot is not None
    return snapshot


def test_envelope_retains_true_thickness_and_original_profile_anchors(session: Session) -> None:
    """
    Compare all shell sections to the declared diameter and unmodified material guides.
    """
    snapshot = _snapshot(session)
    shell = build(snapshot)
    assert shell.thickness_mm == snapshot.diameter_mm
    width = 32 if snapshot.lines == 1 else 4
    assert len(shell.vertices) == len(snapshot.sections) * width
    for index, section in enumerate(snapshot.sections):
        ring = shell.vertices[index * width : (index + 1) * width]
        if snapshot.lines == 1:
            assert ring == section.outline[:-1]
            assert all(
                magnitude(difference(point, section.frame.origin))
                == pytest.approx(snapshot.diameter_mm / 2)
                for point in ring
            )
        else:
            for top, bottom, anchor in (
                (ring[0], ring[3], section.outline[0]),
                (ring[1], ring[2], section.outline[1]),
            ):
                assert dot(difference(top, bottom), section.frame.y) == pytest.approx(
                    snapshot.diameter_mm
                )
                assert (
                    magnitude(difference(top.translated(difference(bottom, top), 0.5), anchor))
                    < 1e-12
                )
    assert (
        "bonded contour unresolved" in shell.description
        if snapshot.lines > 1
        else "circular" in shell.description
    )


def test_thickness_is_one_closed_connected_shell_with_bounded_opacity(session: Session) -> None:
    """
    Exclude gaps, disconnected conductor shells and opaque overlays that hide the path.
    """
    shell = build(_snapshot(session))
    assert 0 < shell.opacity < 0.5
    edges: Counter[tuple[int, int]] = Counter()
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(shell.vertices))}
    for triangle in shell.triangles:
        assert len(set(triangle)) == 3 and all(
            0 <= index < len(shell.vertices) for index in triangle
        )
        for first, second in zip(triangle, triangle[1:] + triangle[:1]):
            edges[(min(first, second), max(first, second))] += 1
            adjacency[first].add(second)
            adjacency[second].add(first)
    assert set(edges.values()) == {2}
    visited, pending = set(), [0]
    while pending:
        index = pending.pop()
        if index not in visited:
            visited.add(index)
            pending.extend(adjacency[index] - visited)
    assert len(visited) == len(shell.vertices)


def test_both_renderers_receive_the_same_shell_without_changing_archived_geometry(
    session: Session,
) -> None:
    """
    Keep thickness visualization independent of the recorded path and section selection.
    """
    snapshot = _snapshot(session)
    before = snapshot_payload(snapshot)
    shell = asdict(build(snapshot))
    assert session.state()["thickness"] == shell
    session.select_section(8)
    assert session.state()["thickness"] == shell
    assert snapshot_payload(snapshot) == before


def test_mixed_profiles_reject_instead_of_guessing_a_shell(tmp_path: Path) -> None:
    """
    Reject malformed correspondence before rendering a misleading occupied envelope.
    """
    snapshot = _snapshot(Session(examples.create(tmp_path / "example", "single", lambda: None)))
    sections = list(snapshot.sections)
    sections[1] = replace(sections[1], kind="material_ruling", outline=sections[1].outline[:2])
    with pytest.raises(ValueError, match="consistent declared"):
        build(replace(snapshot, sections=tuple(sections)))
