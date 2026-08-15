"""Android UI adapter package (Kivy).

This package provides a minimal entrypoint `run_android_app()` that launches
the Kivy-based UI. It's intentionally lightweight and serves as a scaffold
to be expanded with full parity to the Qt UI.
"""
from .main import run_android_app

__all__ = ["run_android_app"]
