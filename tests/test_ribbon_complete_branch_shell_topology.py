"""
Verify oriented manifold shell incidence independently of Fusion and geometric sampling.
"""

from __future__ import annotations

from collections import Counter

import pytest

from experiments.experiment_ribbon_complete.branch_shell_topology import loops
from experiments.experiment_ribbon_complete.spatial_frame import ChartOrientation
from tests.test_ribbon_complete_lengths import checkpoint


@pytest.mark.parametrize("spans,edges", ((1, 3), (1, 6), (3, 5), (4, 8)))
@pytest.mark.parametrize("orientation", tuple(ChartOrientation))
def test_closed_shell_has_two_opposed_uses_per_edge_and_consistent_vertex_cycles(
    spans: int, edges: int, orientation: ChartOrientation
) -> None:
    """
    Every face closes, each shared edge has opposite uses, and Euler characteristic is two.
    """
    faces = loops(spans, edges, orientation, checkpoint)
    uses = Counter((use.key, use.opposed) for face in faces for use in face)
    keys = {key for key, _ in uses}
    assert len(faces) == spans * edges + 2
    assert all(uses[key, False] == uses[key, True] == 1 for key in keys)
    vertices = set()
    for face in faces:
        endpoints = []
        for use in face:
            kind, station, edge = use.key
            start = (station, edge)
            end = (station + 1, edge) if kind == "along" else (station, (edge + 1) % edges)
            endpoints.append((end, start) if use.opposed else (start, end))
            vertices.update((start, end))
        assert all(
            first[1] == second[0] for first, second in zip(endpoints, endpoints[1:] + endpoints[:1])
        )
    assert len(vertices) - len(keys) + len(faces) == 2


def test_caller_stop_prevents_incidence_generation() -> None:
    """
    The topology adapter cannot grant a fresh resource allocation.
    """

    def stopped() -> None:
        """
        Refuse new work using the caller's existing stop.
        """
        raise RuntimeError("latched topology stop")

    with pytest.raises(RuntimeError, match="latched"):
        loops(3, 5, ChartOrientation.NEGATIVE, stopped)
