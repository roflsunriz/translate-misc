import sys
import tkinter as tk
from pathlib import Path
from typing import Protocol, cast

import pytest

from translation_pipeline.gui import TranslationGui


class _StatefulWidget(Protocol):
    def instate(self, statespec: list[str]) -> bool: ...


def _is_disabled(widget: object) -> bool:
    return cast(_StatefulWidget, widget).instate(["disabled"])


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
        assert _is_disabled(app.save_button)
        assert _is_disabled(app.open_original_button)
        assert _is_disabled(app.publish_button)
        assert _is_disabled(app.push_button)
    finally:
        root.destroy()
