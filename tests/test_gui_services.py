from dataclasses import replace
from pathlib import Path

import pytest

from translation_pipeline.errors import PipelineError
from translation_pipeline.gui_services import (
    SessionItem,
    find_repository,
    list_sessions,
    save_draft,
    start_plamo_server,
    write_user_environment,
)
from translation_pipeline.models import SessionMetadata
from translation_pipeline.workspace import create_session


def _metadata(slug: str, created_at: str) -> SessionMetadata:
    return SessionMetadata(
        slug=slug,
        category="Essays",
        original_url=f"https://example.com/{slug}",
        title=slug.title(),
        author=None,
        published_date=None,
        created_at=created_at,
        translator_model="plamo",
        reviewer_provider="cerebras",
        reviewer_model="reviewer",
    )


def test_list_sessions_sorts_newest_first_and_reports_broken_entries(tmp_path: Path) -> None:
    work = tmp_path / ".translation-work"
    create_session(work, _metadata("older", "2026-01-01T00:00:00+00:00"), "source", "draft")
    create_session(work, _metadata("newer", "2026-02-01T00:00:00+00:00"), "source", "draft")
    (work / "broken").mkdir()

    items, warnings = list_sessions(work)

    assert [item.metadata.slug for item in items] == ["newer", "older"]
    assert len(warnings) == 1
    assert "broken" in warnings[0]


def test_save_draft_preserves_review_changes_and_blocks_processed_session(
    tmp_path: Path,
) -> None:
    metadata = _metadata("sample", "2026-01-01T00:00:00+00:00")
    directory = create_session(tmp_path, metadata, "source", "draft")
    item = SessionItem(directory, metadata)

    save_draft(item, "corrected")

    assert (directory / "draft.md").read_text(encoding="utf-8") == "corrected\n"
    with pytest.raises(PipelineError, match="変更できません"):
        save_draft(SessionItem(directory, replace(metadata, stage="published")), "overwrite")


def test_find_repository_accepts_valid_repository(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "mkdocs.yml").write_text("site_name: test\n", encoding="utf-8")

    assert find_repository(tmp_path) == tmp_path.resolve()


def test_environment_writer_rejects_unmanaged_name() -> None:
    with pytest.raises(ValueError, match="管理対象外"):
        write_user_environment("UNRELATED_SECRET", "value")


def test_start_plamo_server_reports_missing_script(tmp_path: Path) -> None:
    with pytest.raises(PipelineError, match="見つかりません"):
        start_plamo_server(tmp_path / "missing.ps1")
