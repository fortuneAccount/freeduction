"""
Minimal Kivy-based UI adapter for Android.

Supports:
    - Real Android runtime (APK / emulator)
    - Desktop Android UI preview mode (--android-preview)
"""

import logging
import os
import sys


def is_real_android() -> bool:
    """Return True only when running inside python-for-android."""
    return hasattr(sys, "getandroidapilevel")


def run_android_app():
    """Start the Kivy-based Android UI (lazy imports)."""

    # Configure environment variables
    os.environ.setdefault('ANDROID_APP_PATH', os.path.dirname(os.path.dirname(__file__)))

    if is_real_android():
        for k, v in {'KIVY_BUILD': 'android', 'KIVY_GL_BACKEND': 'gles', 'KIVY_WINDOW': 'sdl2'}.items():
            os.environ.setdefault(k, v)
        logging.info("Starting Kivy UI on REAL Android runtime")
    else:
        logging.info("Starting Kivy Android UI in DESKTOP PREVIEW mode")

    logging.info(
        "Platform=%s | Android API=%s",
        sys.platform,
        getattr(sys, "getandroidapilevel", None),
    )

    try:
        from kivy.app import App
        from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
        from kivy.uix.label import Label
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.core.window import Window
    except Exception as e:
        logging.exception("Kivy is not available: %s", e)
        raise


    class PlaceholderTab(BoxLayout):
        """Simple placeholder content for each top-level tab."""

        def __init__(self, text: str, **kwargs):
            super().__init__(
                orientation='vertical',
                padding=8,
                spacing=8,
                **kwargs
            )
            self.add_widget(Label(text=text))
            self.add_widget(
                Button(
                    text='Refresh',
                    size_hint=(1, None),
                    height=44
                )
            )


    class AndroidKivyApp(App):
        """Main Kivy application class."""

        def build(self):
            Window.clearcolor = (1, 1, 1, 1)

            tp = TabbedPanel(do_default_tab=False)

            # Setup tab
            setup_tab = TabbedPanelItem(text='SETUP')
            setup_tab.add_widget(
                PlaceholderTab('Setup controls go here')
            )
            tp.add_widget(setup_tab)

            # Deployment tab
            deployment_tab = TabbedPanelItem(text='DEPLOYMENT')
            deployment_tab.add_widget(
                PlaceholderTab('Deployment controls go here')
            )
            tp.add_widget(deployment_tab)

            # Editor tab
            editor_tab = TabbedPanelItem(text='EDITOR')
            editor_tab.add_widget(
                PlaceholderTab('Editor controls go here')
            )
            tp.add_widget(editor_tab)

            return tp

    AndroidKivyApp().run()
