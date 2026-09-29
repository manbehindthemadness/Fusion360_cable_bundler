"""
Cache live Fusion token identities across palette-state snapshots.
"""

from __future__ import annotations

from collections import OrderedDict
from time import perf_counter
from typing import Any, Optional

# noinspection PyUnresolvedReferences
import adsk.fusion

MAX_PALETTE_ENTITIES = 512
MAX_ENTITIES_PER_TOKEN = 16
_valid_entities: OrderedDict[str, tuple[object, ...]] = OrderedDict()
_design_key = ""


def clear_palette_entity_cache() -> None:
    """
    Release retained native proxies when the add-in or document changes.
    """
    global _design_key
    _valid_entities.clear()
    _design_key = ""


def _cache_active(design: adsk.fusion.Design) -> bool:
    """
    Scope retained proxies to one design without retaining its wrapper.
    """
    global _design_key
    try:
        key = getattr(design.rootComponent, "entityToken", "")
    except (AttributeError, RuntimeError):
        key = ""
    if not isinstance(key, str) or not key:
        clear_palette_entity_cache()
        return False
    if key != _design_key:
        clear_palette_entity_cache()
        _design_key = key
    return True


def _cached_entities(token: str) -> Optional[tuple[object, ...]]:
    """
    Reuse only live native proxies; a deleted entity must be resolved afresh.
    """
    entities = _valid_entities.get(token)
    if entities is None:
        return None
    try:
        valid = all(entity.isValid for entity in entities)
    except (AttributeError, RuntimeError):
        valid = False
    if not valid:
        _valid_entities.pop(token, None)
        return None
    _valid_entities.move_to_end(token)
    return entities


def _remember_entities(token: str, entities: tuple[object, ...]) -> None:
    """
    Retain only bounded positive results, leaving missing tokens re-queryable.
    """
    if not entities or len(entities) > MAX_ENTITIES_PER_TOKEN:
        return
    _valid_entities[token] = entities
    _valid_entities.move_to_end(token)
    while len(_valid_entities) > MAX_PALETTE_ENTITIES:
        _valid_entities.popitem(last=False)


class PaletteEntityLookup:
    """
    Resolve each entity token once while constructing one transient UI snapshot.

    A snapshot also reuses bounded valid proxies from earlier palette refreshes.
    Missing or invalid entities are always queried again.
    """

    def __init__(
        self,
        design: Optional[adsk.fusion.Design],
        gateway: Any,
        *,
        measure_lookups: bool = False,
    ) -> None:
        """
        Retain the current design and the non-design fallback gateway.
        """
        self._design = design
        self._gateway = gateway
        self._reuse_allowed = _cache_active(design) if design is not None else False
        self._entities: dict[str, tuple[object, ...]] = {}
        self._fallback_status: dict[str, bool] = {}
        self._measure_lookups = measure_lookups
        self.query_count = 0
        self.empty_count = 0
        self.cache_hit_count = 0
        self.persistent_hit_count = 0
        self.query_seconds = 0.0

    def find_entities(self, token: str) -> tuple[object, ...]:
        """
        Return all Fusion entities matching a token, querying at most once.
        """
        if self._design is None or not token.strip():
            return ()
        if token in self._entities:
            if self._measure_lookups:
                self.cache_hit_count += 1
            return self._entities[token]
        cached = _cached_entities(token) if self._reuse_allowed else None
        if cached is not None:
            if self._measure_lookups:
                self.persistent_hit_count += 1
            self._entities[token] = cached
            return cached
        if self._measure_lookups:
            started = perf_counter()
        entities = tuple(self._design.findEntityByToken(token) or ())
        if self._measure_lookups:
            self.query_seconds += perf_counter() - started
            self.query_count += 1
            self.empty_count += not entities
        self._entities[token] = entities
        if self._reuse_allowed:
            _remember_entities(token, entities)
        return self._entities[token]

    def is_resolvable(self, token: str) -> bool:
        """
        Report linked geometry using the same snapshot cache as typed targets.
        """
        if self._design is not None:
            return bool(self.find_entities(token))
        if token not in self._fallback_status:
            self._fallback_status[token] = self._gateway.is_entity_token_resolvable(token)
        return self._fallback_status[token]
