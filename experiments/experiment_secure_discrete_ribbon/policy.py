"""
Separate ordinary validation from explicitly requested diagnostic construction.
"""

from __future__ import annotations

from enum import Enum


class ExperimentPolicy(Enum):
    """
    Retain failures and attempt rejected inputs only in the diagnostic scratch.
    """

    VALIDATE = "validate"
    OBSERVE = "observe_and_retain"


def exception_chain(error: BaseException) -> list[str]:
    """
    Preserve native kernel causes otherwise hidden by the builder's wrapper.
    """
    messages: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
    return messages
