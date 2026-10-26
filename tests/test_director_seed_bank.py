"""
Check generic seed ranking and its independent scalar length projection contract.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, unit
from experiments.experiment_ribbon_cap_transition.director_fields import DirectorField
from experiments.experiment_ribbon_cap_transition.director_rotation_transport import (
    integrate_rotation,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import free_penalties
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.director_seed_bank import (
    NoAdmissibleSeed,
    candidates,
    ranked_seed,
)
from experiments.experiment_ribbon_cap_transition.director_shooting import FREE, field_for, residual
from experiments.experiment_ribbon_cap_transition.director_transport import DirectorPath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _checkpoint() -> None:
    """
    Bound runtime separately in live experiments.
    """


def test_ranked_generic_shape_recovers_scale_without_reference_path_input() -> None:
    """
    Supply only a pose authored from a unit-rotation shape and recover its length.
    """
    field = DirectorField("author", 120, (math.pi / 2, 0, 0, 0), (0.4, -0.4, 0, 0))
    witness = integrate_rotation(field, 64, _checkpoint)
    last = witness.states[-1]
    case = EndpointCase(
        "anonymous",
        Vector3(0, 0, 0),
        Vector3(*last[:3]),
        Vector3(1, 0, 0),
        unit(Vector3(*last[3:6])),
        Vector3(0, 1, 0),
        unit(Vector3(*last[6:9])),
    )

    def build(values: tuple[float, ...]) -> RoutingField:
        """
        Bind only the target and the shared routing coordinate interpretation.
        """
        return field_for(case, values, policy=FREE)

    def score(path: DirectorPath) -> tuple[float, ...]:
        """
        Use named endpoint and current geometry policies without fixture lookup.
        """
        return residual(case, path) + free_penalties(case, path)

    selected, metrics = ranked_seed(case, (), build, score, _checkpoint)
    assert metrics["seed_screenings"] == len(candidates()) == 44
    assert metrics["seed_score"] < 1e-20
    assert abs(build(selected).length_mm - 120) < 1e-9

    def alternate_family(path: DirectorPath) -> bool:
        """
        Exclude the best endpoint seed while leaving different bank shapes available.
        """
        return path.field.ruling[0] < 0

    alternative, filtered = ranked_seed(
        case, (), build, score, _checkpoint, admissibility=alternate_family
    )
    assert alternative != selected
    assert alternate_family(integrate_rotation(build(alternative), 64, _checkpoint))
    assert filtered["seed_score"] > metrics["seed_score"]
    assert filtered["seed_screenings"] == 44
    assert any(not row["admissible"] for row in filtered["seed_ranking"])

    def longer_seed(path: DirectorPath) -> float:
        """
        Require a geometry-authored length floor without changing seed coefficients.
        """
        assert path.field.length_mm > 0
        return 2.0

    _, length_limited = ranked_seed(
        case, (), build, score, _checkpoint, minimum_length_ratio=longer_seed
    )
    assert len(length_limited["seed_ranking"]) == 44
    assert all(2 <= row["length_ratio"] <= 5 for row in length_limited["seed_ranking"])


def test_inadmissible_seed_bank_stops_without_adding_searches() -> None:
    """
    Retain the fixed screening count when no seed meets a caller's geometric filter.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("independent", Vector3(0, 0, 0), Vector3(80, 0, 0), x, x, y, y)
    screened: list[DirectorPath] = []

    def build(values: tuple[float, ...]) -> RoutingField:
        """
        Bind normal routing coordinates to the frozen boundary inputs.
        """
        return field_for(case, values, policy=FREE)

    def score(path: DirectorPath) -> tuple[float, ...]:
        """
        Leave endpoint scores finite so rejection comes only from admissibility.
        """
        return residual(case, path)

    def reject(path: DirectorPath) -> bool:
        """
        Count every screened shape and reject it without changing its geometry.
        """
        screened.append(path)
        return False

    with pytest.raises(NoAdmissibleSeed, match="fixed generic bank") as failure:
        ranked_seed(case, (), build, score, _checkpoint, admissibility=reject)
    assert len(screened) == len(candidates()) == 44
    assert len(failure.value.seed_ranking) == 44
    assert all(not row["admissible"] for row in failure.value.seed_ranking)

    def exceeds_domain(path: DirectorPath) -> float:
        """
        Expose geometric seed requirements outside the original length search range.
        """
        assert path.field.length_mm > 0
        return 6.0

    with pytest.raises(NoAdmissibleSeed) as too_long:
        ranked_seed(case, (), build, score, _checkpoint, minimum_length_ratio=exceeds_domain)
    assert len(too_long.value.seed_ranking) == 44
    assert all(row["minimum_length_ratio"] == 6 for row in too_long.value.seed_ranking)
