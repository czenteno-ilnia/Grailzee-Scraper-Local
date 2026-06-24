from __future__ import annotations

import pytest

try:
    import tkinter as tk
except ImportError:
    pytest.skip("Tkinter is not available in this Python environment", allow_module_level=True)

from MainApp import MainApp


@pytest.mark.ui
def test_mainapp_can_create_and_destroy_root() -> None:
    root = tk.Tk()
    try:
        app = MainApp(root)
        assert app.root is root
    finally:
        root.destroy()
