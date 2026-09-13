"""
Fusion UI services for support.
"""

from __future__ import annotations

import traceback

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .. import FusionHarnessGateway
from .constants import COMMAND_NAME


def _report_failure(operation: str) -> None:
    """
    Report a lifecycle failure at the Fusion host boundary.
    """
    application = adsk.core.Application.get()
    if application and application.userInterface:
        application.userInterface.messageBox(
            f"Wire Bundler failed to {operation}:\n{traceback.format_exc()}",
            COMMAND_NAME,
        )


def _log_to_fusion(message: str) -> None:
    """
    Write a diagnostic message to Fusion's application log.
    """
    adsk.core.Application.log(
        message,
        adsk.core.LogLevels.InfoLogLevel,
        adsk.core.LogTypes.FileLogType,
    )


def _require_active_design(application: adsk.core.Application) -> adsk.fusion.Design:
    """
    Return the active Fusion design or report the missing host context.
    """
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Harness Builder requires an active Fusion design.")
    return design


def _create_harness_gateway(application: adsk.core.Application) -> FusionHarnessGateway:
    """
    Create a gateway for the active Fusion design and cloud folder.

    Raises:
        RuntimeError: If no Fusion design is active.
    """
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Harness Builder requires an active Fusion design.")
    return FusionHarnessGateway(design, application.data.activeFolder)
