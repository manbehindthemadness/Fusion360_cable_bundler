"""
Retain spatial-inspector compatibility imports for the shared embedded-palette layout policy.
"""

from devtools.ribbon_analysis.palette_layout import LayoutIncoming as LayoutIncoming
from devtools.ribbon_analysis.palette_layout import refresh as refresh
from devtools.ribbon_analysis.palette_layout import show as show

__all__ = ["LayoutIncoming", "refresh", "show"]
