from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from translation_pipeline.application import publish_reviewed_session, push_committed_session
from translation_pipeline.config import Settings
from translation_pipeline.errors import PipelineError
from translation_pipeline.pipeline import prepare_article
from translation_pipeline.publisher import CATEGORIES
from translation_pipeline.workspace import load_session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="translate-article",
        description="Web記事を翻訳・校閲し、人間の最終レビュー後にGitHub Pagesへ公開します。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="URLからレビュー用の下書きを作成")
    prepare.add_argument("url")
    prepare.add_argument("--category", choices=CATEGORIES, default="Essays")
    prepare.add_argument("--slug")
    prepare.add_argument(
        "--review-provider", choices=("cerebras", "sakura", "openrouter"), default=None
    )
    prepare.add_argument("--allow-private-url", action="store_true")

    review = subparsers.add_parser("review", help="下書きを既定のエディターで開く")
    review.add_argument("slug")

    publish_parser = subparsers.add_parser(
        "publish", help="最終レビュー済み下書きをコミットし、mainへpush"
    )
    publish_parser.add_argument("slug")
    publish_parser.add_argument("--yes", action="store_true", help="確認プロンプトを省略")
    publish_parser.add_argument(
        "--no-push", action="store_true", help="コミットまで行い、pushは行わない"
    )

    push_parser = subparsers.add_parser("push", help="失敗したpushだけを再実行")
    push_parser.add_argument("slug")

    status = subparsers.add_parser("status", help="下書きセッションの状態を表示")
    status.add_argument("slug")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = Path.cwd()
    try:
        if args.command == "prepare":
            settings = Settings.from_environment(repository, args.review_provider)
            print(
                f"校閲には {settings.reviewer_provider} APIを使用し、"
                "記事本文を同サービスへ送信します。"
            )
            directory = prepare_article(
                settings,
                args.url,
                args.category,
                args.slug,
                allow_private_url=args.allow_private_url,
            )
            print("下書きを確認・修正したら、次を実行してください:")
            print(f"  translate-article review {directory.name}")
            print(f"  translate-article publish {directory.name}")
            return 0
        settings = Settings.from_environment(repository)
        directory, metadata, draft = load_session(settings.work_directory, args.slug)
        if args.command == "review":
            _open_in_editor(directory / "draft.md")
            return 0
        if args.command == "status":
            print(f"slug: {metadata.slug}")
            print(f"title: {metadata.title}")
            print(f"stage: {metadata.stage}")
            print(f"draft: {directory / 'draft.md'}")
            return 0
        if args.command == "push":
            push_committed_session(settings, args.slug)
            print("mainへのpushが完了しました。GitHub Pagesのワークフローが開始されます。")
            return 0
        if args.command == "publish":
            if metadata.stage != "awaiting_human_review":
                raise PipelineError(
                    f"このセッションは公開待ちではありません（stage: {metadata.stage}）。"
                )
            if not args.yes:
                _confirm_human_review(metadata.title)
            result = publish_reviewed_session(settings, args.slug, draft, push=not args.no_push)
            print(f"記事を追加しました: {result.article_path}")
            if result.pushed:
                print("mainへのpushが完了しました。GitHub Pagesのワークフローが開始されます。")
            else:
                print(f"pushするには translate-article push {metadata.slug} を実行してください。")
            return 0
    except (PipelineError, ValueError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    return 1


def _confirm_human_review(title: str) -> None:
    if not sys.stdin.isatty():
        raise PipelineError(
            "対話確認できません。最終レビュー済みの場合だけ --yes を指定してください。"
        )
    answer = input(f"「{title}」の原文照合と最終修正は完了しましたか？ [y/N]: ")
    if answer.strip().lower() not in {"y", "yes"}:
        raise PipelineError("公開を中止しました。下書きをレビューしてから再実行してください。")


def _open_in_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR")
    try:
        if editor:
            subprocess.Popen([editor, str(path)])
        elif sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as error:
        raise PipelineError(f"エディターを開けません。直接開いてください: {path}") from error
    print(f"下書きを開きました: {path}")
