"""
Focused Fusion UI regressions for palette.
"""

from __future__ import annotations

from tests.fusion_ui_support import (
    Mock,
    SimpleNamespace,
    _PaletteLifecycleModule,
    pytest,
    sys,
)


def test_palette_is_shown_during_command_creation(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Show the palette immediately when Fusion creates the input-free command.
    """
    shown_applications: list[object] = []
    application = object()
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        addin_module,
        "_show_palette",
        shown_applications.append,
    )

    created_handler = addin_module._ShowPaletteCreatedHandler()
    created_handler.notify(SimpleNamespace(command=object()))

    assert shown_applications == [application]


def test_palette_opens_at_relationship_graphic_working_size(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Give the editor enough initial room for its connection-map labels and controls.
    """
    palette = SimpleNamespace(
        incomingFromHTML=SimpleNamespace(add=Mock(return_value=True)),
        navigatingURL=SimpleNamespace(add=Mock(return_value=True)),
        htmlFileURL="palette.html",
    )
    palettes = SimpleNamespace(
        itemById=Mock(return_value=None),
        add=Mock(return_value=palette),
    )
    application = SimpleNamespace(userInterface=SimpleNamespace(palettes=palettes))
    monkeypatch.setattr(addin_module, "_send_palette_state", lambda _application: None)
    monkeypatch.setattr(addin_module, "_log_to_fusion", lambda _message: None)

    addin_module._show_palette(application)

    assert palettes.add.call_args.args[6:8] == (840, 760)
    assert palettes.add.call_args.args[3] is False
    assert palette.isDockedInCanvas is True
    assert palette.dockingOption == "vertical"
    assert palette.dockingState == "right"
    assert palette.isVisible is True


def test_existing_palette_is_redocked_and_revealed(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Recover a floating palette that macOS moved outside Fusion's fullscreen Space.
    """
    palette = SimpleNamespace(dockingState="floating", isVisible=True)
    palettes = SimpleNamespace(itemById=Mock(return_value=palette))
    application = SimpleNamespace(userInterface=SimpleNamespace(palettes=palettes))
    monkeypatch.setattr(addin_module, "_send_palette_state", lambda _application: None)

    addin_module._show_palette(application)

    assert palette.isDockedInCanvas is True
    assert palette.dockingState == "right"
    assert palette.dockingOption == "vertical"
    assert palette.isVisible is True


def test_palette_remains_usable_when_fusion_rejects_redocking(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reveal and refresh an existing palette when Fusion rejects area placement.
    """

    class _Palette:
        """
        Reproduce Fusion's docking-state assignment failure.
        """

        def __init__(self) -> None:
            """
            Start hidden with no docking option assigned.
            """
            self.dockingOption = None
            self.isVisible = False

        # noinspection PyPep8Naming
        @property
        def dockingState(self) -> str:
            """
            Return the current floating state.
            """
            return "floating"

        # noinspection PyPep8Naming
        @dockingState.setter
        def dockingState(self, _value: str) -> None:
            """
            Reproduce Fusion's internal area-placement rejection.
            """
            raise RuntimeError("InternalValidationError: setAreaPlacement")

    palette = _Palette()
    application = SimpleNamespace(
        userInterface=SimpleNamespace(palettes=SimpleNamespace(itemById=Mock(return_value=palette)))
    )
    sent = Mock()
    logged: list[str] = []
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    monkeypatch.setattr(addin_module, "_log_to_fusion", logged.append)

    addin_module._show_palette(application)

    assert palette.isVisible
    sent.assert_called_once_with(application)
    assert logged == [
        "Harness Builder could not restore right docking: InternalValidationError: setAreaPlacement"
    ]
