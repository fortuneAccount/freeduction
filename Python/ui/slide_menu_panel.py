"""Reusable collapsible slide-menu navigation panel.

Wraps ``Custom_Widgets.QCustomSlideMenu`` (the pyqt-custom-widgets slide menu)
in a two-pane layout: a collapsible navigation rail on the left and a
``QStackedWidget`` content pane on the right. Sections are added with
``add_section``; each one gets a checkable nav button and a content page, and
clicking a button switches the visible page.

Intended as a drop-in replacement for a column of ``AccordionSection`` widgets::

    panel = SlideMenuPanel()
    panel.add_section("SOURCES", sources_widget,
                      icon=section_icon("folder"))
    panel.add_section("PATHS", paths_widget,
                      icon=section_icon("folder_arrow"))
    panel.set_current_index(1)
    some_layout.addWidget(panel)

Each section gets a nav button carrying a unique icon. Icons are recolored to
pure black or white (monochrome) so they stay theme-neutral, and when the rail
is expanded the icon+label are left-aligned in the button. When the rail is
collapsed the label is hidden but the icon stays visible (centered), giving an
icon-only navigation strip.

Icons come from ``section_icon(name)``, which draws bold filled silhouettes
(folder, play, database, ...) with QPainter. These stay legible at small sizes
and under light themes, unlike Qt's fine-detail standard pixmaps. Call
``refresh_icon_colors()`` after the theme changes so the black/white recolor
follows the new background.

The section's content page also paints the section icon at 8% opacity in the
bottom-right corner as a faint background watermark.

The stock ``QCustomSlideMenu`` re-expands itself on every ``showEvent``, which
is wrong inside a tabbed UI (switching tabs re-shows the page and would
silently undo a collapsed state). ``_PersistentSlideMenu`` overrides that
behaviour so the open/collapsed state is driven only by the user and this
panel.
"""

from PyQt6.QtCore import Qt, QEasingCurve, QRect, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from Custom_Widgets.QCustomSlideMenu import QCustomSlideMenu


# ---------------------------------------------------------------------------
# Bold silhouette icons
# ---------------------------------------------------------------------------
# Qt's QStyle.StandardPixmap glyphs are fine-detail line art that becomes
# illegible at nav-rail size, especially on light backgrounds. These icons are
# drawn from scratch as bold filled shapes so they read clearly at any theme.

_ICON_DRAWS: "dict[str, object]" = {}
_ICON_CACHE: "dict[str, QIcon]" = {}


def _register_icon(name: str, draw):
    """Register a ``draw(painter, size)`` function as a named section icon."""
    _ICON_DRAWS[name] = draw
    _ICON_CACHE.pop(name, None)


def _silhouette_icon(name: str) -> QIcon:
    """Render the named icon as a bold black silhouette pixmap."""
    cached = _ICON_CACHE.get(name)
    if cached is not None:
        return cached
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0))
    _ICON_DRAWS[name](painter, float(size))
    painter.end()
    icon = QIcon(pixmap)
    _ICON_CACHE[name] = icon
    return icon


def section_icon(name: str) -> QIcon:
    """Return the bold monochrome silhouette icon for *name*.

    Names: ``folder``, ``folder_arrow``, ``play``, ``sliders``, ``monitor``,
    ``database``, ``save``, ``info``. The returned icon is a black silhouette;
    the slide panel recolors it to black or white to match the rail.
    """
    if name not in _ICON_DRAWS:
        return QIcon()
    return _silhouette_icon(name)


def _paint_silhouette(painter: QPainter, s: float) -> None:
    """Start a filled-shape paint (black brush, no pen)."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0))


def _erase(painter: QPainter, rect: QRectF) -> None:
    """Punch a transparent hole out of an already-drawn silhouette."""
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    painter.setBrush(QColor(0, 0, 0, 0))
    painter.drawRect(rect)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.setBrush(QColor(0, 0, 0))


def _draw_folder(painter: QPainter, s: float) -> None:
    _paint_silhouette(painter, s)
    path = QPainterPath()
    path.moveTo(0.10 * s, 0.30 * s)
    path.lineTo(0.36 * s, 0.30 * s)
    path.lineTo(0.44 * s, 0.42 * s)
    path.lineTo(0.90 * s, 0.42 * s)
    path.lineTo(0.90 * s, 0.76 * s)
    path.lineTo(0.10 * s, 0.76 * s)
    path.closeSubpath()
    painter.drawPath(path)


def _draw_folder_arrow(painter: QPainter, s: float) -> None:
    _draw_folder(painter, s)
    path = QPainterPath()
    path.moveTo(0.34 * s, 0.44 * s)
    path.lineTo(0.34 * s, 0.74 * s)
    path.lineTo(0.68 * s, 0.59 * s)
    path.closeSubpath()
    painter.drawPath(path)


def _draw_play(painter: QPainter, s: float) -> None:
    _paint_silhouette(painter, s)
    path = QPainterPath()
    path.moveTo(0.28 * s, 0.16 * s)
    path.lineTo(0.82 * s, 0.50 * s)
    path.lineTo(0.28 * s, 0.84 * s)
    path.closeSubpath()
    painter.drawPath(path)


def _draw_sliders(painter: QPainter, s: float) -> None:
    _paint_silhouette(painter, s)
    for y, knob_x in ((0.20, 0.42), (0.50, 0.60), (0.80, 0.30)):
        painter.drawRect(QRectF(0.12 * s, y * s - 0.05 * s, 0.60 * s, 0.10 * s))
        painter.drawEllipse(QRectF(knob_x * s - 0.10 * s, y * s - 0.10 * s, 0.20 * s, 0.20 * s))


def _draw_monitor(painter: QPainter, s: float) -> None:
    _paint_silhouette(painter, s)
    painter.drawRect(QRectF(0.14 * s, 0.18 * s, 0.72 * s, 0.52 * s))
    _erase(painter, QRectF(0.24 * s, 0.27 * s, 0.52 * s, 0.34 * s))
    painter.drawRect(QRectF(0.44 * s, 0.70 * s, 0.12 * s, 0.14 * s))
    painter.drawRect(QRectF(0.32 * s, 0.84 * s, 0.36 * s, 0.08 * s))


def _draw_database(painter: QPainter, s: float) -> None:
    _paint_silhouette(painter, s)
    painter.drawRect(QRectF(0.20 * s, 0.30 * s, 0.60 * s, 0.40 * s))
    painter.drawEllipse(QRectF(0.20 * s, 0.18 * s, 0.60 * s, 0.24 * s))
    painter.drawEllipse(QRectF(0.20 * s, 0.58 * s, 0.60 * s, 0.24 * s))


def _draw_save(painter: QPainter, s: float) -> None:
    _paint_silhouette(painter, s)
    painter.drawRect(QRectF(0.22 * s, 0.16 * s, 0.56 * s, 0.68 * s))
    _erase(painter, QRectF(0.30 * s, 0.16 * s, 0.40 * s, 0.26 * s))
    painter.drawRect(QRectF(0.40 * s, 0.62 * s, 0.20 * s, 0.22 * s))


def _draw_info(painter: QPainter, s: float) -> None:
    _paint_silhouette(painter, s)
    painter.drawEllipse(QRectF(0.16 * s, 0.16 * s, 0.68 * s, 0.68 * s))
    _erase(painter, QRectF(0.27 * s, 0.27 * s, 0.46 * s, 0.46 * s))
    painter.drawRect(QRectF(0.455 * s, 0.36 * s, 0.09 * s, 0.09 * s))
    painter.drawRect(QRectF(0.455 * s, 0.50 * s, 0.09 * s, 0.20 * s))


for _name, _draw in (
    ("folder", _draw_folder),
    ("folder_arrow", _draw_folder_arrow),
    ("play", _draw_play),
    ("sliders", _draw_sliders),
    ("monitor", _draw_monitor),
    ("database", _draw_database),
    ("save", _draw_save),
    ("info", _draw_info),
):
    _register_icon(_name, _draw)


def _monochrome(icon: QIcon, color: QColor, size: int = 32) -> QIcon:
    """Recolor ``icon`` to a single ``color``, preserving its alpha mask.

    The result is a pure black-and-white silhouette of the source icon (no
    colour hues), ready for use on either a light (black) or dark (white)
    background depending on the ``color`` chosen.
    """
    if icon.isNull():
        return QIcon()
    pixmap = icon.pixmap(QSize(size, size))
    if pixmap.isNull():
        return QIcon()
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(image.rect(), color)
    painter.end()
    return QIcon(QPixmap.fromImage(image))


class _WatermarkOverlay(QWidget):
    """Full-page overlay painting the section icon at 8% opacity.

    Sits on top of the section content (bottom-right corner) but is transparent
    to mouse events, so the watermark stays faintly visible over any content
    while the section remains fully interactive.
    """

    _OPACITY = 0.08
    _INSET = 16

    def __init__(self, icon: QIcon, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._icon = icon
        self._pixmap: "QPixmap | None" = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_icon(self, icon: QIcon) -> None:
        self._icon = icon
        self._pixmap = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._icon.isNull():
            return
        size = min(max(72, min(self.width(), self.height()) // 4), 200)
        if self._pixmap is None or self._pixmap.width() != size:
            source = self._icon.pixmap(QSize(size, size))
            if source.isNull():
                return
            # QIcon.pixmap() never upscales past the icon's native size, so
            # smooth-scale explicitly to the target watermark size.
            image = source.toImage().scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._pixmap = QPixmap.fromImage(image)
        painter = QPainter(self)
        painter.setOpacity(self._OPACITY)
        painter.drawPixmap(
            QRect(self.width() - size - self._INSET,
                  self.height() - size - self._INSET,
                  size, size),
            self._pixmap,
        )
        painter.end()


class _WatermarkPage(QWidget):
    """Stacked page hosting one section's widget with a faint watermark.

    The section widget is made background-transparent and a full-page
    ``_WatermarkOverlay`` paints the section icon at 8% opacity in the
    bottom-right corner. Because the overlay ignores mouse input, the section
    remains fully interactive and the icon is only a faint visual watermark.
    """

    def __init__(self, icon: QIcon, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._overlay = _WatermarkOverlay(icon, self)

    def set_content(self, widget: QWidget) -> None:
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        widget.setAutoFillBackground(False)
        self._layout.addWidget(widget)
        self._overlay.raise_()

    def set_icon(self, icon: QIcon) -> None:
        self._overlay.set_icon(icon)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()


class _PersistentSlideMenu(QCustomSlideMenu):
    """QCustomSlideMenu that does not force a re-expand on every show."""

    def showEvent(self, event):
        # Deliberately a no-op: the layout/geometry drive sizing and the
        # open/collapsed state is user-controlled rather than reset on re-show.
        pass


class SlideMenuPanel(QWidget):
    """Collapsible left navigation rail with a right-hand content pane."""

    sectionChanged = pyqtSignal(int)

    # Fallback icons when a caller does not supply one for a section. Each
    # section index maps to a distinct bold silhouette so a panel built without
    # explicit icons still gets one unique, legible icon per section.
    _DEFAULT_ICON_NAMES: tuple[str, ...] = (
        "folder",
        "folder_arrow",
        "play",
        "sliders",
        "monitor",
        "database",
        "save",
        "info",
    )

    def __init__(
        self,
        parent: "QWidget | None" = None,
        *,
        nav_width: int = 220,
        collapsed_width: int = 48,
        icon_size: int = 22,
        expand_duration: int = 220,
        collapse_duration: int = 168,
        easing: QEasingCurve.Type = QEasingCurve.Type.InBack,
    ) -> None:
        super().__init__(parent)
        self.nav_width = nav_width
        self.collapsed_width = collapsed_width
        self.icon_size = icon_size

        self._sections: list[tuple[str, QPushButton, _WatermarkPage]] = []
        self._current_index = -1
        self._button_texts: dict[QPushButton, str] = {}
        self._collapsed = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # --- Left: navigation rail -------------------------------------
        self.slide_menu = _PersistentSlideMenu(self)
        self.slide_menu.setObjectName("slideMenuRail")
        self.slide_menu.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        self._nav_layout = QVBoxLayout(self.slide_menu)
        self._nav_layout.setContentsMargins(4, 4, 4, 4)
        self._nav_layout.setSpacing(4)

        self.toggle_button = QPushButton("«", self.slide_menu)
        self.toggle_button.setObjectName("slideMenuToggleButton")
        self.toggle_button.setFixedHeight(26)
        self.toggle_button.setToolTip("Collapse menu")
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setAutoDefault(False)
        self.toggle_button.clicked.connect(self.slide_menu.slideMenu)
        self._nav_layout.addWidget(self.toggle_button)
        self._nav_layout.addSpacing(2)
        self._nav_layout.addStretch(1)

        self._button_group = QButtonGroup(self.slide_menu)
        self._button_group.setExclusive(True)

        self.slide_menu.onExpanded.connect(self._on_expanded)
        self.slide_menu.onCollapsed.connect(self._on_collapsed)

        # Set the expanded/collapsed geometry BEFORE the widget is shown and
        # let it begin in the expanded state. Animations run to the configured
        # widths, so the rail ends up fixed at nav_width / collapsed_width.
        self.slide_menu.customizeQCustomSlideMenu(
            defaultWidth=nav_width,
            defaultHeight="parent",
            collapsedWidth=collapsed_width,
            collapsedHeight="parent",
            expandedWidth=nav_width,
            expandedHeight="parent",
            update=False,
        )
        self.set_animation_profile(
            expand_duration=expand_duration,
            collapse_duration=collapse_duration,
            easing=easing,
        )

        outer.addWidget(self.slide_menu)

        # --- Right: content pane ---------------------------------------
        self.content = QStackedWidget(self)
        self.content.setObjectName("slideMenuContent")
        outer.addWidget(self.content, 1)

    # -- Section management ----------------------------------------------

    def add_section(
        self,
        title: str,
        widget: QWidget,
        *,
        icon: "QIcon | None" = None,
        checked: bool = False,
    ) -> int:
        """Append a section (``title`` + ``widget``); return its index.

        The section appears in the rail as a checkable button (with ``icon``,
        falling back to a distinct standard icon per index) and in the content
        pane as a stacked page. If ``checked`` is True the new section becomes
        the current one.
        """
        index = self.content.count()
        button = QPushButton(title, self.slide_menu)
        button.setObjectName("slideMenuNavButton")
        button.setCheckable(True)
        button.setFixedHeight(34)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoDefault(False)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setToolTip(title)
        if icon is None:
            icon = self._default_icon(index)
        mono_icon = icon
        if not icon.isNull():
            mono_icon = _monochrome(icon, self._resolve_icon_color())
            button.setIcon(mono_icon)
            button.setIconSize(QSize(self.icon_size, self.icon_size))
        button.clicked.connect(lambda _=False, i=index: self.set_current_index(i))
        self._button_group.addButton(button)
        self._button_texts[button] = title

        self._nav_layout.insertWidget(self._nav_layout.count() - 1, button)

        page = _WatermarkPage(mono_icon)
        page.set_content(widget)
        self.content.addWidget(page)

        self._apply_button_alignment(button)
        self._sections.append((title, button, page))
        if checked:
            self.set_current_index(index)
        return index

    def _default_icon(self, index: int) -> QIcon:
        """Distinct bold silhouette icon for the section at ``index`` (fallback)."""
        name = self._DEFAULT_ICON_NAMES[index % len(self._DEFAULT_ICON_NAMES)]
        return section_icon(name)

    def _resolve_icon_color(self) -> QColor:
        """Black or white, whichever contrasts with the rail's background.

        Keeps the section icons strictly black & white while remaining visible
        under both light and dark themes.
        """
        try:
            background = self.slide_menu.palette().color(QPalette.ColorRole.Window)
        except Exception:
            background = QColor(0, 0, 0)
        return QColor(0, 0, 0) if background.lightnessF() > 0.5 else QColor(255, 255, 255)

    def refresh_icon_colors(self) -> None:
        """Recolor every section icon for the current rail background.

        Call after the theme changes at runtime; otherwise the black/white icon
        recolor computed at build time goes stale and can leave white icons on
        a light rail (illegible).
        """
        color = self._resolve_icon_color()
        for _, button, page in self._sections:
            icon = button.icon()
            if icon.isNull():
                continue
            mono_icon = _monochrome(icon, color)
            button.setIcon(mono_icon)
            page.set_icon(mono_icon)

    def _apply_button_alignment(self, button: QPushButton) -> None:
        """Left-align icon+label when expanded; center the icon when collapsed."""
        if self._collapsed:
            button.setStyleSheet("text-align: center; padding: 0px;")
        else:
            button.setStyleSheet("text-align: left; padding-left: 8px;")

    def set_current_index(self, index: int) -> None:
        """Show the section at ``index`` and check its nav button."""
        if not 0 <= index < self.content.count():
            return
        if index == self._current_index:
            return
        self._current_index = index
        self._sections[index][1].setChecked(True)
        self.content.setCurrentIndex(index)
        self.sectionChanged.emit(index)

    def current_index(self) -> int:
        """Index of the currently visible section (``-1`` if none)."""
        return self._current_index

    # -- Open/collapse control -------------------------------------------

    def set_animation_profile(
        self,
        *,
        expand_duration: int = 220,
        collapse_duration: int = 168,
        easing: QEasingCurve.Type = QEasingCurve.Type.InBack,
    ) -> None:
        """Configure the rail's open/collapse animation timing and easing.

        ``expand_duration`` / ``collapse_duration`` are in milliseconds and
        *easing* is the ``QEasingCurve`` type applied to both directions.
        The change takes effect the next time the rail animates.
        """
        self.slide_menu._expandingAnimationDuration = int(expand_duration)
        self.slide_menu._collapsingAnimationDuration = int(collapse_duration)
        self.slide_menu._expandingAnimationEasingCurve = easing
        self.slide_menu._collapsingAnimationEasingCurve = easing

    def expand(self) -> None:
        """Animate the rail to its expanded width."""
        self.slide_menu.expandMenu()

    def collapse(self) -> None:
        """Animate the rail to its collapsed width."""
        self.slide_menu.collapseMenu()

    def toggle(self) -> None:
        """Toggle the rail between expanded and collapsed."""
        self.slide_menu.slideMenu()

    def is_collapsed(self) -> bool:
        """True when the rail is currently collapsed."""
        return self._collapsed

    # -- Internal slots ----------------------------------------------------

    def _on_expanded(self) -> None:
        self._collapsed = False
        self.toggle_button.setText("«")
        self.toggle_button.setToolTip("Collapse menu")
        for button, text in self._button_texts.items():
            button.setText(text)
            self._apply_button_alignment(button)

    def _on_collapsed(self) -> None:
        self._collapsed = True
        self.toggle_button.setText("»")
        self.toggle_button.setToolTip("Expand menu")
        for button in self._button_texts:
            button.setText("")
            self._apply_button_alignment(button)
