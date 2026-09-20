"""
Plan non-duplicated preview legs for connected cable-end groups.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid5

from ..domain import HarnessDefinition, PathwayEndpoint
from .edit_cable_groups import cable_end_locations


@dataclass(frozen=True)
class CableGroupControlStep:
    """
    Identify one routed control and whether it is traversed in reverse.
    """

    control_id: UUID
    reversed: bool = False


@dataclass(frozen=True)
class CableGroupRouteLeg:
    """
    Describe one maximal terminal-or-junction leg of a cable-group tree.

    A missing connection endpoint means that end terminates at the first or
    last junction control in ``control_steps``.
    """

    route_id: UUID
    cable_group_id: UUID
    label: str
    start_connection_id: Optional[UUID]
    end_connection_id: Optional[UUID]
    control_steps: tuple[CableGroupControlStep, ...]
    pathway_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class _Node:
    """
    Provide a stable, sortable identity for one topology node.
    """

    kind: str
    identity: UUID
    endpoint: Optional[PathwayEndpoint] = None

    @property
    def key(self) -> str:
        """
        Return a deterministic serialization used for ordering and route IDs.
        """
        suffix = self.endpoint.value if self.endpoint is not None else ""
        return f"{self.kind}:{self.identity}:{suffix}"


@dataclass(frozen=True)
class _Edge:
    """
    Join two topology nodes and optionally represent a complete pathway.
    """

    left: _Node
    right: _Node
    pathway_id: Optional[UUID] = None

    @property
    def key(self) -> tuple[str, str]:
        """
        Return an orientation-independent deterministic identity.
        """
        return _edge_key(self.left, self.right)

    def other(self, node: _Node) -> _Node:
        """
        Return the endpoint opposite ``node``.
        """
        return self.right if node == self.left else self.left


def plan_cable_group_routes(definition: HarnessDefinition) -> tuple[CableGroupRouteLeg, ...]:
    """
    Convert every cable group into unique legs of its minimal topology tree.

    Raises:
        ValueError: If a member is unlocated, members are disconnected, or a
            multi-ended group would branch anywhere other than a junction.
    """
    graph, edges = _topology_graph(definition)
    locations = cable_end_locations(definition)
    pathway_controls = {
        pathway.pathway_id: pathway.ordered_control_ids for pathway in definition.pathways
    }
    junction_controls = {
        junction.junction_id: junction.control_id for junction in definition.junctions
    }
    planned: list[CableGroupRouteLeg] = []
    for group_index, group in enumerate(definition.cable_groups):
        terminal_connections: dict[_Node, UUID] = {}
        for connection_id in group.connection_ids:
            location = locations.get(connection_id)
            if location is None:
                raise ValueError(
                    f"Cable group {group_index + 1} contains an end without a pathway boundary."
                )
            terminal_connections[_boundary_node(*location)] = connection_id
        terminal_nodes = tuple(terminal_connections)
        if len(terminal_nodes) < 2:
            raise ValueError(f"Cable group {group_index + 1} requires at least two ends.")
        tree_edges = _minimal_tree_edges(graph, terminal_nodes, group_index)
        tree_graph = _subgraph(tree_edges)
        _validate_branch_hubs(tree_graph, set(terminal_nodes), group_index)
        internal_terminals = {node for node in terminal_nodes if len(tree_graph.get(node, ())) > 1}
        leaf_terminals = set(terminal_nodes) - internal_terminals
        paths = _maximal_leg_paths(tree_graph, leaf_terminals)
        for leg_index, path in enumerate(paths):
            steps, pathway_ids = _path_controls(path, edges, pathway_controls, junction_controls)
            canonical_path = min(
                "|".join(node.key for node in path),
                "|".join(node.key for node in reversed(path)),
            )
            planned.append(
                CableGroupRouteLeg(
                    route_id=uuid5(group.cable_group_id, canonical_path),
                    cable_group_id=group.cable_group_id,
                    label=f"Group {group_index + 1} Leg {leg_index + 1}",
                    start_connection_id=terminal_connections.get(path[0]),
                    end_connection_id=terminal_connections.get(path[-1]),
                    control_steps=steps,
                    pathway_ids=pathway_ids,
                )
            )
        for lead_index, node in enumerate(sorted(internal_terminals, key=lambda item: item.key)):
            connection_id = terminal_connections[node]
            control_step = _terminal_lead_step(node, pathway_controls, group_index)
            planned.append(
                CableGroupRouteLeg(
                    route_id=uuid5(
                        group.cable_group_id,
                        f"terminal-lead:{node.key}:{connection_id}",
                    ),
                    cable_group_id=group.cable_group_id,
                    label=f"Group {group_index + 1} Leg {len(paths) + lead_index + 1}",
                    start_connection_id=connection_id,
                    end_connection_id=None,
                    control_steps=(control_step,),
                    pathway_ids=(),
                )
            )
    return tuple(planned)


def _boundary_node(pathway_id: UUID, endpoint: PathwayEndpoint) -> _Node:
    """
    Construct one pathway-boundary topology node.
    """
    return _Node("boundary", pathway_id, endpoint)


def _topology_graph(
    definition: HarnessDefinition,
) -> tuple[dict[_Node, list[_Edge]], dict[tuple[str, str], _Edge]]:
    """
    Build the undirected pathway/junction topology used by the Route Editor.
    """
    graph: dict[_Node, list[_Edge]] = {}
    edge_index: dict[tuple[str, str], _Edge] = {}

    def add(edge: _Edge) -> None:
        graph.setdefault(edge.left, []).append(edge)
        graph.setdefault(edge.right, []).append(edge)
        edge_index[edge.key] = edge

    for pathway in definition.pathways:
        add(
            _Edge(
                _boundary_node(pathway.pathway_id, PathwayEndpoint.START),
                _boundary_node(pathway.pathway_id, PathwayEndpoint.END),
                pathway.pathway_id,
            )
        )
    for junction in definition.junctions:
        junction_node = _Node("junction", junction.junction_id)
        graph.setdefault(junction_node, [])
        for relationship in junction.pathway_relationships:
            add(
                _Edge(
                    junction_node,
                    _boundary_node(relationship.pathway_id, relationship.endpoint),
                )
            )
    for adjacent in graph.values():
        adjacent.sort(key=lambda edge: edge.key)
    return graph, edge_index


def _minimal_tree_edges(
    graph: dict[_Node, list[_Edge]],
    terminals: tuple[_Node, ...],
    group_index: int,
) -> tuple[_Edge, ...]:
    """
    Return the union of unique paths from the first terminal to every other.
    """
    root = terminals[0]
    selected: dict[tuple[str, str], _Edge] = {}
    for target in terminals[1:]:
        parents: dict[_Node, tuple[_Node, _Edge]] = {}
        pending = deque([root])
        visited = {root}
        while pending and target not in visited:
            node = pending.popleft()
            for edge in graph.get(node, ()):
                neighbor = edge.other(node)
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                parents[neighbor] = (node, edge)
                pending.append(neighbor)
        if target not in visited:
            raise ValueError(
                f"Cable group {group_index + 1} contains ends in disconnected pathway networks."
            )
        node = target
        while node != root:
            parent, edge = parents[node]
            selected[edge.key] = edge
            node = parent
    return tuple(selected[key] for key in sorted(selected))


def _subgraph(edges: tuple[_Edge, ...]) -> dict[_Node, list[_Edge]]:
    """
    Build adjacency containing only the selected minimal tree.
    """
    graph: dict[_Node, list[_Edge]] = {}
    for edge in edges:
        graph.setdefault(edge.left, []).append(edge)
        graph.setdefault(edge.right, []).append(edge)
    for adjacent in graph.values():
        adjacent.sort(key=lambda candidate: candidate.key)
    return graph


def _validate_branch_hubs(
    graph: dict[_Node, list[_Edge]], terminals: set[_Node], group_index: int
) -> None:
    """
    Require multi-terminal trees to branch only at junction nodes.
    """
    if len(terminals) < 3:
        return
    branch_nodes = [node for node, adjacent in graph.items() if len(adjacent) >= 3]
    if not branch_nodes or any(node.kind != "junction" for node in branch_nodes):
        raise ValueError(
            f"Cable group {group_index + 1} requires junction-centered branching for three or more ends."
        )


def _terminal_lead_step(
    node: _Node,
    pathway_controls: dict[UUID, tuple[UUID, ...]],
    group_index: int,
) -> CableGroupControlStep:
    """
    Return the pathway-end crossing used by one internal terminal lead.
    """
    control_ids = pathway_controls[node.identity]
    if not control_ids:
        raise ValueError(
            f"Cable group {group_index + 1} contains an internal end on a pathway "
            "without a routing control."
        )
    if node.endpoint is PathwayEndpoint.START:
        return CableGroupControlStep(control_ids[0])
    if node.endpoint is PathwayEndpoint.END:
        return CableGroupControlStep(control_ids[-1], True)
    raise ValueError("A cable-group terminal lead must belong to a pathway boundary.")


def _maximal_leg_paths(
    graph: dict[_Node, list[_Edge]], terminals: set[_Node]
) -> tuple[tuple[_Node, ...], ...]:
    """
    Split a tree at terminals and branch junctions without repeating edges.
    """
    stops = {node for node, adjacent in graph.items() if node in terminals or len(adjacent) != 2}
    visited: set[tuple[str, str]] = set()
    paths: list[tuple[_Node, ...]] = []
    for start in sorted(stops, key=lambda node: node.key):
        for first_edge in graph[start]:
            if first_edge.key in visited:
                continue
            visited.add(first_edge.key)
            path = [start, first_edge.other(start)]
            while path[-1] not in stops:
                next_edge = next(edge for edge in graph[path[-1]] if edge.key not in visited)
                visited.add(next_edge.key)
                path.append(next_edge.other(path[-1]))
            paths.append(tuple(path))
    return tuple(paths)


def _path_controls(
    path: tuple[_Node, ...],
    edges: dict[tuple[str, str], _Edge],
    pathway_controls: dict[UUID, tuple[UUID, ...]],
    junction_controls: dict[UUID, UUID],
) -> tuple[tuple[CableGroupControlStep, ...], tuple[UUID, ...]]:
    """
    Expand one topology leg into traversal-ordered controls and pathways.
    """
    steps: list[CableGroupControlStep] = []
    pathway_ids: list[UUID] = []
    for index, node in enumerate(path):
        if node.kind == "junction":
            if index:
                previous = path[index - 1]
                reverse = previous.endpoint is PathwayEndpoint.START
            elif index + 1 < len(path):
                following = path[index + 1]
                reverse = following.endpoint is PathwayEndpoint.END
            else:
                raise ValueError("A routed junction leg must contain an adjacent boundary.")
            steps.append(CableGroupControlStep(junction_controls[node.identity], reverse))
        if index + 1 >= len(path):
            continue
        edge = edges[_edge_key(node, path[index + 1])]
        if edge.pathway_id is None:
            continue
        pathway_ids.append(edge.pathway_id)
        forward = node.endpoint is PathwayEndpoint.START
        control_ids = pathway_controls[edge.pathway_id]
        if not forward:
            control_ids = tuple(reversed(control_ids))
        steps.extend(CableGroupControlStep(control_id, not forward) for control_id in control_ids)
    return tuple(steps), tuple(pathway_ids)


def _edge_key(left: _Node, right: _Node) -> tuple[str, str]:
    """
    Return an orientation-independent key for two topology nodes.
    """
    first, second = sorted((left.key, right.key))
    return first, second
