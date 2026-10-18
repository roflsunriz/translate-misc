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

## 動画講演の文字起こしと翻訳

- 2026-10-19確認: YouTubeの自動字幕は固有名詞と専門用語の誤認識が多いため、全文翻訳の正本にしない。このPCでは `%USERPROFILE%\Documents\whisper_desktop_release\whisper_desktop.exe` を使い、英語固定、翻訳なし、CUDA、`ggml-large-v3-turbo-q8_0`、SRT出力で文字起こしする。音声は `yt-dlp` と `ffmpeg` で16kHz・モノラルPCM WAVにすると入力できる。
- Whisper Desktopの長時間SRTでは、無音や拍手の周辺で同一文の連続反復やゼロ秒区間が生じることがある。元SRTを保存したまま、連続重複、話者名、公式プログラムで確認できる固有名詞を補正し、欠落区間は動画と別の文字起こしを照合してから翻訳する。
- `pl2.ps1` の `ContextSize=4096` と `Parallel=32` は同時処理向けであり、今回のllama-serverでは各要求の利用可能文脈が256トークンになった。長文翻訳時は起動スクリプト自体を変更せず、専用サーバーを `Parallel=1`、`ContextSize=8192` で一時起動し、終了後に `pl2.ps1` の設定へ戻す。
- 2026-10-19時点の実測では、さくらのAI Engineの `llm-jp-3.1-8x13b-instruct4` は長い対訳校閲で訳文以外の解説や原文にない内容を生成し、OpenRouterの `openrouter/free` は長文で本文が空の応答を返した。今回の動画ではPLaMO 2 translateの初稿を正本とし、Codexが原文対照で誤訳、訳抜け、数値、固有名詞、文体を校閲した。これらのモデル挙動は将来変わり得るため、別の長文で再利用する前に本文チャンクで試験する。
