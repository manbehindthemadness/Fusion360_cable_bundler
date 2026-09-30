"""
Assign persistent ribbon pin numbers to physical end-face positions.
"""

from __future__ import annotations

import math
from uuid import UUID

from .model import CableEndAttachment


def ribbon_pin_number(value: str | None) -> int | None:
    """
    Interpret one saved positive-integer connection pin without guessing labels.
    """
    if value is None:
        return None
    if not value.isascii() or not value.isdecimal() or int(value) < 1:
        raise ValueError("Connection pin numbers must be positive integers.")
    return int(value)


def assign_ribbon_pins(
    attachments: tuple[CableEndAttachment, ...],
    line_centers_mm: tuple[tuple[float, float, float], ...],
    target_centers_mm: dict[UUID, tuple[float, float, float]],
) -> dict[UUID, str]:
    """
    Number unpinned top-level targets once by minimum total distance.

    Numbered connections reserve their exact lines. An unattached placeholder
    consumes capacity but remains unnumbered until a target is available.
    """
    if len(attachments) > len(line_centers_mm):
        raise ValueError("A ribbon end has more top-level connections than lines.")
    occupied: set[int] = set()
    for attachment in attachments:
        number = ribbon_pin_number(attachment.pin_number)
        if number is None:
            continue
        if number > len(line_centers_mm) or number in occupied:
            raise ValueError("Ribbon connection pin numbers must claim distinct existing lines.")
        occupied.add(number)
    pending = tuple(
        item
        for item in attachments
        if item.pin_number is None and item.attachment_id in target_centers_mm
    )
    available = tuple(
        index for index in range(1, len(line_centers_mm) + 1) if index not in occupied
    )
    if len(pending) > len(available):
        raise ValueError("A ribbon end has no free line for a connected target.")
    if not pending:
        return {}
    costs = tuple(
        tuple(
            math.dist(target_centers_mm[item.attachment_id], line_centers_mm[line - 1])
            for line in available
        )
        for item in pending
    )
    # Rectangular shortest augmenting-path assignment; stable input order breaks ties.
    row_count, column_count = len(pending), len(available)
    row_potential = [0.0] * (row_count + 1)
    column_potential = [0.0] * (column_count + 1)
    matched_row = [0] * (column_count + 1)
    predecessor = [0] * (column_count + 1)
    for row in range(1, row_count + 1):
        matched_row[0] = row
        column = 0
        minimum = [math.inf] * (column_count + 1)
        visited = [False] * (column_count + 1)
        while True:
            visited[column] = True
            current_row = matched_row[column]
            delta, next_column = math.inf, 0
            for candidate in range(1, column_count + 1):
                if visited[candidate]:
                    continue
                reduced = (
                    costs[current_row - 1][candidate - 1]
                    - row_potential[current_row]
                    - column_potential[candidate]
                )
                if reduced < minimum[candidate]:
                    minimum[candidate] = reduced
                    predecessor[candidate] = column
                if minimum[candidate] < delta:
                    delta, next_column = minimum[candidate], candidate
            for candidate in range(column_count + 1):
                if visited[candidate]:
                    row_potential[matched_row[candidate]] += delta
                    column_potential[candidate] -= delta
                else:
                    minimum[candidate] -= delta
            column = next_column
            if matched_row[column] == 0:
                break
        while column:
            previous = predecessor[column]
            matched_row[column] = matched_row[previous]
            column = previous
    return {
        pending[row - 1].attachment_id: str(available[column - 1])
        for column, row in enumerate(matched_row)
        if column and row
    }
