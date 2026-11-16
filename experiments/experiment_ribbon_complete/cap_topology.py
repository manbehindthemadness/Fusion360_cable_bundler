"""
Validate complete ordered material-cap edge chains independently of Fusion API access.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class CapEdge:
    """
    Retain one observed edge's original profile label and two body-local vertex identities.
    """

    ordinal: int
    profile: str
    vertices: tuple[int, int]

    def __post_init__(self) -> None:
        """
        Reject ambiguous identifiers instead of guessing a missing topological endpoint.
        """
        if (
            type(self.ordinal) is not int
            or self.ordinal < 0
            or not isinstance(self.profile, str)
            or not self.profile.strip()
            or len(self.vertices) != 2
            or any(type(x) is not int for x in self.vertices)
        ):
            raise ValueError("Explicit original edge, profile and two vertex identities required")


@dataclass(frozen=True)
class CapLoopEvidence:
    """
    Keep the full observed chain set and uncertainty without implying interior contact acceptance.

    Native source ownership, coordinates, orientation in world space and collar
    contact require separate evidence. This checks undirected cyclic label order.
    """

    edges: tuple[CapEdge, ...]
    profile_order: tuple[str, ...]
    status: str
    problems: tuple[str, ...]


def _connected(neighbors: dict[int, list[int]]) -> bool:
    """
    Check one whole finite graph without dropping isolated components.
    """
    if not neighbors:
        return False
    pending = [next(iter(neighbors))]
    seen = set()
    while pending:
        vertex = pending.pop()
        if vertex not in seen:
            seen.add(vertex)
            pending.extend(neighbors[vertex])
    return len(seen) == len(neighbors)


def inspect_cap_loop(
    edges: tuple[CapEdge, ...], profile_order: tuple[str, ...], checkpoint: Callable[[], None]
) -> CapLoopEvidence:
    """
    Require one closed cycle and one complete nonbranching chain for every original profile arc.

    Multiple native edges per profile are supported. Missing arcs, disconnected
    fragments, branches, self-loops and cyclic label permutations remain unresolved.
    Reversing traversal direction does not change the original material labels.
    """
    checkpoint()
    if (
        len(profile_order) < 3
        or len(set(profile_order)) != len(profile_order)
        or any(not isinstance(x, str) or not x.strip() for x in profile_order)
        or len({e.ordinal for e in edges}) != len(edges)
        or any(e.profile not in profile_order for e in edges)
    ):
        raise ValueError(
            "Unique original edge identities and complete cyclic profile labels required"
        )
    graph: dict[int, list[int]] = defaultdict(list)
    incident: dict[int, list[int]] = defaultdict(list)
    groups: dict[str, list[CapEdge]] = defaultdict(list)
    problems = []
    for index, edge in enumerate(edges):
        checkpoint()
        a, b = edge.vertices
        graph[a].append(b)
        graph[b].append(a)
        incident[a].append(index)
        incident[b].append(index)
        groups[edge.profile].append(edge)
        if a == b:
            problems.append("self_loop")
    if any(len(v) != 2 for v in graph.values()):
        problems.append("nonmanifold_cap_vertices")
    if not _connected(graph):
        problems.append("disconnected_cap")
    if set(groups) != set(profile_order):
        problems.append("missing_profiles")
    for profile in profile_order:
        checkpoint()
        chain: dict[int, list[int]] = defaultdict(list)
        for edge in groups[profile]:
            a, b = edge.vertices
            chain[a].append(b)
            chain[b].append(a)
        if (
            not _connected(chain)
            or sum(len(v) == 1 for v in chain.values()) != 2
            or any(len(v) not in (1, 2) for v in chain.values())
        ):
            problems.append(f"profile_not_single_open_chain:{profile}")
    if not problems:
        start = edges[0].vertices[0]
        vertex, current = start, 0
        labels = []
        visited = set()
        while current not in visited:
            checkpoint()
            visited.add(current)
            edge = edges[current]
            if not labels or labels[-1] != edge.profile:
                labels.append(edge.profile)
            a, b = edge.vertices
            vertex = b if vertex == a else a
            next_edges = incident[vertex]
            current = next_edges[0] if next_edges[1] == current else next_edges[1]
        if len(labels) > 1 and labels[0] == labels[-1]:
            labels.pop()
        observed = tuple(labels)
        orders = (profile_order, tuple(reversed(profile_order)))
        if (
            vertex != start
            or len(visited) != len(edges)
            or not any(
                observed == order[i:] + order[:i] for order in orders for i in range(len(order))
            )
        ):
            problems.append("cyclic_profile_order")
    return CapLoopEvidence(
        edges,
        profile_order,
        "certified_ordered_cap_cycle" if not problems else "unresolved_cap_topology",
        tuple(problems),
    )
