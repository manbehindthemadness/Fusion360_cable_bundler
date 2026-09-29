"""
Cache Fusion token lookups within one palette-state snapshot.
"""

from __future__ import annotations

from typing import Any, Optional

# noinspection PyUnresolvedReferences
import adsk.fusion


class PaletteEntityLookup:
    """
    Resolve each entity token once while constructing one transient UI snapshot.

    The cache is discarded after serialization, so later model edits always query
    Fusion again and cannot inherit stale link status from an earlier command.
    """

    def __init__(self, design: Optional[adsk.fusion.Design], gateway: Any) -> None:
        """
        Retain the current design and the non-design fallback gateway.
        """
        self._design = design
        self._gateway = gateway
        self._entities: dict[str, tuple[object, ...]] = {}
        self._fallback_status: dict[str, bool] = {}

    def find_entities(self, token: str) -> tuple[object, ...]:
        """
        Return all Fusion entities matching a token, querying at most once.
        """
        if self._design is None or not token.strip():
            return ()
        if token not in self._entities:
            self._entities[token] = tuple(self._design.findEntityByToken(token) or ())
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
