from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from translation_pipeline.config import Settings
from translation_pipeline.errors import PipelineError
from translation_pipeline.models import SessionMetadata
from translation_pipeline.openai_compatible_client import OpenAICompatibleClient
from translation_pipeline.workspace import load_session

PROVIDER_KEYS = {
    "cerebras": "CEREBRAS_API_KEY",
    "sakura": "SAKURA_AI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}
PERSISTENT_NAMES = (
    *PROVIDER_KEYS.values(),
    "TRANSLATE_REVIEW_PROVIDER",
    "TRANSLATE_PLAMO_SCRIPT",
)
DEFAULT_PLAMO_SCRIPT = Path.home() / "Documents" / "llama.cpp" / "scripts" / "pl2.ps1"


@dataclass(frozen=True)
class SessionItem:
    directory: Path
    metadata: SessionMetadata

    @property
    def label(self) -> str:
        return f"{self.metadata.title}  [{self.metadata.slug}]"


def find_repository(start: Path | None = None) -> Path:
    candidates = [
        (start or Path.cwd()).resolve(),
        Path(__file__).resolve().parents[1],
    ]
    for candidate in candidates:
        if (candidate / ".git").exists() and (candidate / "mkdocs.yml").is_file():
            return candidate
    raise PipelineError("翻訳リポジトリを見つけられません。リポジトリ内から起動してください。")


def list_sessions(work_directory: Path) -> tuple[list[SessionItem], list[str]]:
    items: list[SessionItem] = []
    warnings: list[str] = []
    if not work_directory.is_dir():
        return items, warnings
    for directory in work_directory.iterdir():
        if not directory.is_dir():
            continue
        try:
            loaded_directory, metadata, _ = load_session(work_directory, directory.name)
        except PipelineError as error:
            warnings.append(str(error))
            continue
        items.append(SessionItem(loaded_directory, metadata))
    items.sort(key=lambda item: item.metadata.created_at, reverse=True)
    return items, warnings


def read_source(item: SessionItem) -> str:
    path = item.directory / "source.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise PipelineError(f"原文を読み取れません: {path}") from error


def save_draft(item: SessionItem, draft: str) -> None:
    if item.metadata.stage != "awaiting_human_review":
        raise PipelineError("公開待ちではないセッションの下書きは変更できません。")
    path = item.directory / "draft.md"
    try:
        path.write_text(draft.rstrip() + "\n", encoding="utf-8", newline="\n")
    except OSError as error:
        raise PipelineError(f"下書きを保存できません: {path}") from error


def load_persistent_environment() -> None:
    for name in PERSISTENT_NAMES:
        value = read_user_environment(name)
        if value:
            os.environ[name] = value


def read_user_environment(name: str) -> str | None:
    _validate_environment_name(name)
    if sys.platform != "win32":
        return os.environ.get(name)
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None
    return value if isinstance(value, str) and value else None


def write_user_environment(name: str, value: str) -> None:
    _validate_environment_name(name)
    if not value:
        raise PipelineError("空の値は保存できません。")
    if sys.platform != "win32":
        raise PipelineError("恒久設定の保存はWindowsでのみ利用できます。")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    os.environ[name] = value
    _broadcast_environment_change()


def delete_user_environment(name: str) -> None:
    _validate_environment_name(name)
    if sys.platform != "win32":
        raise PipelineError("恒久設定の削除はWindowsでのみ利用できます。")
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            access=winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass
    os.environ.pop(name, None)
    _broadcast_environment_change()


def configured_plamo_script() -> Path:
    configured = os.environ.get("TRANSLATE_PLAMO_SCRIPT")
    return Path(configured) if configured else DEFAULT_PLAMO_SCRIPT


def check_plamo_server(settings: Settings) -> str:
    endpoint = replace(settings.translator, timeout_seconds=3.0)
    return OpenAICompatibleClient(endpoint).healthcheck()


def start_plamo_server(script: Path) -> None:
    resolved = script.expanduser().resolve()
    if not resolved.is_file():
        raise PipelineError(f"PLaMo起動スクリプトが見つかりません: {resolved}")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(resolved),
        ],
        cwd=resolved.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise PipelineError(f"PLaMoを起動できません。\n{detail}")


def _validate_environment_name(name: str) -> None:
    if name not in PERSISTENT_NAMES:
        raise ValueError(f"管理対象外の環境変数です: {name}")


def _broadcast_environment_change() -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    result = ctypes.c_size_t()
    user32.SendMessageTimeoutW(
        0xFFFF,
        0x001A,
        0,
        "Environment",
        0x0002,
        5000,
        ctypes.byref(result),
    )
