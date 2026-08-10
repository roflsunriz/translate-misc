from pathlib import Path

import pytest

from translation_pipeline.config import Settings


@pytest.mark.parametrize(
    ("provider", "key_name", "expected_url", "expected_model"),
    [
        ("cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1", "gpt-oss-120b"),
        (
            "sakura",
            "SAKURA_AI_API_KEY",
            "https://api.ai.sakura.ad.jp/v1",
            "llm-jp-3.1-8x13b-instruct4",
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
    expected_model: str,
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
