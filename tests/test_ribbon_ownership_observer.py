"""
Preserve original native coverage decisions and failures while retaining their exact bookkeeping.
"""

from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_native_ownership.observer import Observer
from tests.test_ribbon_native_correspondence import _collection, _cover


def test_real_coverage_failure_is_unchanged_and_original_map_is_detached() -> None:
    """
    Retain a demonstrated uncovered fifth face without new inversions, acceptance or exception transport.
    """
    mapping, _ = _collection(extra=True)
    mapping.body.revisionId = "original-body"
    _cover(mapping)
    queries = mapping.queries, mapping.distance_queries
    observed = Observer(type(mapping).seal_surfaces)
    with pytest.raises(RuntimeError, match="Uncovered native faces"):
        with observed:
            mapping.seal_surfaces()
    assert sys.getprofile() is None and observed.calls == 1 and len(observed.failures) == 1
    assert (mapping.queries, mapping.distance_queries) == queries and not mapping.sealed
    payload = observed.payload()["failures"][0]
    assert payload["body_revision"] == "original-body"
    assert payload["owners"] == [[0, 0], [1, 1]] and payload["unowned"] == [2, 3, 4]
    assert payload["regions"] == [[0], [0], [1], [], []]
    mapping.owners[4] = 0
    mapping.members[0].add(4)
    assert observed.payload()["failures"][0] == payload


def test_successful_seal_retains_no_failed_mapping_and_does_not_change_query_work() -> None:
    """
    Observe the original successful cap correspondence while leaving later physical checks untouched.
    """
    mapping, _ = _collection()
    _cover(mapping)
    control, _ = _collection()
    _cover(control)
    control.seal_surfaces()
    with Observer(type(mapping).seal_surfaces) as observed:
        mapping.seal_surfaces()
    assert mapping.sealed and observed.calls == 1 and not observed.failures
    assert mapping.owners == control.owners and mapping.members == control.members
    assert (mapping.queries, mapping.distance_queries) == (
        control.queries,
        control.distance_queries,
    )


def test_unrelated_exception_propagates_without_becoming_a_coverage_failure() -> None:
    """
    The observer never swallows original source, cancellation or host errors.
    """
    mapping, _ = _collection()
    error = InterruptedError("original source guard")
    observed = Observer(type(mapping).seal_surfaces)
    with pytest.raises(InterruptedError) as caught:
        with observed:
            raise error
    assert caught.value is error and observed.calls == 0 and not observed.failures
    assert sys.getprofile() is None


def test_existing_profiler_and_reused_lease_are_refused_without_displacing_them() -> None:
    """
    Preserve debugger or caller instrumentation and prevent accidental repeated diagnostic execution.
    """
    mapping, _ = _collection()
    observed = Observer(type(mapping).seal_surfaces)
    other = Mock()
    previous = sys.getprofile()
    try:
        sys.setprofile(other)
        with pytest.raises(RuntimeError, match="existing profiler"):
            with observed:
                pytest.fail("must not enter")
        assert sys.getprofile() is other
    finally:
        sys.setprofile(previous)
    with observed:
        pass
    with pytest.raises(RuntimeError, match="unused lease"):
        with observed:
            pytest.fail("must not reenter")


def test_unexpected_profile_replacement_is_preserved_and_reported() -> None:
    """
    A stolen lease is a harness error rather than permission to remove another profiler.
    """
    mapping, _ = _collection()
    other = Mock()
    previous = sys.getprofile()
    try:
        with pytest.raises(RuntimeError, match="lease changed"):
            with Observer(type(mapping).seal_surfaces):
                sys.setprofile(other)
        assert sys.getprofile() is other
    finally:
        sys.setprofile(previous)


def test_failed_record_limit_is_visible_without_changing_original_rejections() -> None:
    """
    Unexpected repeated checks cannot create an unbounded evidence list or hide the original failure.
    """
    mapping, _ = _collection(extra=True)
    _cover(mapping)
    with Observer(type(mapping).seal_surfaces) as observed:
        for _ in range(3):
            with pytest.raises(RuntimeError, match="Uncovered native faces"):
                mapping.seal_surfaces()
        with pytest.raises(RuntimeError, match="only after"):
            observed.payload()
    assert observed.calls == 3 and len(observed.failures) == 2 and observed.overflow


def test_non_python_observation_target_rejects_before_installation() -> None:
    """
    Refuse a native builtin without a Python frame instead of silently observing nothing.
    """
    with pytest.raises(ValueError, match="Python seal"):
        Observer(sys.setprofile)
    assert sys.getprofile() is None
