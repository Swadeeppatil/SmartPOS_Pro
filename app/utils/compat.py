"""
SmartPOS Pro - KivyMD 1.2.0 Compatibility Shim
Provides unified helper so all screens work with KivyMD 1.2.0.
"""
from kivymd.uix.snackbar import MDSnackbar


def show_snackbar(text: str, duration: float = 2.5):
    """Show a simple snackbar. Works with KivyMD 1.2.0."""
    MDSnackbar(text=str(text), duration=duration).open()


def get_progress_bar():
    """Return the correct progress bar class for installed KivyMD."""
    try:
        from kivymd.uix.progressbar import MDProgressBar
        return MDProgressBar
    except ImportError:
        try:
            from kivymd.uix.progressindicator import MDLinearProgressIndicator
            return MDLinearProgressIndicator
        except ImportError:
            from kivy.uix.progressbar import ProgressBar
            return ProgressBar
