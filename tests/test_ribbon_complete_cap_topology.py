"""
Verify split native-cap chains without replacing missing or unexpected topology.
"""

from dataclasses import replace

import pytest

from experiments.experiment_ribbon_complete.cap_topology import CapEdge, inspect_cap_loop
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def cycle() -> tuple[CapEdge, ...]:
    """
    Keep a closed cycle with two native edges for every original profile arc.
    """
    return tuple(CapEdge(i, "ABC"[i // 2], (i, (i + 1) % 6)) for i in range(6))


def test_split_profile_chains_preserve_original_cyclic_labels_in_either_traversal() -> None:
    """
    Input enumeration and undirected traversal orientation do not change material labels.
    """
    edges = cycle()
    for selected in (edges, tuple(reversed(edges)), edges[3:] + edges[:3]):
        result = inspect_cap_loop(selected, ("A", "B", "C"), checkpoint)
        assert result.edges is selected
        assert result.status == "certified_ordered_cap_cycle" and not result.problems


@pytest.mark.parametrize("kind", ("missing", "branch", "disconnected", "self_loop"))
def test_incomplete_or_nonmanifold_boundaries_cannot_be_certified(kind: str) -> None:
    """
    No edge fragment or disconnected component may disappear from cap coverage.
    """
    edges = cycle()
    if kind == "missing":
        edges = edges[:-1]
    elif kind == "branch":
        edges += (CapEdge(99, "A", (1, 3)),)
    elif kind == "disconnected":
        edges += tuple(
            CapEdge(e.ordinal + 10, e.profile, (e.vertices[0] + 10, e.vertices[1] + 10))
            for e in cycle()
        )
    else:
        edges = (replace(edges[0], vertices=(0, 0)),) + edges[1:]
    result = inspect_cap_loop(edges, ("A", "B", "C"), checkpoint)
    assert result.status == "unresolved_cap_topology" and result.problems


def test_closed_cycle_with_wrong_profile_permutation_is_not_an_ordered_cap() -> None:
    """
    A closed manifold loop alone does not preserve persistent material profile order.
    """
    edges = tuple(CapEdge(i, label, (i, (i + 1) % 4)) for i, label in enumerate("ACBD"))
    result = inspect_cap_loop(edges, tuple("ABCD"), checkpoint)
    assert result.status == "unresolved_cap_topology"
    assert "cyclic_profile_order" in result.problems


def test_malformed_provenance_and_caller_stop_do_not_return_a_cap_certificate() -> None:
    """
    Duplicate IDs, undeclared labels and cancellation are not geometric successes.
    """
    edges = cycle()
    for selected in (edges + (edges[0],), (replace(edges[0], profile="unknown"),) + edges[1:]):
        with pytest.raises(ValueError, match="original edge"):
            inspect_cap_loop(selected, tuple("ABC"), checkpoint)
    with pytest.raises(ValueError, match="two vertex"):
        CapEdge(0, "A", (0, True))

    def stop() -> None:
        """
        Refuse the caller's exhausted allocation without creating partial acceptance.
        """
        raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        inspect_cap_loop(edges, tuple("ABC"), stop)
