from pathlib import Path

import pytest

from translation_pipeline.config import Settings


def test_default_translator_uses_plamo_server_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRANSLATE_TRANSLATOR_URL", raising=False)

    settings = Settings.from_environment(tmp_path)

    assert settings.translator.base_url == "http://127.0.0.1:3002/v1"


@pytest.mark.parametrize(
    ("provider", "key_name", "expected_url", "expected_model"),
    [
        ("cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1", None),
        (
            "sakura",
            "SAKURA_AI_API_KEY",
            "https://api.ai.sakura.ad.jp/v1",
            None,
        ),
        (
            "openrouter",
            "OPENROUTER_API_KEY",
            "https://openrouter.ai/api/v1",
            "openrouter/free",
        ),
    ],
)
def test_reviewer_provider_presets(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    key_name: str,
    expected_url: str,
    expected_model: str | None,
) -> None:
    monkeypatch.setenv(key_name, "secret-for-test")
    settings = Settings.from_environment(Path.cwd(), provider)

    assert settings.reviewer_provider == provider
    assert settings.reviewer.base_url == expected_url
    assert settings.reviewer.model == expected_model
    assert settings.reviewer.api_key == "secret-for-test"


def test_unknown_reviewer_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="校閲プロバイダー"):
        Settings.from_environment(Path.cwd(), "unknown")
