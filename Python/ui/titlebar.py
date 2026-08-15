"""Custom frameless-window title bar with window controls and a close-button
context menu.

The title bar replaces the native caption for ``Qt.WindowType.FramelessWindowHint``
windows. It provides:

* a title label (with the window icon) that drags the window around,
* double-click-to-maximize / restore on the empty area,
* minimize / maximize / close buttons,
* a right-click context menu on the close button exposing:
    - ``On Top``  -- toggle the always-on-top hint,
    - ``Kill $exe_path`` -- kill the executable of the currently selected
      Editor row (``$exe_path`` resolves to ``<directory>\\<name>``),
    - ``Shrink``  -- toggle a compact strip-sized window (restores on toggle).

Styling is theme-neutral: it uses ``palette(...)`` QSS roles so it reads
correctly under light and dark themes.
"""

import os
import subprocess

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from Python import constants

_TITLEBAR_QSS = """
QWidget#titleBar {
    background-color: palette(window);
    border-bottom: 1px solid palette(mid);
}
QLabel#titleBarTitle {
    color: palette(text);
    font-weight: 600;
}
QPushButton#titleBarButton {
    background-color: transparent;
    border: none;
    color: palette(text);
    font-family: "Segoe MDL2 Assets", "Segoe UI Symbol", "Segoe UI";
    font-size: 11pt;
}
QPushButton#titleBarButton:hover {
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
QPushButton#titleBarButton:pressed {
    background-color: palette(dark);
}
QPushButton#titleBarCloseButton:hover {
    background-color: #e81123;
    color: #ffffff;
}
"""


class TitleBar(QWidget):
    """Draggable, clickable custom title bar for a frameless main window."""

    HEIGHT = 34
    BUTTON_WIDTH = 46

    def __init__(self, window: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(self.HEIGHT)
        self.setStyleSheet(_TITLEBAR_QSS)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._window = window
        self._drag_offset = None
        self._dragging = False
        self._shrunk = False
        self._saved_geometry = None
        self._saved_min_size = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        self.icon_label.setPixmap(self._window.windowIcon().pixmap(18, 18))
        layout.addWidget(self.icon_label)
        layout.addSpacing(6)

        self.title_label = QLabel(self._window.windowTitle())
        self.title_label.setObjectName("titleBarTitle")
        layout.addWidget(self.title_label, 1)

        layout.addSpacing(6)

        self.min_button = self._make_button("—", "Minimize")
        self.max_button = self._make_button("□", "Maximize")
        self.close_button = self._make_button("✕", "Close")
        self.close_button.setObjectName("titleBarCloseButton")

        self.min_button.clicked.connect(self._minimize)
        self.max_button.clicked.connect(self._toggle_maximize)
        self.close_button.clicked.connect(self._window.close)
        self.close_button.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.close_button.customContextMenuRequested.connect(self._show_close_menu)

        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

        self._update_max_button()

    def _make_button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("titleBarButton")
        button.setFixedSize(self.BUTTON_WIDTH, self.HEIGHT)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAutoDefault(False)
        return button

    # ------------------------------------------------------------------
    # Window control slots
    # ------------------------------------------------------------------

    def _minimize(self) -> None:
        self._window.showMinimized()

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self._update_max_button()

    def _update_max_button(self) -> None:
        maximized = self._window.isMaximized()
        self.max_button.setText("❐" if maximized else "□")
        self.max_button.setToolTip("Restore" if maximized else "Maximize")

    def _is_on_top(self) -> bool:
        return bool(self._window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def _toggle_on_top(self) -> None:
        on_top = not self._is_on_top()
        self._window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        self._window.show()

    def _is_shrunk(self) -> bool:
        return self._shrunk

    def _toggle_shrink(self) -> None:
        if self._shrunk:
            if self._saved_geometry is not None:
                self._window.setGeometry(self._saved_geometry)
            if self._saved_min_size is not None:
                self._window.setMinimumSize(self._saved_min_size)
            self._shrunk = False
        else:
            if self._window.isMaximized():
                self._window.showNormal()
            self._saved_geometry = self._window.geometry()
            self._saved_min_size = self._window.minimumSize()
            self._window.setMinimumSize(0, 0)
            self._window.resize(280, self.HEIGHT + 4)
            self._shrunk = True

    # ------------------------------------------------------------------
    # Kill action
    # ------------------------------------------------------------------

    def _resolve_exe_path(self):
        """Return the exe path (directory + name) of the selected Editor row."""
        mw = self._window
        editor = getattr(mw, "editor_tab", None)
        table = getattr(editor, "table", None)
        if table is None:
            return None
        row = table.currentRow()
        if row < 0:
            return None

        def _text(col):
            item = table.item(row, col)
            return item.text() if item is not None else ""

        name = _text(constants.EditorCols.NAME.value)
        directory = _text(constants.EditorCols.DIRECTORY.value)
        if not name:
            return None
        if directory and os.path.isabs(directory):
            return os.path.join(directory, name)
        return name

    def _kill_exe(self) -> None:
        exe_path = self._resolve_exe_path()
        if not exe_path:
            self._status("No game selected in the Editor to kill.")
            return
        basename = os.path.basename(exe_path)
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", basename],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._status(f"Killed {basename}")
            else:
                detail = (result.stderr or result.stdout or "unknown error").strip()
                self._status(f"Could not kill {basename}: {detail}")
        except Exception as exc:
            self._status(f"Failed to kill {basename}: {exc}")

    def _status(self, message: str, timeout: int = 3000) -> None:
        mw = self._window
        bar = mw.statusBar() if mw is not None else None
        if bar is not None:
            bar.showMessage(message, timeout)

    # ------------------------------------------------------------------
    # Close-button context menu
    # ------------------------------------------------------------------

    def _show_close_menu(self, position) -> None:
        menu = QMenu(self)

        on_top_action = menu.addAction("On Top")
        on_top_action.setCheckable(True)
        on_top_action.setChecked(self._is_on_top())
        on_top_action.setToolTip("Keep this window above all other windows")

        exe_path = self._resolve_exe_path()
        kill_label = (
            f"Kill {os.path.basename(exe_path)}" if exe_path else "Kill $exe_path"
        )
        kill_action = menu.addAction(kill_label)
        kill_action.setEnabled(exe_path is not None)
        kill_action.setToolTip(
            "Force-kill the executable of the selected Editor row"
            if exe_path
            else "Select a game in the Editor first"
        )

        shrink_action = menu.addAction("Restore Size" if self._shrunk else "Shrink")
        shrink_action.setCheckable(True)
        shrink_action.setChecked(self._shrunk)
        shrink_action.setToolTip("Shrink this window to a compact strip")

        chosen = menu.exec(self.close_button.mapToGlobal(position))
        if chosen is on_top_action:
            self._toggle_on_top()
        elif chosen is kill_action:
            self._kill_exe()
        elif chosen is shrink_action:
            self._toggle_shrink()

    # ------------------------------------------------------------------
    # Dragging / maximize
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._window.isMaximized()
        ):
            self._drag_offset = (
                event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            )
            self._dragging = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._dragging
            and event.buttons() & Qt.MouseButton.LeftButton
            and not self._window.isMaximized()
        ):
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_max_button()
        super().changeEvent(event)

    def setWindowTitle(self, title: str) -> None:
        self.title_label.setText(title)

    def setWindowIcon(self, icon) -> None:
        self.icon_label.setPixmap(icon.pixmap(18, 18))
