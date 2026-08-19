from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from translation_pipeline.models import Endpoint


@dataclass(frozen=True)
class Settings:
    repository: Path
    work_directory: Path
    translator: Endpoint
    reviewer: Endpoint
    reviewer_provider: str
    chunk_characters: int
    fetch_timeout_seconds: float
    max_download_bytes: int

    @classmethod
    def from_environment(cls, repository: Path, reviewer_provider: str | None = None) -> Settings:
        root = repository.resolve()
        provider = (
            reviewer_provider or os.environ.get("TRANSLATE_REVIEW_PROVIDER", "cerebras")
        ).lower()
        return cls(
            repository=root,
            work_directory=root / ".translation-work",
            translator=_endpoint_from_environment("TRANSLATOR", "http://127.0.0.1:3002/v1"),
            reviewer=_reviewer_endpoint(provider),
            reviewer_provider=provider,
            chunk_characters=_integer("TRANSLATE_CHUNK_CHARACTERS", 3500, minimum=500),
            fetch_timeout_seconds=_number("TRANSLATE_FETCH_TIMEOUT", 30.0, minimum=1.0),
            max_download_bytes=_integer(
                "TRANSLATE_MAX_DOWNLOAD_BYTES", 15 * 1024 * 1024, minimum=1024
            ),
        )


def _endpoint_from_environment(prefix: str, default_url: str) -> Endpoint:
    base_url = os.environ.get(f"TRANSLATE_{prefix}_URL", default_url).rstrip("/")
    return Endpoint(
        base_url=base_url,
        model=os.environ.get(f"TRANSLATE_{prefix}_MODEL") or None,
        api_key=os.environ.get(f"TRANSLATE_{prefix}_API_KEY", "no-key"),
        timeout_seconds=_number(f"TRANSLATE_{prefix}_TIMEOUT", 600.0, minimum=1.0),
    )


def _reviewer_endpoint(provider: str) -> Endpoint:
    if provider == "cerebras":
        return Endpoint(
            base_url="https://api.cerebras.ai/v1",
            model=os.environ.get("CEREBRAS_MODEL") or None,
            api_key=os.environ.get("CEREBRAS_API_KEY", ""),
            timeout_seconds=_number("TRANSLATE_REVIEWER_TIMEOUT", 600.0, minimum=1.0),
        )
    if provider == "sakura":
        return Endpoint(
            base_url="https://api.ai.sakura.ad.jp/v1",
            model=os.environ.get("SAKURA_AI_MODEL") or None,
            api_key=os.environ.get("SAKURA_AI_API_KEY", ""),
            timeout_seconds=_number("TRANSLATE_REVIEWER_TIMEOUT", 600.0, minimum=1.0),
        )
    if provider == "openrouter":
        return Endpoint(
            base_url="https://openrouter.ai/api/v1",
            model=os.environ.get("OPENROUTER_MODEL", "openrouter/free"),
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            timeout_seconds=_number("TRANSLATE_REVIEWER_TIMEOUT", 600.0, minimum=1.0),
        )
    raise ValueError(
        "校閲プロバイダーは cerebras、sakura、openrouter のいずれかを指定してください。"
    )


def _integer(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as error:
        raise ValueError(f"環境変数 {name} は整数で指定してください。") from error
    if value < minimum:
        raise ValueError(f"環境変数 {name} は {minimum} 以上で指定してください。")
    return value


def _number(name: str, default: float, minimum: float) -> float:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as error:
        raise ValueError(f"環境変数 {name} は数値で指定してください。") from error
    if value < minimum:
        raise ValueError(f"環境変数 {name} は {minimum} 以上で指定してください。")
    return value
