"""
Choose sparse overview sections independently of stored inspection resolution.
"""

from __future__ import annotations


def visible_section_indices(count: int, selected: int) -> tuple[int, ...]:
    """
    Show at most nine sections, retaining both ends and the slider's selected sample.

    Replace the nearest interior overview section when inspecting an intermediate
    sample. Recorded geometry and the full slider range remain unchanged.
    """
    if count == 0:
        return ()
    if not 0 <= selected < count:
        raise ValueError("Selected section is outside the recorded samples.")
    if count <= 9:
        return tuple(range(count))
    indices = [round(i * (count - 1) / 8) for i in range(9)]
    if selected not in indices:
        nearest = min(range(1, 8), key=lambda i: abs(indices[i] - selected))
        indices[nearest] = selected
    return tuple(sorted(indices))
