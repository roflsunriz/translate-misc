from pathlib import Path

import pytest

from translation_pipeline.application import publish_reviewed_session, push_committed_session
from translation_pipeline.config import Settings
from translation_pipeline.models import Endpoint, SessionMetadata
from translation_pipeline.publisher import PublicationResult
from translation_pipeline.workspace import create_session, load_session, update_session_stage


def _settings(repository: Path) -> Settings:
    return Settings(
        repository=repository,
        work_directory=repository / ".translation-work",
        translator=Endpoint("http://localhost:3002/v1", "plamo", "no-key", 10),
        reviewer=Endpoint("https://api.example/v1", "reviewer", "key", 10),
        reviewer_provider="cerebras",
        chunk_characters=3500,
        fetch_timeout_seconds=10,
        max_download_bytes=10000,
    )


def _metadata(stage: str = "awaiting_human_review") -> SessionMetadata:
    return SessionMetadata(
        slug="sample",
        category="Essays",
        original_url="https://example.com/sample",
        title="Sample",
        author=None,
        published_date=None,
        created_at="2026-08-10T00:00:00+00:00",
        translator_model="plamo",
        reviewer_provider="cerebras",
        reviewer_model="reviewer",
        stage=stage,
    )


def test_publish_reviewed_session_saves_draft_and_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    create_session(settings.work_directory, _metadata(), "source", "old draft")
    result = PublicationResult("abc123", False, tmp_path / "docs/articles/sample.md")
    monkeypatch.setattr("translation_pipeline.application.publish", lambda *a, **k: result)

    actual = publish_reviewed_session(settings, "sample", "new draft", push=False)

    _, metadata, draft = load_session(settings.work_directory, "sample")
    assert actual == result
    assert draft == "new draft\n"
    assert metadata.stage == "committed_not_pushed"
    assert metadata.commit == "abc123"


def test_push_committed_session_marks_session_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    directory = create_session(settings.work_directory, _metadata(), "source", "draft")
    metadata = update_session_stage(directory, _metadata(), "committed_not_pushed", "abc123")
    pushed: list[str] = []
    monkeypatch.setattr(
        "translation_pipeline.application.push_existing_commit",
        lambda repository, current: pushed.append(current.commit or ""),
    )

    push_committed_session(settings, metadata.slug)

    _, updated, _ = load_session(settings.work_directory, metadata.slug)
    assert pushed == ["abc123"]
    assert updated.stage == "published"
