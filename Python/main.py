import sys
import os
import logging
import argparse
from importlib import import_module

# Add the parent directory (anattagen) to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def setup_logging():
    """Set up logging to file and console. Honor ANATTAGEN_LOG_LEVEL environment variable for verbosity."""
    log_file = os.path.join(project_root, 'app.log')
    level_name = os.environ.get('ANATTAGEN_LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Starting application from {script_dir}")
    logging.info(f"Log file: {os.path.abspath(log_file)}")


def main():
    """Main function to run the application."""
    parser = argparse.ArgumentParser(
        description="Game Env Manager - Main App"
    )
    parser.add_argument(
        "--android-preview",
        action="store_true",
        help="Run the Android Kivy UI in desktop preview mode",
    )

    args, _ = parser.parse_known_args()
    # Remove app-specific args so Kivy doesn't try to parse them
    sys.argv = [arg for arg in sys.argv if arg != "--android-preview"]

    setup_logging()

    # Detect REAL Android runtime (python-for-android only)
    is_android = hasattr(sys, "getandroidapilevel")

    logging.info(
        "Runtime selection: %s",
        "ANDROID"
        if is_android
        else "ANDROID PREVIEW"
        if args.android_preview
        else "DESKTOP (PyQt)",
    )

    if is_android or args.android_preview:
        # Configure Kivy environment
        if is_android:
            os.environ.setdefault('KIVY_BUILD', 'android')
            os.environ.setdefault('KIVY_GL_BACKEND', 'gles')
            os.environ.setdefault('KIVY_WINDOW', 'sdl2')
            # Fake ANDROID_APP_PATH to prevent Kivy import errors
            os.environ.setdefault('ANDROID_APP_PATH', project_root)
            logging.info("Configured Kivy for real Android runtime")
        else:
            # Fake ANDROID_APP_PATH for desktop preview
            os.environ.setdefault('ANDROID_APP_PATH', project_root)
            logging.info("Running Kivy in desktop preview mode (no Android env vars set)")

        try:
            android_main = import_module('Python.android_ui.main')
            android_main.run_android_app()
            return
        except Exception:
            logging.exception('Failed to start Android UI adapter')

    # Desktop / default path (PyQt)
    try:
        from PyQt6.QtWidgets import QApplication
        from Python.main_window_new import MainWindow

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.exception('Failed to start PyQt UI: %s', e)


if __name__ == "__main__":
    main()
