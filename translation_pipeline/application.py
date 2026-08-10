from __future__ import annotations

import subprocess
from pathlib import Path

from translation_pipeline.config import Settings
from translation_pipeline.errors import PipelineError
from translation_pipeline.publisher import PublicationResult, publish, push_existing_commit
from translation_pipeline.workspace import load_session, update_session_stage


def publish_reviewed_session(
    settings: Settings,
    slug: str,
    draft: str,
    *,
    push: bool,
) -> PublicationResult:
    directory, metadata, _ = load_session(settings.work_directory, slug)
    if metadata.stage != "awaiting_human_review":
        raise PipelineError(f"このセッションは公開待ちではありません（stage: {metadata.stage}）。")

    (directory / "draft.md").write_text(draft.rstrip() + "\n", encoding="utf-8", newline="\n")
    try:
        result = publish(settings.repository, metadata, draft, push=push)
    except PipelineError:
        head = _current_head(settings.repository)
        article = settings.repository / "docs" / "articles" / f"{metadata.slug}.md"
        if article.exists() and head:
            update_session_stage(directory, metadata, "committed_not_pushed", head)
        raise

    stage = "published" if result.pushed else "committed_not_pushed"
    update_session_stage(directory, metadata, stage, result.commit)
    return result


def push_committed_session(settings: Settings, slug: str) -> None:
    directory, metadata, _ = load_session(settings.work_directory, slug)
    if metadata.stage != "committed_not_pushed":
        raise PipelineError(
            f"このセッションは再push待ちではありません（stage: {metadata.stage}）。"
        )
    push_existing_commit(settings.repository, metadata)
    update_session_stage(directory, metadata, "published", metadata.commit)


def _current_head(repository: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None
