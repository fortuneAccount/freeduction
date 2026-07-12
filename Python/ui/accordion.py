from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QStackedWidget, QToolButton,
    QSizePolicy, QLabel
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, pyqtSlot
from PyQt6.QtGui import QPainter


class _BlankPage(QWidget):
    """Empty widget used as page 0 of the animation target QStackedWidget.
    When Fusion's backing store fails to clear, this gives the compositor
    a clean, zero-content surface to blit instead of a stale buffer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.eraseRect(self.rect())
        painter.end()


class AccordionSection(QWidget):
    # Large sentinel value used as "uncapped" maximum height
    EXPANDED_MAX = 16777215  # Qt's QWIDGETSIZE_MAX

    def __init__(self, title: str, content: QWidget, animation_duration=200,
                 start_expanded=False, qlementine_style: bool = False,
                 max_height: int = None):
        """
        Args:
            title:            Header label text.
            content:          Widget shown in the collapsible area.
            animation_duration: Expand/collapse animation time in milliseconds.
            start_expanded:   Whether the section starts open.
            qlementine_style: When True, applies Qlementine-compatible toggle
                              button styling (suppressed menu-indicator, rounded
                              border, bold header).  When False (default) the
                              existing appearance is preserved unchanged.
            max_height:       Optional maximum height when expanded. If None, uses EXPANDED_MAX.
        """
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._max_height = max_height if max_height is not None else self.EXPANDED_MAX

        # ---- widget attributes that break Fusion's paint-cache behaviour ----
        # Forces a complete redrawing of the background canvas on every
        # geometry update.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        # Breaks Fusion's optimisation that skips redrawing overlapping child
        # boundaries.
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        # Ensures that layout margin recalculations force a global window
        # redraw step.
        self.setAttribute(Qt.WidgetAttribute.WA_LayoutOnResize, True)

        self.toggle_button = QToolButton(text=title, checkable=True, checked=start_expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle_button.clicked.connect(self.toggle)

        if qlementine_style:
            self._apply_qlementine_style()

        # ---- animation target: QStackedWidget with blank + content pages ----
        # Page 0: blank surface that Fusion can blit cleanly when the backing
        #          store fails to clear stale buffer content.
        # Page 1: the actual content widget.
        # The QStackedWidget itself carries the same widget attributes so its
        # own surface is always repainted from scratch.
        self._stack = QStackedWidget()
        self._stack.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._stack.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self._stack.setAttribute(Qt.WidgetAttribute.WA_LayoutOnResize, True)

        self._blank_page = _BlankPage()
        self._stack.addWidget(self._blank_page)   # index 0
        self._stack.addWidget(content)             # index 1
        self._stack.setCurrentIndex(1 if start_expanded else 0)

        initial_height = self._max_height if start_expanded else 0
        self._stack.setMaximumHeight(initial_height)

        self.animation = QPropertyAnimation(self._stack, b"maximumHeight")
        self.animation.setDuration(animation_duration)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.valueChanged.connect(self._on_animation_frame)

        # Keep content_height for backward compatibility with external code that reads/writes it.
        self.content_height = content.sizeHint().height()

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self._stack)

    def _apply_qlementine_style(self) -> None:
        """Apply Qlementine-compatible styling to the toggle button.

        Suppresses the default QToolButton menu indicator, adds a rounded
        border, left-aligned bold text, and reserves space for a caret arrow
        via left padding.  The animation and sibling-collapse logic are not
        affected.
        """
        self.toggle_button.setObjectName("qlementineAccordionToggle")
        self.toggle_button.setStyleSheet(
            "QToolButton#qlementineAccordionToggle {"
            "    border: none;"
            "    border-radius: 4px;"
            "    padding: 4px 8px 4px 22px;"
            "    text-align: left;"
            "    font-weight: 600;"
            "}"
            "QToolButton#qlementineAccordionToggle::menu-indicator { image: none; width: 0px; }"
        )

    # ------------------------------------------------------------------
    # Fusion paint-cache purge
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        """Override to force Fusion to drop its visual cache and repaint
        the viewport surface from scratch.  Without this, Fusion's
        aggressive layout-reuse optimisation leaves stale glyph fragments
        when children resize during animation frames."""
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        painter.eraseRect(event.rect())
        painter.end()
        super().paintEvent(event)

    @pyqtSlot()
    def _on_animation_frame(self):
        """Called on every animation value change.  Forces child widgets to
        clean themselves up and prompts the parent layout to re-synchronise
        so Fusion cannot cache stale geometry."""
        for child in self._stack.findChildren(QWidget):
            child.update()
        parent_layout = self.parent().layout() if self.parent() else None
        if parent_layout is not None:
            parent_layout.activate()
        QTimer.singleShot(0, self._deferred_sync)

    def _deferred_sync(self):
        """Asynchronous layout pass that runs after the current event loop
        iteration finishes, ensuring the underlying layout engine fully
        synchronises before the next frame is painted."""
        if self.parent() is not None:
            self.parent().updateGeometry()
            self.parent().update()
        self.updateGeometry()
        self.update()

    @pyqtSlot()
    def toggle(self):
        checked = self.toggle_button.isChecked()

        # If opening this section, close other sibling AccordionSection instances
        if checked:
            parent_widget = self.parent()
            if parent_widget is not None:
                try:
                    for sibling in parent_widget.findChildren(AccordionSection):
                        if sibling is not self and sibling.toggle_button.isChecked():
                            sibling.toggle_button.setChecked(False)
                            sibling.toggle()
                except Exception:
                    pass

        start_height = self._stack.maximumHeight()
        end_height = self._max_height if checked else 0

        # Switch to blank page while collapsed so Fusion blits a clean surface.
        self._stack.setCurrentIndex(1 if checked else 0)

        self.animation.stop()
        self.animation.setStartValue(start_height)
        self.animation.setEndValue(end_height)
        self.animation.start()


class AccordionMenu(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        for i in range(3):
            content_widget = self.create_section_content(i)
            section = AccordionSection(f"Section {i + 1}", content_widget)
            layout.addWidget(section)

        layout.addStretch(1)

    def create_section_content(self, index: int) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for j in range(3):
            content_layout.addWidget(QLabel(f"Item {index + 1}.{j + 1}"))
        content_layout.addStretch(1)
        return content


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Animated Accordion Menu - Qt6")
    layout = QVBoxLayout(window)

    accordion = AccordionMenu()
    layout.addWidget(accordion)

    window.resize(300, 400)
    window.show()
    sys.exit(app.exec())
