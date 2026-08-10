from pathlib import Path


def test_vbs_launcher_is_ascii_compatible_and_shows_gui() -> None:
    launcher = Path(__file__).resolve().parents[1] / "start-translation-gui.vbs"
    content = launcher.read_bytes().decode("ascii")

    assert ".venv\\Scripts\\pythonw.exe" in content
    assert " -m translation_pipeline.gui" in content
    assert "shell.Run command, 1, False" in content
