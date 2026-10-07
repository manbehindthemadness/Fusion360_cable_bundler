"""
Reject changed replay inputs before resolving any Fusion Path references.
"""

from types import SimpleNamespace

import pytest

from experiments.experiment_ribbon_cap_transition.section_warp_trial import imposed_flex
from experiments.experiment_ribbon_cap_transition.straight_twist import twist_frames
from experiments.experiment_ribbon_cap_transition.warp_replay import retained_path


def _collection(items: list[SimpleNamespace]) -> SimpleNamespace:
    """
    Present native collection access without loading the unavailable Fusion host.
    """
    return SimpleNamespace(count=len(items), item=items.__getitem__)


class _Arcs(list[SimpleNamespace]):
    """
    Provide the count property used by native sketch collections.
    """

    @property
    def count(self) -> int:
        """
        Report retained topology without modifying collection contents.
        """
        return len(self)


class _Evaluator:
    """
    Supply five identical finite samples for a zero-warp replay guard.
    """

    def getParameterExtents(self) -> tuple[bool, float, float]:
        """
        Report a fixed source parameter interval.
        """
        return True, 0.0, 1.0

    def getPointAtParameter(self, _parameter: float) -> tuple[bool, SimpleNamespace]:
        """
        Return origin; no native entity is created or required.
        """
        return True, SimpleNamespace(x=0.0, y=0.0, z=0.0)


@pytest.mark.parametrize("failure", ("topology", "moved_fit_point"))
def test_replay_rejects_changed_geometry_before_path_creation(failure: str) -> None:
    """
    No Fusion import/reference operation is reached on invalid retained inputs.
    """
    arcs = _Arcs(
        [SimpleNamespace(geometry=SimpleNamespace(evaluator=_Evaluator())) for _ in range(42)]
    )
    count = 41 if failure == "topology" else 42
    point = SimpleNamespace(worldGeometry=SimpleNamespace(x=0.001, y=0.0, z=0.0))
    splines = _collection(
        [SimpleNamespace(fitPoints=_collection([point] * 5)) for _ in range(count)]
    )
    sketch = SimpleNamespace(
        name="Three-anchor flex section 02",
        sketchCurves=SimpleNamespace(sketchFittedSplines=splines),
    )
    component = SimpleNamespace(sketches=[sketch])
    source = SimpleNamespace(
        sketchCurves=SimpleNamespace(sketchArcs=arcs), sketchToModelSpace=lambda value: value
    )
    frame = twist_frames(360)[0]
    flex = imposed_flex(frame, (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), 0)
    with pytest.raises(RuntimeError, match="topology changed|fit points differ"):
        retained_path(component, source, SimpleNamespace(), frame, flex, 2)
