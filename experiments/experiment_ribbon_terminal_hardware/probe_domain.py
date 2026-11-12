"""
Bind negative-only hardware inspection to explicit material of one immutable route.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .model import Terminal


@dataclass(frozen=True)
class ProbeDomain:
    """
    Select unique original terminal/member pairs without granting clearance to unmeasured material.

    Order may prioritize a previously involved terminal. A completed subset
    without a strict occupied-point witness is still unresolved, not clear.
    """

    source: FoldRoute
    pairs: tuple[tuple[Terminal, int], ...]

    def __post_init__(self) -> None:
        """
        Reject guessed, repeated or absent member identities before consuming hardware work.
        """
        if (
            not isinstance(self.pairs, tuple)
            or not self.pairs
            or any(
                not isinstance(pair, tuple)
                or len(pair) != 2
                or not isinstance(pair[0], Terminal)
                or type(pair[1]) is not int
                or not 0 <= pair[1] < len(self.source.pieces)
                for pair in self.pairs
            )
            or len(set(self.pairs)) != len(self.pairs)
        ):
            raise ValueError(
                "Use unique existing terminal/material pairs for a negative-only probe"
            )

    @property
    def terminals(self) -> tuple[Terminal, ...]:
        """
        Preserve the first occurrence of each explicitly selected terminal.
        """
        return tuple(dict.fromkeys(terminal for terminal, _ in self.pairs))

    def members(self, terminal: Terminal) -> tuple[int, ...]:
        """
        Keep original piece identities and declared order for this terminal only.
        """
        return tuple(index for selected, index in self.pairs if selected is terminal)
