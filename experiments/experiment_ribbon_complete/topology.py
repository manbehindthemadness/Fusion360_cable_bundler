"""
Share explicit serial attachment traversal without assigning geometry or physical feasibility.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from .contracts import BranchPlan, IncompleteRibbonInput


def ancestry(
    terminal: BranchPlan, branches: dict[UUID, BranchPlan], checkpoint: Callable[[], None]
) -> tuple[BranchPlan, ...]:
    """
    Walk terminal-to-root order, rejecting cycles, missing parents and changed end/conductor identity.
    """
    result = []
    seen: set[UUID] = set()
    current = terminal
    while True:
        checkpoint()
        identity = current.attachment.attachment_id
        if (
            identity in seen
            or current.conductor != terminal.conductor
            or current.root_attachment_id != terminal.root_attachment_id
            or current.source.leg.start_connection_id != terminal.source.leg.start_connection_id
        ):
            raise IncompleteRibbonInput(
                "An end chain changed conductor/connection or contains a cycle"
            )
        seen.add(identity)
        result.append(current)
        parent = current.attachment.parent_attachment_id
        if parent is None:
            if identity != terminal.root_attachment_id:
                raise IncompleteRibbonInput("An end chain differs from its declared root identity")
            return tuple(result)
        if parent not in branches or branches[parent].attachment.attachment_id != parent:
            raise IncompleteRibbonInput("An end chain is missing its parent")
        current = branches[parent]


def terminal_chains(
    branches: tuple[BranchPlan, ...], checkpoint: Callable[[], None]
) -> tuple[tuple[BranchPlan, ...], ...]:
    """
    Preserve alternative-terminal order and require every branch to belong to a validated chain.

    A cycle disconnected from all leaves must not disappear from accounting.
    Each returned chain is ordered terminal-to-root; siblings remain alternatives.
    """
    checkpoint()
    nodes = {b.attachment.attachment_id: b for b in branches}
    if not branches or len(nodes) != len(branches):
        raise IncompleteRibbonInput("Unique complete attachment identities are required")
    parents = {b.attachment.parent_attachment_id for b in branches}
    leaves = tuple(b for b in branches if b.attachment.attachment_id not in parents)
    chains = tuple(ancestry(b, nodes, checkpoint) for b in leaves)
    visited = {b.attachment.attachment_id for chain in chains for b in chain}
    if visited != set(nodes):
        raise IncompleteRibbonInput(
            "An attachment cycle or unreachable branch is absent from all terminal chains"
        )
    return chains
