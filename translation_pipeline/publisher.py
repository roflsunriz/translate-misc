from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from translation_pipeline.errors import PipelineError
from translation_pipeline.models import ARTICLE_ATTRIBUTION, SessionMetadata
from translation_pipeline.workspace import validate_slug

CATEGORIES = ("Essays", "Notes", "Papers", "Games")


@dataclass(frozen=True)
class PublicationResult:
    commit: str
    pushed: bool
    article_path: Path


def publish(
    repository: Path,
    metadata: SessionMetadata,
    draft: str,
    *,
    push: bool,
) -> PublicationResult:
    root = repository.resolve()
    _validate_repository(root)
    _validate_draft(metadata, draft)
    article_path = root / "docs" / "articles" / f"{metadata.slug}.md"
    targets = [article_path, root / "docs" / "index.md", root / "mkdocs.yml", root / "CHANGELOG.md"]
    if article_path.exists() or article_path.is_symlink():
        raise PipelineError(f"公開先の記事が既に存在します: {article_path}")
    _require_clean_targets(root, targets)

    original = {path: path.read_bytes() if path.exists() else None for path in targets}
    try:
        article_path.write_text(draft.rstrip() + "\n", encoding="utf-8", newline="\n")
        _write(
            root / "docs" / "index.md",
            update_index(
                (root / "docs" / "index.md").read_text(encoding="utf-8"),
                metadata.category,
                metadata.title,
                metadata.slug,
            ),
        )
        _write(
            root / "mkdocs.yml",
            update_navigation(
                (root / "mkdocs.yml").read_text(encoding="utf-8"),
                metadata.category,
                metadata.title,
                metadata.slug,
            ),
        )
        _write(
            root / "CHANGELOG.md",
            update_changelog((root / "CHANGELOG.md").read_text(encoding="utf-8"), metadata.title),
        )
        _run([sys.executable, "-m", "mkdocs", "build", "--strict"], root)
        relative = [str(path.relative_to(root)) for path in targets]
        _run(["git", "add", "--", *relative], root)
        _run(
            [
                "git",
                "commit",
                "--only",
                "-m",
                f"docs(translations): 「{metadata.title}」の翻訳を追加",
                "--",
                *relative,
            ],
            root,
        )
        commit = _run(["git", "rev-parse", "HEAD"], root).strip()
    except Exception:
        if _head_did_not_include_article(root, article_path):
            _restore_files(original)
            _unstage_targets(root, targets)
        raise

    if push:
        try:
            _run(["git", "push", "origin", "main"], root)
        except PipelineError as error:
            raise PipelineError(
                f"コミット {commit[:12]} は作成しましたが、pushに失敗しました。"
                f" `translate-article push {metadata.slug}` で再試行できます。\n{error}"
            ) from error
    return PublicationResult(commit=commit, pushed=push, article_path=article_path)


def push_existing_commit(repository: Path, metadata: SessionMetadata) -> None:
    if not metadata.commit:
        raise PipelineError("再pushできるコミットがセッションに記録されていません。")
    root = repository.resolve()
    head = _run(["git", "rev-parse", "HEAD"], root).strip()
    if head != metadata.commit:
        raise PipelineError(
            "現在のHEADがセッションの公開コミットと一致しません。意図しないpushを防ぐため停止しました。"
        )
    _run(["git", "push", "origin", "main"], root)


def update_index(content: str, category: str, title: str, slug: str) -> str:
    _validate_category(category)
    path = f"articles/{slug}.md"
    if path in content:
        raise PipelineError(f"index.md には {path} が既に登録されています。")
    lines = content.rstrip().splitlines()
    heading = f"## {category}"
    try:
        start = lines.index(heading)
    except ValueError as error:
        raise PipelineError(f"docs/index.md に見出し {heading} がありません。") from error
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    safe_title = title.replace("[", "\\[").replace("]", "\\]")
    lines.insert(end, f"- [{safe_title}]({path})")
    return "\n".join(lines).rstrip() + "\n"


def update_navigation(content: str, category: str, title: str, slug: str) -> str:
    _validate_category(category)
    path = f"articles/{slug}.md"
    if path in content:
        raise PipelineError(f"mkdocs.yml には {path} が既に登録されています。")
    lines = content.rstrip().splitlines()
    section = f"  - {category}:"
    try:
        start = lines.index(section)
    except ValueError as error:
        raise PipelineError(f"mkdocs.yml にナビゲーション {category} がありません。") from error
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("  - ")),
        len(lines),
    )
    yaml_title = json.dumps(title, ensure_ascii=False)
    lines.insert(end, f"      - {yaml_title}: {path}")
    return "\n".join(lines).rstrip() + "\n"


def update_changelog(content: str, title: str) -> str:
    entry = f"- 翻訳記事「{title}」をアーカイブから閲覧できるように、記事本文と索引を追加した。"
    if entry in content:
        return content.rstrip() + "\n"
    lines = content.rstrip().splitlines()
    try:
        unreleased = lines.index("## [Unreleased]")
    except ValueError as error:
        raise PipelineError("CHANGELOG.md に [Unreleased] セクションがありません。") from error
    next_release = next(
        (i for i in range(unreleased + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    try:
        added = lines.index("### Added", unreleased + 1, next_release)
    except ValueError:
        lines[unreleased + 1 : unreleased + 1] = ["", "### Added", "", entry]
        return "\n".join(lines).rstrip() + "\n"
    insertion = next(
        (i for i in range(added + 1, next_release) if lines[i].startswith("### ")),
        next_release,
    )
    while insertion > added + 1 and not lines[insertion - 1].strip():
        insertion -= 1
    lines.insert(insertion, entry)
    return "\n".join(lines).rstrip() + "\n"


def _validate_repository(root: Path) -> None:
    for relative in (".git", "mkdocs.yml", "docs/index.md", "CHANGELOG.md"):
        if not (root / relative).exists():
            raise PipelineError(f"リポジトリ直下で実行してください（不足: {relative}）。")
    branch = _run(["git", "branch", "--show-current"], root).strip()
    if branch != "main":
        raise PipelineError(
            f"GitHub Pages公開用の main ブランチで実行してください（現在: {branch}）。"
        )


def _validate_draft(metadata: SessionMetadata, draft: str) -> None:
    validate_slug(metadata.slug)
    if metadata.category not in CATEGORIES:
        _validate_category(metadata.category)
    if (
        not metadata.title.strip()
        or len(metadata.title) > 300
        or any(ord(character) < 32 for character in metadata.title)
    ):
        raise PipelineError("記事タイトルが空、長すぎる、または制御文字を含んでいます。")
    if not draft.lstrip().startswith("# "):
        raise PipelineError("下書きの先頭にMarkdownのタイトルがありません。")
    if metadata.original_url not in draft:
        raise PipelineError("下書きから原文URLが削除されています。")
    if ARTICLE_ATTRIBUTION not in draft:
        raise PipelineError("PLaMo 2 translate の出力である旨の表示が削除されています。")
    dangerous = re.compile(r"<\s*script\b|javascript\s*:|\bon\w+\s*=", re.IGNORECASE)
    if dangerous.search(draft):
        raise PipelineError("下書きに実行可能なHTMLまたは危険なURLが含まれています。")


def _validate_category(category: str) -> None:
    if category not in CATEGORIES:
        raise PipelineError(f"カテゴリは {', '.join(CATEGORIES)} から選んでください。")


def _require_clean_targets(root: Path, targets: list[Path]) -> None:
    relative = [str(path.relative_to(root)) for path in targets]
    output = _run(["git", "status", "--porcelain", "--", *relative], root)
    if output.strip():
        raise PipelineError(
            "公開処理が更新するファイルに未コミット変更があります。先に内容を確認してコミットしてください:\n"
            + output.strip()
        )


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise PipelineError(f"コマンドに失敗しました: {' '.join(command[:3])}\n{detail}")
    return completed.stdout


def _restore_files(original: dict[Path, bytes | None]) -> None:
    for path, content in original.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)


def _unstage_targets(root: Path, targets: list[Path]) -> None:
    relative = [str(path.relative_to(root)) for path in targets]
    subprocess.run(
        ["git", "restore", "--staged", "--", *relative],
        cwd=root,
        capture_output=True,
        check=False,
    )


def _head_did_not_include_article(root: Path, article_path: Path) -> bool:
    relative = str(article_path.relative_to(root))
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{relative}"],
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode != 0
