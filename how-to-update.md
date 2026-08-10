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
mypy translation_pipeline
pytest
pip-audit
mkdocs build --strict
```

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
