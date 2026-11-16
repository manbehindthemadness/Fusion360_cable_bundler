"""
Check whole-graph material ancestry, including cycles that a leaf-only walk would omit.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from experiments.experiment_ribbon_complete.topology import terminal_chains
from tests.test_ribbon_complete_lengths import checkpoint, forked_plan


@pytest.mark.parametrize("fault", ("cycle", "missing_parent", "connection", "root"))
def test_invalid_material_ancestry_is_not_dropped_or_repaired(fault: str) -> None:
    """
    Original order and root/end identity remain authoritative even when other valid terminal chains exist.
    """
    plan = forked_plan()
    branches = list(plan.branches)
    index = next(i for i, b in enumerate(branches) if b.attachment.attachment_id == UUID(int=90000))
    child = branches[index]
    if fault == "cycle":
        other_index = next(
            i for i, b in enumerate(branches) if b.attachment.attachment_id == UUID(int=90001)
        )
        other = branches[other_index]
        branches[index] = replace(
            child,
            attachment=replace(
                child.attachment, parent_attachment_id=other.attachment.attachment_id
            ),
        )
        branches[other_index] = replace(
            other,
            attachment=replace(
                other.attachment, parent_attachment_id=child.attachment.attachment_id
            ),
        )
    elif fault == "missing_parent":
        branches[index] = replace(
            child, attachment=replace(child.attachment, parent_attachment_id=UUID(int=999999))
        )
    elif fault == "connection":
        branches[index] = replace(
            child,
            source=replace(
                child.source,
                leg=replace(child.source.leg, start_connection_id=plan.group.connection_ids[1]),
            ),
        )
    else:
        branches[index] = replace(child, root_attachment_id=UUID(int=999999))
    with pytest.raises(ValueError):
        terminal_chains(tuple(branches), checkpoint)
