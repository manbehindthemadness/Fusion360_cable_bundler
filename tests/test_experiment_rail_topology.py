"""
Require unambiguous native topology before accepting a segmented seam length.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_diagnosis.rail_topology import RailEdge, measure_chain


@pytest.mark.parametrize("segments", (1, 3, 9))
def test_segmented_chain_retains_length_and_orientation(segments: int) -> None:
    """
    Native segmentation and reversed edge storage do not change the measured rail.
    """
    edges = tuple(RailEdge(i, i + 1, i, (10, 20), 12 / segments) for i in range(segments))
    for start, end in ((0, segments), (segments, 0)):
        result = measure_chain(tuple(reversed(edges)), start, end)
        assert result["status"] == "measured"
        assert result["length_mm"] == pytest.approx(12)
        assert len(result["edge_ids"]) == segments


@pytest.mark.parametrize(
    "defect", ("gap", "branch", "duplicate", "disconnected_loop", "face_change", "invalid_length")
)
def test_ambiguous_or_invalid_topology_cannot_pass(defect: str) -> None:
    """
    Do not bridge gaps, choose branches, discard loops, or merge different face pairs.
    """
    edges = [
        RailEdge(0, 0, 1, (10, 20), 4),
        RailEdge(1, 1, 2, (10, 20), 4),
        RailEdge(2, 2, 3, (10, 20), 4),
    ]
    if defect == "gap":
        edges.pop(1)
    elif defect == "branch":
        edges.append(RailEdge(3, 1, 4, (10, 20), 1))
    elif defect == "duplicate":
        edges.append(RailEdge(3, 0, 1, (10, 20), 4))
    elif defect == "disconnected_loop":
        edges.extend((RailEdge(3, 5, 6, (10, 20), 1), RailEdge(4, 6, 5, (10, 20), 1)))
    elif defect == "face_change":
        edges[1] = RailEdge(1, 1, 2, (20, 30), 4)
    else:
        edges[1] = RailEdge(1, 1, 2, (10, 20), float("nan"))
    assert measure_chain(tuple(edges), 0, 3)["status"] == "unmeasured"
