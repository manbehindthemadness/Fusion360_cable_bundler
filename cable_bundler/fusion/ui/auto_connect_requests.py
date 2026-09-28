"""
Carry Auto Connect picker choices and apply options across Fusion commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class AutoConnectPickRequest:
    """
    Identify one ending picker without authorizing an edit.
    """

    harness_id: UUID
    side: str
    request_id: str
    document: object


@dataclass(frozen=True)
class AutoConnectApplyRequest:
    """
    Retain both contact selections and ending choices for one explicit apply.
    """

    harness_id: UUID
    interface_id: UUID
    contact_ids: tuple[UUID, ...]
    connection_id: UUID
    parent_attachment_id: Optional[UUID]
    include_pins: bool
    include_values: bool
    diameter_mm: Optional[float]
    document: object
    target_interface_id: Optional[UUID] = None
    target_contact_ids: tuple[UUID, ...] = ()
    target_connection_id: Optional[UUID] = None
    target_parent_attachment_id: Optional[UUID] = None
    target_include_pins: bool = True
    target_include_values: bool = True
    target_diameter_mm: Optional[float] = None
