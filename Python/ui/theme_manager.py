"""
Theme manager for freeduction UI theming system.

Provides a pluggable provider abstraction over optional third-party Qt theme
libraries (qfluentwidgets, qdarktheme, qdarkstyle) and the Qlementine style
(PyQt6-Qlementine pip package). Falls back to the default Qt appearance when
libraries are unavailable or fail to apply.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_theme_file(filename: str) -> str | None:
    """Return the absolute path to a bundled theme JSON file, or None."""
    try:
        from Python import constants  # type: ignore[import]
        app_root = constants.APP_ROOT_DIR
    except Exception:
        app_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    path = os.path.join(app_root, "assets", "themes", filename)
    return path if os.path.isfile(path) else None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ThemeProvider(ABC):
    """Abstract base class for all theme providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name for this theme."""
        ...

    @property
    def requires_restart(self) -> bool:
        """Return True if the theme only takes full effect after a restart."""
        return False

    @abstractmethod
    def apply(self, app) -> None:
        """Apply this theme to the given QApplication instance."""
        ...

    @classmethod
    def is_available(cls) -> bool:
        """Return True if the backing library can be imported."""
        return True


# ---------------------------------------------------------------------------
# Default provider
# ---------------------------------------------------------------------------

class DefaultProvider(ThemeProvider):
    """Clears any applied stylesheet and restores the standard Qt palette."""

    @property
    def name(self) -> str:
        return "Default (Qt)"

    def apply(self, app) -> None:
        app.setStyleSheet("")
        app.setPalette(app.style().standardPalette())

    @classmethod
    def is_available(cls) -> bool:
        return True


# ---------------------------------------------------------------------------
# Fluent providers (qfluentwidgets)
# ---------------------------------------------------------------------------

class FluentDarkProvider(ThemeProvider):
    """Applies the Fluent Dark theme via qfluentwidgets and qdarktheme stylesheet."""

    @property
    def name(self) -> str:
        return "Fluent Dark"

    def apply(self, app) -> None:
        from qfluentwidgets import setTheme, Theme  # type: ignore[import]
        import qdarktheme  # type: ignore[import]
        setTheme(Theme.DARK)
        app.setStyleSheet(qdarktheme.load_stylesheet("dark"))

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qfluentwidgets") is not None and importlib.util.find_spec("qdarktheme") is not None


class FluentLightProvider(ThemeProvider):
    """Applies the Fluent Light theme via qfluentwidgets and qdarktheme stylesheet."""

    @property
    def name(self) -> str:
        return "Fluent Light"

    def apply(self, app) -> None:
        from qfluentwidgets import setTheme, Theme  # type: ignore[import]
        import qdarktheme  # type: ignore[import]
        setTheme(Theme.LIGHT)
        app.setStyleSheet(qdarktheme.load_stylesheet("light"))

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qfluentwidgets") is not None and importlib.util.find_spec("qdarktheme") is not None


# ---------------------------------------------------------------------------
# qt-dark-theme providers (qdarktheme)
# ---------------------------------------------------------------------------

class QtDarkThemeDarkProvider(ThemeProvider):
    """Applies the dark variant via qdarktheme."""

    @property
    def name(self) -> str:
        return "Dark Theme (Dark)"

    @property
    def requires_restart(self) -> bool:
        return False

    def apply(self, app) -> None:
        import qdarktheme  # type: ignore[import]
        if hasattr(qdarktheme, "setup_theme"):
            qdarktheme.setup_theme("dark")
        else:
            app.setStyleSheet(qdarktheme.load_stylesheet("dark"))

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qdarktheme") is not None


class QtDarkThemeLightProvider(ThemeProvider):
    """Applies the light variant via qdarktheme."""

    @property
    def name(self) -> str:
        return "Dark Theme (Light)"

    @property
    def requires_restart(self) -> bool:
        return False

    def apply(self, app) -> None:
        import qdarktheme  # type: ignore[import]
        if hasattr(qdarktheme, "setup_theme"):
            qdarktheme.setup_theme("light")
        else:
            app.setStyleSheet(qdarktheme.load_stylesheet("light"))

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qdarktheme") is not None


# ---------------------------------------------------------------------------
# QDarkStyleSheet provider (qdarkstyle)
# ---------------------------------------------------------------------------

class QDarkStyleProvider(ThemeProvider):
    """Applies the QDarkStyleSheet via qdarkstyle."""

    @property
    def name(self) -> str:
        return "QDarkStyleSheet"

    @property
    def requires_restart(self) -> bool:
        return False

    def apply(self, app) -> None:
        import qdarkstyle  # type: ignore[import]
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt6"))

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qdarkstyle") is not None


# ---------------------------------------------------------------------------
# Qlementine providers  (PyQt6-Qlementine pip package)
# ---------------------------------------------------------------------------

class _QlementineProviderBase(ThemeProvider):
    """
    Shared base for Qlementine dark and light providers.

    Uses the PyQt6-Qlementine package (import PyQt6Qlementine).
    Availability is checked via importlib so the app starts without the
    package installed.

    The bundled theme JSON files live at:
        assets/themes/qlementine_dark.json
        assets/themes/qlementine_light.json
    """

    # Theme JSON filename — overridden in subclasses.
    _theme_file: str = ""

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("PyQt6Qlementine") is not None

    def _apply_style(self, app) -> None:
        """Instantiate QlementineStyle, load the bundled theme, and apply it."""
        from PyQt6Qlementine import QlementineStyle, Theme  # type: ignore[import]
        from PyQt6.QtCore import QJsonDocument  # type: ignore[import]

        # Create style and set it on the application.
        style = QlementineStyle(app)
        app.setStyle(style)

        # Load the theme JSON and apply it.
        theme_path = _get_theme_file(self._theme_file)
        if theme_path:
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                doc = QJsonDocument.fromVariant(raw)
                theme = Theme.fromJsonDoc(doc)
                style.setTheme(theme)
                logger.info("Applied Qlementine theme from %s", theme_path)
            except Exception as exc:
                logger.warning("Failed to load Qlementine theme %s: %s", theme_path, exc)
        else:
            logger.warning(
                "Qlementine theme file not found: %s — using default theme.", self._theme_file
            )

        # Re-apply configured font so it takes priority over Qlementine's default.
        try:
            from PyQt6.QtGui import QFont  # type: ignore[import]
            config = getattr(app, "_freeduction_config", None)
            if config is not None:
                font_family = getattr(config, "ui_font_family", "")
                font_size = getattr(config, "ui_font_size", 9)
                if font_family:
                    app.setFont(QFont(font_family, font_size))
        except Exception as exc:
            logger.debug("Could not re-apply font after Qlementine apply: %s", exc)


class QlementineDarkProvider(_QlementineProviderBase):
    """Applies Qlementine with the bundled dark theme."""

    _theme_file = "qlementine_dark.json"

    @property
    def name(self) -> str:
        return "Qlementine (Dark)"

    def apply(self, app) -> None:
        self._apply_style(app)


class QlementineLightProvider(_QlementineProviderBase):
    """Applies Qlementine with the bundled light theme."""

    _theme_file = "qlementine_light.json"

    @property
    def name(self) -> str:
        return "Qlementine (Light)"

    def apply(self, app) -> None:
        self._apply_style(app)


# ---------------------------------------------------------------------------
# ThemeManager
# ---------------------------------------------------------------------------

class ThemeManager:
    """
    Manages theme providers and applies themes to the running QApplication.

    The active theme identifier is stored externally in AppConfig; this class
    is stateless between calls beyond holding the provider registry.

    Qlementine (qlementine_dark / qlementine_light) is listed first when the
    plugin DLL is present on the system.
    """

    # Qlementine IDs are prepended so they appear at the top of the selector.
    THEME_IDS: list[str] = [
        "qlementine_dark",
        "qlementine_light",
        "default",
        "fluent_dark",
        "fluent_light",
        "qdarktheme_dark",
        "qdarktheme_light",
        "qdarkstyle",
    ]

    def __init__(self) -> None:
        self._registry: dict[str, ThemeProvider] = {
            "qlementine_dark": QlementineDarkProvider(),
            "qlementine_light": QlementineLightProvider(),
            "default": DefaultProvider(),
            "fluent_dark": FluentDarkProvider(),
            "fluent_light": FluentLightProvider(),
            "qdarktheme_dark": QtDarkThemeDarkProvider(),
            "qdarktheme_light": QtDarkThemeLightProvider(),
            "qdarkstyle": QDarkStyleProvider(),
        }

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def list_available_themes(self) -> list[tuple[str, str]]:
        """Return (theme_id, display_name) pairs for all available themes.

        "default" is always included regardless of installed libraries.
        Qlementine entries appear first when the plugin is present.
        """
        result: list[tuple[str, str]] = []
        for theme_id in self.THEME_IDS:
            provider = self._registry.get(theme_id)
            if provider is not None and provider.is_available():
                result.append((theme_id, provider.name))
        return result

    def is_theme_available(self, theme_id: str) -> bool:
        """Return True if the given theme ID is registered and its library is available."""
        provider = self._registry.get(theme_id)
        return provider is not None and provider.is_available()

    # ------------------------------------------------------------------
    # Apply helpers
    # ------------------------------------------------------------------

    def apply_theme(self, theme_id: str, app, config=None) -> bool:
        """Apply the theme identified by *theme_id* to *app*.

        Returns True if a restart is required for the theme to take full
        effect, False otherwise.

        Falls back to the default theme on any error (unknown ID, unavailable
        library, or exception from the provider).

        If *config* is provided it is attached to the app instance so that
        Qlementine providers can re-apply font settings after loading the style.
        """
        # Guard: QApplication must exist
        if app is None:
            logger.warning("apply_theme called with no QApplication instance; skipping.")
            return False

        # Attach config to app for font re-application inside providers.
        if config is not None:
            try:
                app._freeduction_config = config
            except Exception:
                pass

        provider = self._registry.get(theme_id)

        if provider is None:
            logger.warning("Unknown theme ID %r; falling back to default.", theme_id)
            provider = self._registry["default"]

        if not provider.is_available():
            logger.warning(
                "Theme %r is not available (library missing); falling back to default.",
                theme_id,
            )
            provider = self._registry["default"]

        try:
            provider.apply(app)
        except Exception:
            logger.exception(
                "Error applying theme %r; falling back to default.", theme_id
            )
            try:
                self._registry["default"].apply(app)
            except Exception:
                logger.exception("Error applying default theme fallback.")
            return False

        try:
            app.processEvents()
        except Exception:
            logger.warning("app.processEvents() failed after applying theme %r.", theme_id)

        return provider.requires_restart

    def apply_theme_from_config(self, config, app) -> None:
        """Read ui_theme from *config* and apply it to *app*.

        Falls back to the default theme on any error.
        """
        if app is None:
            logger.warning(
                "apply_theme_from_config called with no QApplication instance; skipping."
            )
            return

        try:
            theme_id = getattr(config, "ui_theme", "default") or "default"
            self.apply_theme(theme_id, app, config=config)
        except Exception:
            logger.exception(
                "Unexpected error in apply_theme_from_config; falling back to default."
            )
            try:
                self._registry["default"].apply(app)
            except Exception:
                logger.exception("Error applying default theme in fallback path.")


# ---------------------------------------------------------------------------
# UICapabilityManager
# ---------------------------------------------------------------------------

_QLEMENTINE_THEME_IDS: frozenset[str] = frozenset({"qlementine_dark", "qlementine_light"})

# QSS fragment applied at the QApplication level when Qlementine is active to
# give tooltips a rounded, modern look consistent with the Qlementine style.
_QLEMENTINE_TOOLTIP_QSS = """
QToolTip {
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 6px 10px;
    background-color: palette(base);
    color: palette(text);
    font-size: 13px;
}
"""

# QSS applied to QToolButton inside AccordionSection when Qlementine is active.
# Suppresses the default indicator and uses a simple arrow-style caret.
_QLEMENTINE_ACCORDION_QSS = """
QToolButton {
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    text-align: left;
    font-weight: 600;
}
QToolButton::menu-indicator { image: none; width: 0px; }
QToolButton[checked="true"]  { padding-left: 22px; }
QToolButton[checked="false"] { padding-left: 22px; }
"""


class UICapabilityManager:
    """
    Lightweight, QApplication-free component that exposes boolean capability
    flags indicating which enhanced widget variants are available under the
    current theme.

    All flags are True only when a Qlementine theme is active; otherwise they
    are all False, leaving every widget in its existing fallback state.

    Usage::

        caps = UICapabilityManager.from_config(config)
        if caps.has_qlementine_navigation:
            # configure QTabWidget for native Qlementine nav bar
            ...
    """

    def __init__(self, theme_id: str) -> None:
        is_qlementine = theme_id in _QLEMENTINE_THEME_IDS
        self.has_qlementine_navigation: bool = is_qlementine
        self.has_qlementine_accordion: bool = is_qlementine
        self.has_qlementine_toggles: bool = is_qlementine
        self.has_qlementine_popovers: bool = is_qlementine

    @classmethod
    def from_config(cls, config) -> "UICapabilityManager":
        """Construct a UICapabilityManager from an AppConfig instance.

        Safe to call before a QApplication exists.  Any error in reading
        config returns a fully-fallback (all-False) instance.
        """
        try:
            theme_id = getattr(config, "ui_theme", "") or ""
        except Exception:
            theme_id = ""
        return cls(theme_id)
