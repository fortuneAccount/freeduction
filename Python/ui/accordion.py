from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QToolButton, QSizePolicy, QLabel
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve


class AccordionSection(QWidget):
    EXPANDED_MAX = 16777215  # Qt's QWIDGETSIZE_MAX

    def __init__(self, title: str, content: QWidget, animation_duration=200,
                 start_expanded=False, qlementine_style: bool = False,
                 max_height: int = None):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._max_height = max_height if max_height is not None else self.EXPANDED_MAX

        self.toggle_button = QToolButton(text=title, checkable=True, checked=start_expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle_button.clicked.connect(self.toggle)

        if qlementine_style:
            self._apply_qlementine_style()

        self._content_container = QWidget()
        container_layout = QVBoxLayout(self._content_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(content)

        initial_height = self._max_height if start_expanded else 0
        self._content_container.setMaximumHeight(initial_height)

        self.animation = QPropertyAnimation(self._content_container, b"maximumHeight")
        self.animation.setDuration(animation_duration)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.content_height = content.sizeHint().height()

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self._content_container)

    def _apply_qlementine_style(self) -> None:
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

    def toggle(self):
        checked = self.toggle_button.isChecked()

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

        start_height = self._content_container.maximumHeight()
        end_height = self._max_height if checked else 0

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
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Animated Accordion Menu - Qt6")
    layout = QVBoxLayout(window)

    accordion = AccordionMenu()
    layout.addWidget(accordion)

    window.resize(300, 400)
    window.show()
    sys.exit(app.exec())
