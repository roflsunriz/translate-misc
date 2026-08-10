from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from collections.abc import Callable
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Protocol, cast

from translation_pipeline.application import publish_reviewed_session, push_committed_session
from translation_pipeline.config import Settings
from translation_pipeline.errors import PipelineError
from translation_pipeline.gui_services import (
    PROVIDER_KEYS,
    SessionItem,
    check_plamo_server,
    configured_plamo_script,
    delete_user_environment,
    find_repository,
    list_sessions,
    load_persistent_environment,
    read_source,
    read_user_environment,
    save_draft,
    start_plamo_server,
    write_user_environment,
)
from translation_pipeline.pipeline import prepare_article
from translation_pipeline.publisher import CATEGORIES, PublicationResult
from translation_pipeline.workspace import load_session

PROVIDER_LABELS = {
    "cerebras": "Cerebras",
    "sakura": "さくらのAI Engine",
    "openrouter": "OpenRouter Free Router",
}
PROVIDER_BY_LABEL = {label: provider for provider, label in PROVIDER_LABELS.items()}
STAGE_LABELS = {
    "awaiting_human_review": "人間レビュー待ち",
    "committed_not_pushed": "コミット済み・push待ち",
    "published": "公開済み",
}


class _StatefulWidget(Protocol):
    def state(self, statespec: list[str]) -> object: ...


def _set_widget_enabled(widget: ttk.Widget, enabled: bool) -> None:
    state = ["!disabled"] if enabled else ["disabled"]
    cast(_StatefulWidget, widget).state(state)


class TranslationGui:
    def __init__(self, root: tk.Tk, repository: Path) -> None:
        self.root = root
        self.repository = repository
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._success_callback: Callable[[object], None] | None = None
        self._show_task_error = True
        self._busy = False
        self._loading_draft = False
        self._draft_dirty = False
        self._current_item: SessionItem | None = None
        self._session_by_label: dict[str, SessionItem] = {}
        self._action_buttons: list[ttk.Button] = []

        preferred = os.environ.get("TRANSLATE_REVIEW_PROVIDER", "cerebras")
        if preferred not in PROVIDER_LABELS:
            preferred = "cerebras"
        self.url_var = tk.StringVar()
        self.category_var = tk.StringVar(value="Essays")
        self.provider_var = tk.StringVar(value=PROVIDER_LABELS[preferred])
        self.slug_var = tk.StringVar()
        self.session_var = tk.StringVar()
        self.session_detail_var = tk.StringVar(value="下書きはまだありません。")
        self.server_status_var = tk.StringVar(value="PLaMo 2: 確認中…")
        self.status_var = tk.StringVar(value="準備完了")
        self.push_var = tk.BooleanVar(value=True)
        self.script_var = tk.StringVar(value=str(configured_plamo_script()))
        self.key_vars = {provider: tk.StringVar() for provider in PROVIDER_LABELS}
        self.key_status_vars = {
            provider: tk.StringVar(value="確認中…") for provider in PROVIDER_LABELS
        }

        self._configure_window()
        self._build_layout()
        self._refresh_key_statuses()
        self._refresh_sessions()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_events)
        self.root.after(250, lambda: self._check_server(quiet=True))

    def _configure_window(self) -> None:
        self.root.title("翻訳記事パイプライン")
        self.root.geometry("1200x800")
        self.root.minsize(820, 620)
        self.root.option_add("*Font", ("Yu Gothic UI", 10))
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Yu Gothic UI", 18, "bold"))
        style.configure("Subtitle.TLabel", foreground="#4b5563")
        style.configure("StatusOk.TLabel", foreground="#137333")
        style.configure("StatusError.TLabel", foreground="#b3261e")

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        ttk.Label(outer, text="翻訳記事パイプライン", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text="URLから翻訳・校閲し、人間レビュー後にGitHub Pagesへ公開する。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        notebook = ttk.Notebook(outer)
        notebook.grid(row=2, column=0, sticky="nsew")
        self.new_tab = ttk.Frame(notebook, padding=16)
        self.review_tab = ttk.Frame(notebook, padding=12)
        self.settings_tab = ttk.Frame(notebook, padding=16)
        notebook.add(self.new_tab, text="新規翻訳")
        notebook.add(self.review_tab, text="レビュー・公開")
        notebook.add(self.settings_tab, text="設定")

        self._build_new_tab()
        self._build_review_tab()
        self._build_settings_tab()

        status = ttk.Frame(outer)
        status.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(1, weight=1)
        self.server_status_label = ttk.Label(status, textvariable=self.server_status_var)
        self.server_status_label.grid(row=0, column=0, sticky="w")
        ttk.Separator(status, orient=tk.VERTICAL).grid(row=0, column=1, sticky="nsw", padx=12)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=2, sticky="e")

    def _build_new_tab(self) -> None:
        tab = self.new_tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(7, weight=1)

        ttk.Label(tab, text="記事URL").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(tab, textvariable=self.url_var).grid(row=0, column=1, columnspan=3, sticky="ew")

        ttk.Label(tab, text="カテゴリ").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(12, 0)
        )
        ttk.Combobox(
            tab,
            textvariable=self.category_var,
            values=CATEGORIES,
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w", pady=(12, 0))
        ttk.Label(tab, text="校閲サービス").grid(
            row=1, column=2, sticky="e", padx=(20, 10), pady=(12, 0)
        )
        ttk.Combobox(
            tab,
            textvariable=self.provider_var,
            values=tuple(PROVIDER_BY_LABEL),
            state="readonly",
            width=18,
        ).grid(row=1, column=3, sticky="ew", pady=(12, 0))

        ttk.Label(tab, text="slug（省略可）").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=(12, 0)
        )
        ttk.Entry(tab, textvariable=self.slug_var).grid(
            row=2, column=1, columnspan=3, sticky="ew", pady=(12, 0)
        )
        ttk.Label(
            tab,
            text="本文は選択したクラウドLLMへ送信される。APIキーは「設定」タブで保存できる。",
            style="Subtitle.TLabel",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(12, 8))

        button_row = ttk.Frame(tab)
        button_row.grid(row=4, column=0, columnspan=4, sticky="ew")
        prepare_button = ttk.Button(button_row, text="下書きを作成", command=self._prepare_article)
        prepare_button.pack(side=tk.LEFT)
        check_button = ttk.Button(button_row, text="PLaMo接続確認", command=self._check_server)
        check_button.pack(side=tk.LEFT, padx=(8, 0))
        start_button = ttk.Button(button_row, text="PLaMoを起動", command=self._start_server)
        start_button.pack(side=tk.LEFT, padx=(8, 0))
        self._action_buttons.extend([prepare_button, check_button, start_button])

        self.progress = ttk.Progressbar(tab, mode="indeterminate")
        self.progress.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(12, 8))
        ttk.Label(tab, text="進捗").grid(row=6, column=0, columnspan=4, sticky="w")
        log_frame = ttk.Frame(tab)
        log_frame.grid(row=7, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap="word", height=14, state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

    def _build_review_tab(self) -> None:
        tab = self.review_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        selector = ttk.Frame(tab)
        selector.grid(row=0, column=0, sticky="ew")
        selector.columnconfigure(1, weight=1)
        ttk.Label(selector, text="下書き").grid(row=0, column=0, padx=(0, 8))
        self.session_combo = ttk.Combobox(selector, textvariable=self.session_var, state="readonly")
        self.session_combo.grid(row=0, column=1, sticky="ew")
        self.session_combo.bind("<<ComboboxSelected>>", self._on_session_selected)
        ttk.Button(selector, text="再読込", command=self._refresh_sessions).grid(
            row=0, column=2, padx=(8, 0)
        )

        ttk.Label(tab, textvariable=self.session_detail_var, style="Subtitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(8, 8)
        )

        panes = ttk.Panedwindow(tab, orient=tk.HORIZONTAL)
        panes.grid(row=2, column=0, sticky="nsew")
        source_frame, self.source_text = self._text_pane(panes, "抽出した原文", editable=False)
        draft_frame, self.draft_text = self._text_pane(panes, "翻訳・校閲後の下書き", editable=True)
        panes.add(source_frame, weight=1)
        panes.add(draft_frame, weight=1)
        self.draft_text.bind("<<Modified>>", self._on_draft_modified)

        actions = ttk.Frame(tab)
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.save_button = ttk.Button(
            actions, text="下書きを保存", command=self._save_current_draft
        )
        self.save_button.pack(side=tk.LEFT)
        self.open_original_button = ttk.Button(
            actions, text="原文ページを開く", command=self._open_original
        )
        self.open_original_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(actions, text="GitHubへpushして公開", variable=self.push_var).pack(
            side=tk.LEFT, padx=(20, 0)
        )
        self.publish_button = ttk.Button(
            actions, text="最終確認して公開", command=self._publish_current
        )
        self.publish_button.pack(side=tk.RIGHT)
        self.push_button = ttk.Button(actions, text="pushを再試行", command=self._retry_push)
        self.push_button.pack(side=tk.RIGHT, padx=(0, 8))
        self._action_buttons.extend(
            [
                self.save_button,
                self.open_original_button,
                self.publish_button,
                self.push_button,
            ]
        )

    def _text_pane(
        self, parent: ttk.Panedwindow, title: str, *, editable: bool
    ) -> tuple[ttk.Frame, tk.Text]:
        frame = ttk.Frame(parent, padding=(0, 0, 6, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        ttk.Label(frame, text=title).grid(row=0, column=0, sticky="w", pady=(0, 4))
        text = tk.Text(
            frame, wrap="word", undo=editable, state=tk.NORMAL if editable else tk.DISABLED
        )
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        return frame, text

    def _build_settings_tab(self) -> None:
        tab = self.settings_tab
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, text="APIキー", font=("Yu Gothic UI", 12, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(
            tab,
            text="キーはWindowsユーザー環境変数へ保存する。入力値は画面やログへ再表示しない。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 10))

        row = 2
        for provider, label in PROVIDER_LABELS.items():
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            ttk.Entry(tab, textvariable=self.key_vars[provider], show="●").grid(
                row=row, column=1, sticky="ew", pady=4
            )
            ttk.Label(tab, textvariable=self.key_status_vars[provider], width=14).grid(
                row=row, column=2, sticky="w", padx=10, pady=4
            )
            ttk.Button(
                tab,
                text="削除",
                command=partial(self._delete_key, provider),
            ).grid(row=row, column=3, pady=4)
            row += 1

        ttk.Label(tab, text="既定の校閲サービス").grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=(14, 4)
        )
        ttk.Combobox(
            tab,
            textvariable=self.provider_var,
            values=tuple(PROVIDER_BY_LABEL),
            state="readonly",
        ).grid(row=row, column=1, sticky="w", pady=(14, 4))
        row += 1

        ttk.Separator(tab).grid(row=row, column=0, columnspan=4, sticky="ew", pady=16)
        row += 1
        ttk.Label(tab, text="PLaMo起動スクリプト", font=("Yu Gothic UI", 12, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w"
        )
        row += 1
        ttk.Entry(tab, textvariable=self.script_var).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0)
        )
        ttk.Button(tab, text="参照…", command=self._browse_script).grid(
            row=row, column=3, padx=(8, 0), pady=(8, 0)
        )
        row += 1
        save_settings_button = ttk.Button(tab, text="設定を恒久保存", command=self._save_settings)
        save_settings_button.grid(row=row, column=0, sticky="w", pady=(16, 0))
        self._action_buttons.append(save_settings_button)

    def _prepare_article(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("入力を確認", "記事URLを入力してください。", parent=self.root)
            return
        try:
            self._persist_settings()
            settings = Settings.from_environment(self.repository, self._selected_provider())
        except (PipelineError, ValueError, OSError) as error:
            messagebox.showerror("設定エラー", str(error), parent=self.root)
            return
        slug = self.slug_var.get().strip() or None
        category = self.category_var.get()
        self._append_log(f"下書き生成を開始: {url}")
        self._run_task(
            lambda: prepare_article(
                settings,
                url,
                category,
                slug,
                allow_private_url=False,
                progress=lambda message: self.events.put(("log", message)),
            ),
            self._prepared,
        )

    def _prepared(self, result: object) -> None:
        if not isinstance(result, Path):
            raise TypeError("下書き保存先が不正です。")
        self._append_log(f"完了: {result / 'draft.md'}")
        self.status_var.set("下書きを作成しました")
        self.slug_var.set("")
        self._refresh_sessions(select_slug=result.name)

    def _check_server(self, quiet: bool = False) -> None:
        settings = Settings.from_environment(self.repository, self._selected_provider())
        self.server_status_var.set("PLaMo 2: 確認中…")
        self.server_status_label.configure(style="TLabel")
        self._run_task(
            lambda: check_plamo_server(settings),
            self._server_checked,
            show_error=not quiet,
        )

    def _server_checked(self, result: object) -> None:
        model = str(result)
        self.server_status_var.set(f"PLaMo 2: 接続済み（{model}）")
        self.server_status_label.configure(style="StatusOk.TLabel")
        self.status_var.set("PLaMo 2へ接続できました")

    def _start_server(self) -> None:
        script = Path(self.script_var.get().strip())
        settings = Settings.from_environment(self.repository, self._selected_provider())

        def start_and_wait() -> str:
            try:
                return check_plamo_server(settings)
            except PipelineError:
                start_plamo_server(script)
            last_error: PipelineError | None = None
            for _ in range(30):
                try:
                    return check_plamo_server(settings)
                except PipelineError as error:
                    last_error = error
                    time.sleep(1)
            raise PipelineError(
                "PLaMoを起動しましたが、30秒以内に接続できませんでした。"
            ) from last_error

        self.server_status_var.set("PLaMo 2: 起動中…")
        self._append_log(f"PLaMo起動スクリプトを実行: {script}")
        self._run_task(start_and_wait, self._server_checked)

    def _refresh_sessions(self, select_slug: str | None = None) -> None:
        settings = Settings.from_environment(self.repository, self._selected_provider())
        items, warnings = list_sessions(settings.work_directory)
        self._session_by_label = {item.label: item for item in items}
        self.session_combo.configure(values=tuple(self._session_by_label))
        for warning in warnings:
            self._append_log(f"警告: {warning}")
        target = next((item for item in items if item.metadata.slug == select_slug), None)
        if target is None and self._current_item is not None:
            target = next(
                (item for item in items if item.metadata.slug == self._current_item.metadata.slug),
                None,
            )
        if target is None and items:
            target = items[0]
        if target is None:
            self.session_var.set("")
            self._current_item = None
            self._set_review_contents("", "", editable=False)
            self._update_review_actions()
            return
        self.session_var.set(target.label)
        self._load_item(target)

    def _on_session_selected(self, _event: tk.Event[tk.Misc]) -> None:
        selected = self._session_by_label.get(self.session_var.get())
        if selected is None or selected == self._current_item:
            return
        if not self._confirm_discard_or_save():
            if self._current_item is not None:
                self.session_var.set(self._current_item.label)
            return
        self._load_item(selected)

    def _load_item(self, item: SessionItem) -> None:
        _, metadata, draft = load_session(
            item.directory.parent,
            item.metadata.slug,
        )
        current = SessionItem(item.directory, metadata)
        source = read_source(current)
        editable = metadata.stage == "awaiting_human_review"
        self._current_item = current
        self._set_review_contents(source, draft, editable=editable)
        stage = STAGE_LABELS.get(metadata.stage, metadata.stage)
        provider = PROVIDER_LABELS.get(metadata.reviewer_provider, metadata.reviewer_provider)
        self.session_detail_var.set(f"{stage} ・ {provider} ・ {metadata.original_url}")
        self._update_review_actions()

    def _set_review_contents(self, source: str, draft: str, *, editable: bool) -> None:
        self._replace_text(self.source_text, source, editable=False)
        self._loading_draft = True
        self._replace_text(self.draft_text, draft, editable=editable)
        self.draft_text.edit_modified(False)
        self._draft_dirty = False
        self._loading_draft = False

    @staticmethod
    def _replace_text(widget: tk.Text, value: str, *, editable: bool) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        widget.configure(state=tk.NORMAL if editable else tk.DISABLED)

    def _on_draft_modified(self, _event: tk.Event[tk.Misc]) -> None:
        if self.draft_text.edit_modified():
            if not self._loading_draft and self._current_item is not None:
                self._draft_dirty = True
                self.status_var.set("下書きに未保存の変更があります")
            self.draft_text.edit_modified(False)

    def _save_current_draft(self, *, show_message: bool = True) -> bool:
        item = self._current_item
        if item is None:
            if show_message:
                messagebox.showwarning(
                    "下書きなし", "保存する下書きを選択してください。", parent=self.root
                )
            return False
        try:
            save_draft(item, self.draft_text.get("1.0", "end-1c"))
        except PipelineError as error:
            messagebox.showerror("保存エラー", str(error), parent=self.root)
            return False
        self._draft_dirty = False
        self.status_var.set("下書きを保存しました")
        if show_message:
            messagebox.showinfo("保存完了", "下書きを保存しました。", parent=self.root)
        return True

    def _confirm_discard_or_save(self) -> bool:
        if not self._draft_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "未保存の変更",
            "下書きに未保存の変更があります。保存してから切り替えますか？",
            parent=self.root,
        )
        if answer is None:
            return False
        if answer:
            return self._save_current_draft(show_message=False)
        self._draft_dirty = False
        return True

    def _publish_current(self) -> None:
        item = self._current_item
        if item is None:
            messagebox.showwarning(
                "下書きなし", "公開する下書きを選択してください。", parent=self.root
            )
            return
        if item.metadata.stage != "awaiting_human_review":
            messagebox.showwarning(
                "公開できません", "この下書きはすでに処理済みです。", parent=self.root
            )
            return
        push = self.push_var.get()
        action = "コミットしてGitHub Pagesへ公開" if push else "ローカルでコミット"
        confirmed = messagebox.askyesno(
            "最終レビューの確認",
            f"原文との照合と最終修正は完了しましたか？\n\n「{item.metadata.title}」を{action}します。",
            icon=messagebox.WARNING,
            parent=self.root,
        )
        if not confirmed:
            return
        if not self._save_current_draft(show_message=False):
            return
        draft = self.draft_text.get("1.0", "end-1c")
        settings = Settings.from_environment(self.repository, self._selected_provider())
        self._append_log(f"公開処理を開始: {item.metadata.title}")
        self._run_task(
            lambda: publish_reviewed_session(settings, item.metadata.slug, draft, push=push),
            self._published,
        )

    def _published(self, result: object) -> None:
        if not isinstance(result, PublicationResult):
            raise TypeError("公開結果が不正です。")
        message = (
            "GitHub Pagesの公開処理を開始しました。" if result.pushed else "コミットしました。"
        )
        self._append_log(f"完了: {message} ({result.commit[:12]})")
        self.status_var.set(message)
        slug = result.article_path.stem
        self._refresh_sessions(select_slug=slug)
        messagebox.showinfo("公開処理完了", message, parent=self.root)

    def _retry_push(self) -> None:
        item = self._current_item
        if item is None or item.metadata.stage != "committed_not_pushed":
            messagebox.showwarning(
                "再push不可", "push待ちのセッションを選択してください。", parent=self.root
            )
            return
        if not messagebox.askyesno(
            "pushの確認", "現在のコミットをorigin/mainへpushしますか？", parent=self.root
        ):
            return
        settings = Settings.from_environment(self.repository, self._selected_provider())
        self._run_task(
            lambda: push_committed_session(settings, item.metadata.slug),
            lambda _result: self._push_completed(item.metadata.slug),
        )

    def _push_completed(self, slug: str) -> None:
        self.status_var.set("GitHub Pagesの公開処理を開始しました")
        self._refresh_sessions(select_slug=slug)
        messagebox.showinfo(
            "push完了",
            "origin/mainへpushしました。GitHub Pagesの処理が開始されます。",
            parent=self.root,
        )

    def _open_original(self) -> None:
        if self._current_item is None:
            return
        webbrowser.open(self._current_item.metadata.original_url)

    def _update_review_actions(self) -> None:
        stage = self._current_item.metadata.stage if self._current_item else ""
        _set_widget_enabled(self.open_original_button, self._current_item is not None)
        if stage == "awaiting_human_review":
            _set_widget_enabled(self.save_button, True)
            _set_widget_enabled(self.publish_button, True)
        else:
            _set_widget_enabled(self.save_button, False)
            _set_widget_enabled(self.publish_button, False)
        _set_widget_enabled(self.push_button, stage == "committed_not_pushed")

    def _save_settings(self) -> None:
        try:
            self._persist_settings()
        except (PipelineError, ValueError, OSError) as error:
            messagebox.showerror("設定エラー", str(error), parent=self.root)
            return
        self._refresh_key_statuses()
        self.status_var.set("設定を恒久保存しました")
        messagebox.showinfo(
            "設定完了", "設定をWindowsユーザー環境変数へ保存しました。", parent=self.root
        )

    def _persist_settings(self) -> None:
        for provider, name in PROVIDER_KEYS.items():
            value = self.key_vars[provider].get().strip()
            if value:
                write_user_environment(name, value)
                self.key_vars[provider].set("")
        write_user_environment("TRANSLATE_REVIEW_PROVIDER", self._selected_provider())
        script = self.script_var.get().strip()
        if script:
            write_user_environment("TRANSLATE_PLAMO_SCRIPT", script)

    def _refresh_key_statuses(self) -> None:
        for provider, name in PROVIDER_KEYS.items():
            if read_user_environment(name):
                status = "恒久保存済み"
            elif os.environ.get(name):
                status = "この起動中のみ"
            else:
                status = "未設定"
            self.key_status_vars[provider].set(status)

    def _selected_provider(self) -> str:
        try:
            return PROVIDER_BY_LABEL[self.provider_var.get()]
        except KeyError as error:
            raise PipelineError("校閲サービスを選択してください。") from error

    def _delete_key(self, provider: str) -> None:
        label = PROVIDER_LABELS[provider]
        if not messagebox.askyesno(
            "APIキーを削除", f"{label}の恒久保存されたAPIキーを削除しますか？", parent=self.root
        ):
            return
        delete_user_environment(PROVIDER_KEYS[provider])
        self.key_vars[provider].set("")
        self._refresh_key_statuses()
        self.status_var.set(f"{label}のAPIキーを削除しました")

    def _browse_script(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="PLaMo起動スクリプトを選択",
            filetypes=(("PowerShellスクリプト", "*.ps1"), ("すべてのファイル", "*.*")),
        )
        if selected:
            self.script_var.set(selected)

    def _run_task(
        self,
        task: Callable[[], object],
        on_success: Callable[[object], None],
        *,
        show_error: bool = True,
    ) -> None:
        if self._busy:
            if show_error:
                messagebox.showinfo(
                    "処理中", "現在の処理が終わるまでお待ちください。", parent=self.root
                )
            return
        self._busy = True
        self._success_callback = on_success
        self._show_task_error = show_error
        self._set_busy(True)

        def worker() -> None:
            try:
                result = task()
            except Exception as error:
                self.events.put(("error", error))
            else:
                self.events.put(("success", result))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "success":
                    self._finish_task()
                    callback = self._success_callback
                    self._success_callback = None
                    if callback is not None:
                        callback(payload)
                elif kind == "error":
                    self._finish_task()
                    self._success_callback = None
                    self._handle_task_error(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _finish_task(self) -> None:
        self._busy = False
        self._set_busy(False)

    def _handle_task_error(self, payload: object) -> None:
        message = str(payload)
        self._append_log(f"エラー: {message}")
        self.status_var.set("処理に失敗しました")
        if not self._show_task_error:
            self.server_status_var.set("PLaMo 2: 未接続")
            self.server_status_label.configure(style="StatusError.TLabel")
            return
        messagebox.showerror("処理エラー", message, parent=self.root)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.start(12)
            for button in self._action_buttons:
                _set_widget_enabled(button, False)
        else:
            self.progress.stop()
            self.progress.configure(value=0)
            for button in self._action_buttons:
                _set_widget_enabled(button, True)
            self._update_review_actions()

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message.rstrip() + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        if self._busy and not messagebox.askyesno(
            "処理中",
            "処理中に閉じると、現在の作業が完了しない場合があります。閉じますか？",
            parent=self.root,
        ):
            return
        if not self._confirm_discard_or_save():
            return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        load_persistent_environment()
        repository = find_repository()
        TranslationGui(root, repository)
    except Exception as error:
        root.withdraw()
        messagebox.showerror("起動エラー", str(error), parent=root)
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
