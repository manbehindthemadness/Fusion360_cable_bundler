"""
Regressions for palette entity lookup measurement and retention.
"""

from __future__ import annotations

import importlib

from tests.fusion_ui_support import Mock, SimpleNamespace, _PaletteLifecycleModule, pytest


def test_palette_lookup_measurement_counts_fusion_queries_only(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Diagnose distinct host calls without counting snapshot cache reuse as work.
    """
    lookup_type = importlib.import_module(
        "cable_bundler.fusion.ui.palette_geometry"
    ).PaletteEntityLookup
    find_entities = Mock(side_effect=lambda token: (object(),) if token == "present" else ())
    lookup = lookup_type(
        SimpleNamespace(findEntityByToken=find_entities), object(), measure_lookups=True
    )

    assert len(lookup.find_entities("present")) == 1
    assert len(lookup.find_entities("present")) == 1
    assert lookup.find_entities("missing") == ()
    assert lookup.query_count == 2
    assert lookup.empty_count == 1
    assert lookup.cache_hit_count == 1
    assert lookup.query_seconds >= 0.0
    assert find_entities.call_count == 2

    unmeasured = lookup_type(SimpleNamespace(findEntityByToken=find_entities), object())
    assert len(unmeasured.find_entities("present")) == 1
    assert unmeasured.query_count == 0
    assert unmeasured.query_seconds == 0.0


def test_palette_lookup_reuses_valid_entities_across_refreshes(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Avoid repeated native queries while rechecking proxy validity on each snapshot.
    """
    cache = importlib.import_module("cable_bundler.fusion.ui.palette_geometry")
    cache.clear_palette_entity_cache()
    first_entity = SimpleNamespace(isValid=True)
    replacement = SimpleNamespace(isValid=True)
    resolver = Mock(side_effect=[(first_entity,), (replacement,), (), ()])
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(entityToken="design-a"), findEntityByToken=resolver
    )
    try:
        first = cache.PaletteEntityLookup(design, object(), measure_lookups=True)
        assert first.find_entities("linked") == (first_entity,)
        assert first.query_count == 1

        second = cache.PaletteEntityLookup(design, object(), measure_lookups=True)
        assert second.find_entities("linked") == (first_entity,)
        assert second.query_count == 0
        assert second.persistent_hit_count == 1
        assert resolver.call_count == 1

        first_entity.isValid = False
        third = cache.PaletteEntityLookup(design, object(), measure_lookups=True)
        assert third.find_entities("linked") == (replacement,)
        assert third.query_count == 1
        assert third.find_entities("missing") == ()
        assert cache.PaletteEntityLookup(design, object()).find_entities("missing") == ()
        assert resolver.call_count == 4
    finally:
        cache.clear_palette_entity_cache()


def test_palette_lookup_scopes_and_bounds_retained_entities(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Release prior-design proxies and evict old tokens under the capacity limit.
    """
    cache = importlib.import_module("cable_bundler.fusion.ui.palette_geometry")
    cache.clear_palette_entity_cache()
    monkeypatch.setitem(vars(cache), "MAX_PALETTE_ENTITIES", 2)
    first_resolver = Mock(side_effect=lambda _token: (SimpleNamespace(isValid=True),))
    first_design = SimpleNamespace(
        rootComponent=SimpleNamespace(entityToken="design-a"), findEntityByToken=first_resolver
    )
    second_resolver = Mock(side_effect=lambda _token: (SimpleNamespace(isValid=True),))
    second_design = SimpleNamespace(
        rootComponent=SimpleNamespace(entityToken="design-b"), findEntityByToken=second_resolver
    )
    try:
        for token in ("a", "b", "c", "a"):
            cache.PaletteEntityLookup(first_design, object()).find_entities(token)
        assert first_resolver.call_count == 4
        assert len(cache._valid_entities) == 2

        cache.PaletteEntityLookup(second_design, object()).find_entities("a")
        assert second_resolver.call_count == 1
        assert len(cache._valid_entities) == 1
    finally:
        cache.clear_palette_entity_cache()
