import json
from pathlib import Path

import pytest

from translation_pipeline.errors import PipelineError
from translation_pipeline.workspace import load_session, normalize_slug, validate_slug


def test_slug_is_normalized() -> None:
    assert normalize_slug("A Useful_Article!") == "a-useful-article"


@pytest.mark.parametrize("slug", ["../outside", "UPPER", "two--hyphens", "ends-"])
def test_unsafe_slug_is_rejected(slug: str) -> None:
    with pytest.raises(PipelineError, match="slug"):
        validate_slug(slug)


def test_session_metadata_slug_must_match_directory(tmp_path: Path) -> None:
    directory = tmp_path / "safe"
    directory.mkdir()
    (directory / "draft.md").write_text("draft", encoding="utf-8")
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "slug": "different",
                "category": "Essays",
                "original_url": "https://example.com",
                "title": "Title",
                "author": None,
                "published_date": None,
                "created_at": "2026-08-10T00:00:00+00:00",
                "translator_model": "plamo",
                "reviewer_provider": "openrouter",
                "reviewer_model": "openrouter/free",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PipelineError, match="一致"):
        load_session(tmp_path, "safe")
