"""
Theme manager for freeduction UI theming system.

Provides a pluggable provider abstraction over optional third-party Qt theme
libraries (qfluentwidgets, qdarktheme, qdarkstyle). Falls back to the default
Qt appearance when libraries are unavailable or fail to apply.
"""

from __future__ import annotations

import importlib.util
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


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
    """Applies the Fluent Dark theme via qfluentwidgets."""

    @property
    def name(self) -> str:
        return "Fluent Dark"

    def apply(self, app) -> None:
        from qfluentwidgets import setTheme, Theme  # type: ignore[import]
        setTheme(Theme.DARK)

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qfluentwidgets") is not None


class FluentLightProvider(ThemeProvider):
    """Applies the Fluent Light theme via qfluentwidgets."""

    @property
    def name(self) -> str:
        return "Fluent Light"

    def apply(self, app) -> None:
        from qfluentwidgets import setTheme, Theme  # type: ignore[import]
        setTheme(Theme.LIGHT)

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qfluentwidgets") is not None


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
# ThemeManager
# ---------------------------------------------------------------------------

class ThemeManager:
    """
    Manages theme providers and applies themes to the running QApplication.

    The active theme identifier is stored externally in AppConfig; this class
    is stateless between calls beyond holding the provider registry.
    """

    THEME_IDS: list[str] = [
        "default",
        "fluent_dark",
        "fluent_light",
        "qdarktheme_dark",
        "qdarktheme_light",
        "qdarkstyle",
    ]

    def __init__(self) -> None:
        self._registry: dict[str, ThemeProvider] = {
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

    def apply_theme(self, theme_id: str, app) -> bool:
        """Apply the theme identified by *theme_id* to *app*.

        Returns True if a restart is required for the theme to take full
        effect, False otherwise.

        Falls back to the default theme on any error (unknown ID, unavailable
        library, or exception from the provider).
        """
        # Guard: QApplication must exist
        if app is None:
            logger.warning("apply_theme called with no QApplication instance; skipping.")
            return False

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
            self.apply_theme(theme_id, app)
        except Exception:
            logger.exception(
                "Unexpected error in apply_theme_from_config; falling back to default."
            )
            try:
                self._registry["default"].apply(app)
            except Exception:
                logger.exception("Error applying default theme in fallback path.")
