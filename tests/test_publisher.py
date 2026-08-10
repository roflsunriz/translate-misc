import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from translation_pipeline.errors import PipelineError
from translation_pipeline.models import ARTICLE_ATTRIBUTION, SessionMetadata
from translation_pipeline.publisher import (
    publish,
    update_changelog,
    update_index,
    update_navigation,
)


def test_index_entry_is_added_to_selected_category() -> None:
    content = "# Index\n\n## Essays\n\n- [Old](articles/old.md)\n\n## Notes\n"

    updated = update_index(content, "Essays", "New", "new")

    assert "- [New](articles/new.md)\n\n## Notes" in updated


def test_navigation_entry_quotes_title() -> None:
    content = (
        "nav:\n  - Home: index.md\n  - Essays:\n      - Old: articles/old.md\n"
        "  - Notes:\n      - Note: articles/note.md\n"
    )

    updated = update_navigation(content, "Essays", "A: New Article", "new")

    assert '      - "A: New Article": articles/new.md\n  - Notes:' in updated


def test_duplicate_navigation_path_is_rejected() -> None:
    with pytest.raises(PipelineError, match="既に登録"):
        update_navigation(
            "nav:\n  - Essays:\n      - Old: articles/new.md\n", "Essays", "New", "new"
        )


def test_changelog_added_section_is_created() -> None:
    content = "# 変更履歴\n\n## [Unreleased]\n\n### Changed\n\n- Existing\n"

    updated = update_changelog(content, "New")

    assert "### Added\n\n- 翻訳記事「New」" in updated
    assert "### Changed" in updated


def test_publish_builds_and_commits_only_publication_files(tmp_path: Path) -> None:
    (tmp_path / "docs" / "articles").mkdir(parents=True)
    (tmp_path / "docs" / "articles" / "old.md").write_text("# Old\n", encoding="utf-8")
    (tmp_path / "docs" / "index.md").write_text(
        "# Index\n\n## Essays\n\n## Notes\n\n## Papers\n\n## Games\n", encoding="utf-8"
    )
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Test\nnav:\n  - Home: index.md\n  - Essays:\n      - Old: articles/old.md\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# 変更履歴\n\n## [Unreleased]\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("site/\n", encoding="utf-8")
    (tmp_path / "unrelated.txt").write_text("before\n", encoding="utf-8")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "初期状態")
    (tmp_path / "unrelated.txt").write_text("user change\n", encoding="utf-8")
    _git(tmp_path, "add", "unrelated.txt")
    metadata = SessionMetadata(
        slug="new-article",
        category="Essays",
        original_url="https://example.com/new",
        title="New Article",
        author=None,
        published_date=None,
        created_at=datetime.now(UTC).isoformat(),
        translator_model="plamo",
        reviewer_provider="openrouter",
        reviewer_model="openrouter/free",
    )
    draft = (
        "# New Article\n\n**Original URL:** "
        "[example.com/new](https://example.com/new)\n\n---\n\n訳文だ。\n\n---\n\n"
        f"{ARTICLE_ATTRIBUTION}\n"
    )

    result = publish(tmp_path, metadata, draft, push=False)

    assert result.pushed is False
    assert result.article_path.is_file()
    changed = _git(tmp_path, "show", "--pretty=format:", "--name-only", "HEAD")
    assert set(changed.splitlines()) == {
        "CHANGELOG.md",
        "docs/articles/new-article.md",
        "docs/index.md",
        "mkdocs.yml",
    }
    assert _git(tmp_path, "status", "--short").strip() == "M  unrelated.txt"


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return completed.stdout.strip()
