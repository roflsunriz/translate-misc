from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from translation_pipeline.errors import PipelineError
from translation_pipeline.models import SessionMetadata

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_slug(value: str) -> str:
    slug = value.strip().lower().replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        raise PipelineError(
            "slugを生成できません。--slug に英小文字・数字・ハイフンで指定してください。"
        )
    validate_slug(slug)
    return slug


def validate_slug(slug: str) -> None:
    if not _SLUG.fullmatch(slug):
        raise PipelineError("slugは英小文字・数字・ハイフンだけで指定してください。")


def session_directory(work_directory: Path, slug: str) -> Path:
    validate_slug(slug)
    return work_directory / slug


def create_session(
    work_directory: Path,
    metadata: SessionMetadata,
    source_markdown: str,
    draft_markdown: str,
) -> Path:
    directory = session_directory(work_directory, metadata.slug)
    if directory.exists():
        raise PipelineError(
            f"作業セッション {directory} は既に存在します。別の --slug を指定してください。"
        )
    directory.mkdir(parents=True)
    _write_text(directory / "source.md", source_markdown)
    _write_text(directory / "draft.md", draft_markdown)
    _write_json(directory / "metadata.json", metadata.to_dict())
    return directory


def load_session(work_directory: Path, slug: str) -> tuple[Path, SessionMetadata, str]:
    directory = session_directory(work_directory, slug)
    metadata_path = directory / "metadata.json"
    draft_path = directory / "draft.md"
    if not metadata_path.is_file() or not draft_path.is_file():
        raise PipelineError(f"作業セッションが見つかりません: {directory}")
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(f"セッション情報を読み取れません: {metadata_path}") from error
    if not isinstance(value, dict):
        raise PipelineError("セッション情報の形式が不正です。")
    metadata = SessionMetadata.from_dict(value)
    if metadata.slug != slug:
        raise PipelineError("セッション情報のslugが作業ディレクトリ名と一致しません。")
    validate_slug(metadata.slug)
    return directory, metadata, draft_path.read_text(encoding="utf-8")


def update_session_stage(
    directory: Path, metadata: SessionMetadata, stage: str, commit: str | None = None
) -> SessionMetadata:
    updated = replace(metadata, stage=stage, commit=commit)
    _write_json(directory / "metadata.json", updated.to_dict())
    return updated


def _write_text(path: Path, value: str) -> None:
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
