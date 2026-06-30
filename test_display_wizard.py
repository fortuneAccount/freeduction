import configparser
import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

# Provide lightweight stubs for the GUI dependencies used by display_wizard.py.
pyqt6_mod = types.ModuleType("PyQt6")
qtwidgets_mod = types.ModuleType("PyQt6.QtWidgets")
qtcore_mod = types.ModuleType("PyQt6.QtCore")
qtgui_mod = types.ModuleType("PyQt6.QtGui")

class DummyWidget:
    def __init__(self, *args, **kwargs):
        pass

class DummyQtObject:
    pass

class DummyMessageBox:
    @staticmethod
    def information(*args, **kwargs):
        return None

for name in [
    "QDialog", "QVBoxLayout", "QHBoxLayout", "QLabel", "QPushButton",
    "QFrame", "QWidget", "QComboBox", "QCheckBox",
    "QGroupBox", "QGridLayout", "QScrollArea", "QSizePolicy", "QTabWidget",
    "QFileDialog",
]:
    setattr(qtwidgets_mod, name, DummyWidget)

qtwidgets_mod.QMessageBox = DummyMessageBox

qtcore_mod.Qt = DummyQtObject
qtcore_mod.QRect = DummyWidget
qtgui_mod.QPainter = DummyWidget
qtgui_mod.QColor = DummyWidget
qtgui_mod.QPen = DummyWidget
qtgui_mod.QBrush = DummyWidget
qtgui_mod.QGuiApplication = types.SimpleNamespace(screens=lambda: [], primaryScreen=lambda: None)

sys.modules["PyQt6"] = pyqt6_mod
sys.modules["PyQt6.QtWidgets"] = qtwidgets_mod
sys.modules["PyQt6.QtCore"] = qtcore_mod
sys.modules["PyQt6.QtGui"] = qtgui_mod

constants_mod = types.ModuleType("Python.constants")
sys.modules["Python.constants"] = constants_mod

spec = importlib.util.spec_from_file_location(
    "display_wizard",
    ROOT / "Python" / "ui" / "display_wizard.py",
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class DisplayWizardParserTests(unittest.TestCase):
    def test_parse_change_screen_resolution_output(self):
        output = """Display 1
  1920x1080 60Hz 32bpp
  2560x1440 144Hz 32bpp
Display 2
  1280x720 60Hz 32bpp
"""

        parsed = module.DisplayWizard._parse_change_screen_resolution_output(output)
        mode_data = {key: value for key, value in parsed.items() if isinstance(key, int)}
        self.assertEqual(
            mode_data,
            {
                1: [
                    {"resolution": "1920x1080", "refresh": "60", "bit_depth": "32bpp"},
                    {"resolution": "2560x1440", "refresh": "144", "bit_depth": "32bpp"},
                ],
                2: [{"resolution": "1280x720", "refresh": "60", "bit_depth": "32bpp"}],
            },
        )

    def test_parse_change_screen_resolution_output_with_colons_and_labels(self):
        output = """Display: 1
  1920x1080 @ 60Hz, 32bpp
  2560x1440 @ 144Hz, 32bpp
Display 2
  1280x720 @ 60Hz, 32bpp
"""

        parsed = module.DisplayWizard._parse_change_screen_resolution_output(output)
        mode_data = {key: value for key, value in parsed.items() if isinstance(key, int)}
        self.assertEqual(
            mode_data[1][0],
            {"resolution": "1920x1080", "refresh": "60", "bit_depth": "32bpp"},
        )
        self.assertEqual(mode_data[2][0]["resolution"], "1280x720")

    def test_parse_actual_change_screen_resolution_output(self):
        output = """Connected display devices:
  [0] \\.\\DISPLAY7                  AMD Radeon 740M Graphics
      \\.\\DISPLAY7\\Monitor0           Generic PnP Monitor
          Settings: 1152x864 32bit @75Hz default

  [1] \\.\\DISPLAY8                  AMD Radeon 740M Graphics
Display modes for \\.\\DISPLAY7:
  1920x1080 32bit @60Hz default
  1280x720 32bit @48Hz default
Display modes for \\.\\DISPLAY8:
  1920x1200 32bit @60Hz default
"""

        parsed = module.DisplayWizard._parse_change_screen_resolution_output(output)
        self.assertEqual(parsed["display_names"][0], "AMD Radeon 740M Graphics")
        self.assertEqual(parsed["display_names"][1], "\\.\\DISPLAY8")
        self.assertEqual(parsed[0][0]["resolution"], "1920x1080")
        self.assertEqual(parsed[0][0]["refresh"], "60")
        self.assertEqual(parsed[0][0]["bit_depth"], "32bit")

    def test_save_ini_writes_display_sections_and_keys(self):
        wizard = module.DisplayWizard.__new__(module.DisplayWizard)
        wizard.windowing_app_name = ""
        wizard.accept = lambda: None
        wizard._monitor_states = {
            "Desktop / Exit State": {
                1: {
                    "screen": types.SimpleNamespace(name=lambda: "Primary Display"),
                    "enable": types.SimpleNamespace(isChecked=lambda: True),
                    "resolution": types.SimpleNamespace(currentText=lambda: "1920x1080"),
                    "refresh": types.SimpleNamespace(currentText=lambda: "60"),
                    "bit_depth": types.SimpleNamespace(currentText=lambda: "32bpp"),
                }
            }
        }
        wizard.setup_tab = types.SimpleNamespace(
            main_window=types.SimpleNamespace(
                config=types.SimpleNamespace(),
                config_manager=types.SimpleNamespace(save_config=lambda config: None),
            )
        )

        with tempfile.NamedTemporaryFile("w+", suffix=".ini", delete=False) as handle:
            path = handle.name
        try:
            wizard._save_ini(path)
            parser = configparser.ConfigParser()
            parser.read(path)
            self.assertIn("Primary Display", parser.sections())
            self.assertEqual(parser["Primary Display"]["resolution"], "1920x1080")
            self.assertEqual(parser["Primary Display"]["frequency"], "60")
            self.assertEqual(parser["Primary Display"]["bitdepth"], "32bpp")
        finally:
            pathlib.Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
