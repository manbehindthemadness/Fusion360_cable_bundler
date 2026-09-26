"""
Guard palette reads during Fusion document transitions.
"""

from __future__ import annotations

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .palette_state import _contact_palette_document_scope
from .payloads import _read_palette_payload

_CONTACT_SCOPED_READS = frozenset(
    (
        "get_interface_contact_signatures",
        "get_interface_contacts_cached",
        "get_interface_contacts",
        "get_interface_contact_cache_status",
        "rebuild_interface_contacts_cache",
    )
)


def _stale_palette_document_request(
    application: adsk.core.Application, action: str, data: str
) -> bool:
    """
    Ignore queued reads from a closing or different Fusion document.

    An absent activeProduct attribute belongs only to lightweight test doubles;
    a real Fusion application always exposes it, even during document closure.
    """
    if action != "get_state" and action not in _CONTACT_SCOPED_READS:
        return False
    try:
        document = application.activeDocument
    except AttributeError:
        pass
    except (RuntimeError, TypeError):
        return True
    else:
        if document is None:
            return True
    try:
        active_product = application.activeProduct
    except AttributeError:
        return False
    except (RuntimeError, TypeError):
        return True
    try:
        design = adsk.fusion.Design.cast(active_product)
    except (AttributeError, RuntimeError, TypeError):
        return True
    if design is None:
        return True
    if action == "get_state":
        return False
    scope = _read_palette_payload(data).get("contactDocumentScope")
    if not isinstance(scope, str) or not scope:
        return False  # A palette loaded before this field existed.
    try:
        return scope != _contact_palette_document_scope(application, design)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return True
