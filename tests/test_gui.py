import sys
import tkinter as tk
from pathlib import Path

import pytest

from translation_pipeline.gui import TranslationGui


@pytest.mark.skipif(sys.platform != "win32", reason="TkデスクトップGUIはWindowsで検証する")
def test_gui_builds_without_console_and_supports_small_window(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "mkdocs.yml").write_text("site_name: test\n", encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = TranslationGui(root, tmp_path)
        root.geometry("820x620")
        root.update_idletasks()

        assert root.title() == "翻訳記事パイプライン"
        assert root.minsize() == (820, 620)
        assert app.provider_var.get() in {
            "Cerebras",
            "さくらのAI Engine",
            "OpenRouter Free Router",
        }
        assert app.save_button.instate(["disabled"])
        assert app.open_original_button.instate(["disabled"])
        assert app.publish_button.instate(["disabled"])
        assert app.push_button.instate(["disabled"])
    finally:
        root.destroy()
