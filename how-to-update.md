# 更新手順

## 前提

- Python 3.11以降を利用する。
- 作業前に `git status --short --branch` で既存差分を確認する。
- APIキーや記事本文を含む `.translation-work/` をGitへ追加しない。

## 依存関係の更新

仮想環境を有効化し、依存関係を再インストールする。

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]" --upgrade
```

`pyproject.toml` のバージョン範囲を変更する場合は、採用パッケージの公式リリース、Python対応範囲、ライセンス、既知の非互換変更を確認する。

## API・モデル設定の更新

各サービスの公式ドキュメントと利用中アカウントのモデル一覧を確認し、既定値を変更する。

- llama.cpp: <https://github.com/ggml-org/llama.cpp/tree/master/tools/server>
- PLaMo 2 translate: <https://huggingface.co/pfnet/plamo-2-translate>
- Cerebras: <https://inference-docs.cerebras.ai/>
- さくらのAI Engine: <https://manual.sakura.ad.jp/api/cloud/ai-engine/inference.html>
- OpenRouter Free Models Router: <https://openrouter.ai/docs/guides/routing/routers/free-router>

モデル名は `translation_pipeline/config.py` の既定値とREADMEの表を同時に更新する。ローカルllama.cppのポートを変更する場合も、起動スクリプト、`translation_pipeline/config.py` の既定URL、README、設定テストを同時に更新する。キー名やAPI URLを変更する場合は、キーがログ、例外、テスト成果物へ出ないことも確認する。

## 検証

```powershell
ruff check .
ruff format --check .
mypy translation_pipeline tests
.\.venv\Scripts\dmypy.exe run -- translation_pipeline tests
pytest
pip-audit
mkdocs build --strict
```

GUIを変更した場合は、Windowsで `start-translation-gui.vbs` をダブルクリックし、次を確認する。

- ターミナルウィンドウを表示せず起動できる。
- 820×620以上のウィンドウで各タブ、入力欄、原文・下書き、操作ボタンを利用できる。
- APIキーの保存状態だけが表示され、値そのものは再表示・ログ出力されない。
- PLaMoの起動とポート3002への接続確認ができる。
- 下書きの切り替え時に未保存の変更を保存・破棄・キャンセルできる。
- 公開待ち、コミット済み、公開済みの状態に応じて保存・公開・再pushボタンが切り替わる。

実記事の翻訳やGitHubへのpushは外部通信と副作用を伴うため、UI検証では勝手に実行しない。公開可能なURLを使い、確認画面の内容を確認したうえで個別に実行する。

実APIを使う確認は費用と外部送信を伴うため、公開可能な短い記事だけで行う。次の三経路を個別に確認する。

```powershell
translate-article prepare "公開可能なURL" --review-provider cerebras
translate-article prepare "公開可能なURL" --review-provider sakura --slug sakura-check
translate-article prepare "公開可能なURL" --review-provider openrouter --slug openrouter-check
```

生成された各 `source.md` と `draft.md` を比較し、Markdown構造、URL、数値、常体、訳抜けを確認する。検証用セッションは `.translation-work/` 内にありGit管理外である。

## 復旧

- 下書き生成に失敗した場合は公開ファイルが変更されないため、原因を修正して別slugで再実行する。
- 公開のビルドまたはコミットに失敗した場合、パイプラインが対象ファイルを実行前へ戻す。`git status --short` で確認する。
- pushだけに失敗した場合はコミットを戻さず、`translate-article push <slug>` で再試行する。
- 誤った記事をすでにpushした場合は履歴を書き換えず、対象コミットを `git revert <commit>` で打ち消してmainへpushする。

## Dependabot PR の更新

前提は `.github/dependabot.yml` と PR 用 CI（CI）です。更新 PR の head SHA と `gh pr checks <PR番号>` の結果を確認してください。patch／minor は全チェック成功後に自動取り込みされます。初回 CI 失敗は failed jobs のみを 1 回再実行し、再失敗した PR は残して手動で修正します。

設定を変えたときは `actionlint .github/workflows/dependabot-automation.yml` と実際の PR の Actions 結果を確認します。問題があれば呼び出し先の共通 workflow SHA を直前の検証済み値へ戻すコミットを push します。取り込まれた依存更新に問題があれば通常の revert コミットで復旧します。

CI 完了より Dependabot の分類が遅れる場合は、`callback_workflow_file` が指す呼び出し側 workflow を `workflow_dispatch` し、同じ PR 番号・head SHA・全チェックを再確認する。呼び出し側のファイル名を変える際はこの入力も一緒に更新する。
