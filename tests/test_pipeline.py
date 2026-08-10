from pathlib import Path

import pytest

from translation_pipeline.config import Settings
from translation_pipeline.models import Article, Endpoint
from translation_pipeline.pipeline import prepare_article, render_article


class _FakeClient:
    chat_calls = 0

    def __init__(self, endpoint: Endpoint) -> None:
        self.endpoint = endpoint

    def healthcheck(self) -> str:
        return self.endpoint.model or "discovered-model"

    def completion(self, prompt: str, *, max_tokens: int = 4096, stop=()):  # type: ignore[no-untyped-def]
        del max_tokens
        assert "<|plamo:op|>input lang=English" in prompt
        assert stop == ("<|plamo:op|>",)
        return "これはテストです。"

    def chat(self, system: str, user: str, *, max_tokens: int = 4096) -> str:
        del system, max_tokens
        self.__class__.chat_calls += 1
        if "<source" in user:
            return "これはテストだ。"
        return "これはテストである。"


def test_prepare_creates_human_review_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    article = Article(
        url="https://example.com/sample-article",
        title="Sample Article",
        author="Example Author",
        published_date="2026-08-10",
        source_markdown="This is a sufficiently long article body. " * 8,
    )
    monkeypatch.setattr("translation_pipeline.pipeline.fetch_and_extract", lambda *a, **k: article)
    monkeypatch.setattr("translation_pipeline.pipeline.OpenAICompatibleClient", _FakeClient)
    settings = Settings(
        repository=tmp_path,
        work_directory=tmp_path / ".translation-work",
        translator=Endpoint("http://localhost:3002/v1", "plamo", "no-key", 10),
        reviewer=Endpoint("https://api.example/v1", "reviewer", "test-key", 10),
        reviewer_provider="cerebras",
        chunk_characters=3500,
        fetch_timeout_seconds=10,
        max_download_bytes=10000,
    )

    directory = prepare_article(
        settings,
        article.url,
        "Essays",
        None,
        allow_private_url=False,
        progress=lambda message: None,
    )

    draft = (directory / "draft.md").read_text(encoding="utf-8")
    assert "# Sample Article" in draft
    assert "これはテストだ。" in draft
    assert "PLaMo 2 translate" in draft
    assert (directory / "source.md").is_file()
    assert _FakeClient.chat_calls == 1


def test_render_article_keeps_attribution() -> None:
    article = Article("https://example.com/a", "A", None, None, "source")

    rendered = render_article(article, "訳文だ。")

    assert "**Original URL:**" in rendered
    assert "PLaMo 2 translate" in rendered
    assert "人間が最終確認" in rendered
