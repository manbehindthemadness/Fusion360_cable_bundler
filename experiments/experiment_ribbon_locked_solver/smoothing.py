"""
Apply the shared optional aesthetic sequence under one explicit material-length allowance.
"""

from __future__ import annotations

from typing import Any, Callable

from experiments.experiment_ribbon_aesthetic.layout_solve import ease as ease_layout
from experiments.experiment_ribbon_aesthetic.merge import merge
from experiments.experiment_ribbon_aesthetic.solve import ease as ease_radii
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


def smooth(
    first: FoldRoute,
    percent: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, dict[str, str]]:
    """
    Preserve the original radius/merge/layout/merge ordering; zero performs no work.
    """
    if not percent:
        return first, {"smoothing": "disabled"}
    fraction = percent / 100
    maximum_length = first.material_length_mm * (1 + fraction)
    final, radius = ease_radii(first, fraction, checkpoint, record)
    final, before = merge(final, maximum_length, checkpoint, record)
    final, layout = ease_layout(final, maximum_length, checkpoint, record)
    final, after = merge(final, maximum_length, checkpoint, record)
    return final, {
        "radius_easing": radius,
        "merge_before": before,
        "layout_easing": layout,
        "merge_after": after,
    }
