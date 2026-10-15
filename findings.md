# プロジェクト固有の知見

共通指針と [AGENTS.md](AGENTS.md) を読んだ後、作業前にこの文書を全文読む。元の条件・確認日・未検証事項を保ったまま、固有の実現手段と再利用する知見を集約する。

## 共通指針の具体化と適用範囲

- 対象: 共通指針の「設計と実装方針」「検証」「更新手順」「ドキュメント」と、各節に明記した共通ルール。
- 理由・範囲: Pythonの翻訳パイプラインとMkDocsの公開資料を併せて管理する。共通の検証をRuff・mypy・pytest・pip-audit・strictサイトビルドで具体化する。記事の公開承認条件と利用者向け操作はREADMEのまま適用する。
- 代替手段・検証: 以下の実効コマンド・根拠を用い、[検証記録](verification.md) で成功・未検証を区別する。共通方針の完了条件やユーザーの明示指示は弱めない。

## READMEなどから移した開発・運用情報

## ローカル確認

```powershell
mkdocs serve --livereload --dirty
```

コードを変更した場合は次を実行します。

```powershell
ruff check .
ruff format --check .
mypy translation_pipeline tests
.\.venv\Scripts\dmypy.exe run -- translation_pipeline tests
pytest
pip-audit
mkdocs build --strict
```

## 依存更新の自動処理

Dependabot は対象の依存関係を毎週確認します。patch／minor 更新は PR のチェック（CI）が成功した後に自動で squash merge されます。CI の失敗ジョブは 1 回だけ再実行します。再失敗した PR は残して手動で修正します。major 更新は手動で確認します。マージ後はデプロイ workflow を明示起動します。

## 文書の役割

- [README.md](README.md): 利用開始と操作、利用者が知る必要のある制限。
- この文書: 固有の配置・ツール・実行手段・例外・再利用する調査知見。
- [verification.md](verification.md): 検証手順、実測結果、証拠、未検証事項。
- [how-to-update.md](how-to-update.md): 更新と復旧の手順。
