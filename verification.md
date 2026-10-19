# 検証手順

## Dependabot 自動処理（2026-09-23）

`.github/workflows/dependabot-automation.yml` を actionlint で検査し、PR 用 workflow 名（CI）と一致することを確認する。Dependabot の patch／minor かつ全 PR チェック成功の場合だけ取り込み、major・古い SHA・再失敗は残す。

実際の Dependabot PR がまだない場合、動作経路は未検証として扱う。実 PR 発生後に自動化ジョブ、CI の再試行、マージ結果を確認する。

大量の Dependabot PR により CI 完了より分類が遅れる場合でも、分類後の `workflow_dispatch` が現在の PR 番号と head SHA を照合して再評価する。別の作成者、古い SHA、未完了の CI はマージしない。

## 2026-10-05: GitHub受付・READMEの整備（公開前）

- 比較元: `71b2813b397c7283d363210a2c62f9d36b1ce098`（`main`）。
- 受付フォーム 2 件のYAML構造、重複キー・ID、入力型、選択肢、予約ファイル名を一括検査し、エラー0件。
- 既存の固有質問・入力例・必須条件を原文と照合。READMEのリンク・画像・コマンド・条件を確認し、裏付けがある誤記だけを訂正した。
- 既存のCI、Dependabot、labeler、ライセンスのファイル内容は比較元から変更していない。
- 製品のビルド・インストール・実機操作、GitHub上のフォーム表示、公開後CIは今回の静的検証に含めない。公開後に実際の受付表示と必要ラベルの適用を確認する。

## 2026-10-16: findings.mdへの知見分離

- AGENTS・READMEなどから移した本文を移行前のGit内容と照合し、条件・確認日・コマンド・未検証事項を保持する。移動先の参照とMarkdownの見出し・コードブロックを確認する。
- 変更範囲は文書の配置と参照。アプリのビルド・実機動作を今回再検証したとは扱わない。

- 実行結果: 移行前本文と移動後の文書を行単位で照合し、本文の欠落0件。変更文書の相対リンク・見出し参照の新規エラー0件、git diff --check成功。共通指針の記録先変更は意味の整合を別途確認した。
- GitHub上の既存Dependabot open alertsは0件。更新PRは0件で、今回の文書移行とは別の状態として確認した。新規の外部監査送信は自動承認レビューの制限により実行せず、GitHub上の既存警告確認で補完した。これはローカル依存監査・最新版照会の成功を意味しない。

## 2026-10-19: IMF動画講演の翻訳下書き

- IMF公式動画（81分45秒）の16kHz・モノラルPCM音声をWhisper Desktopの `ggml-large-v3-turbo-q8_0`、英語固定、CUDA、翻訳なしでSRT化した。904区間、開始00:00:00、終了01:21:23、文字化け0件を確認した。
- 元SRTを保持し、同一文の連続反復59件と重複した話者紹介1件を除外した。欠落したV. Anantha Nageswaran氏の導入部は動画と別の文字起こしで照合し、公式プログラムで話者名・役職を確認した。補正版は844区間、主要部8見出し、話者22見出し、動画時刻リンク30件となった。
- PLaMO 2 translateで44チャンクを翻訳した。さくらのAI Engineは長文校閲で指示外の解説と原文にない内容を生成し、OpenRouter無料ルーターは長文で本文が空の応答を返したため、いずれの出力も採用していない。Codexが補正版原文とPLaMO初稿を対照し、誤訳、訳抜け、数値、固有名詞、文体を修正した。
- 公開前の固有名詞監査では、IMF公式プログラム、AnthropicのモデルSystem Card・Claude Fable・Claude Corps、OpenAIのGPT-6 Astra・Jakub Pachockiによる「An Alien Mind」、Ant GroupのAnt A-Fu、TheoPhysEvalのarXiv論文、Boston UniversityとICBC Standard Bankの公式プロフィールを照合した。`alignment` は「アライメント」とし、一次資料で確認できない最初の会場質問者名は断定表記を削除した。
- レビュー用下書きは `.translation-work/inside-the-event-horizon/draft.md` に保存した。原文と訳文の主要見出し8件、話者見出し22件、時刻リンク30件が一致し、文字化け、未復元の保護記号、既知の誤訳語は0件だった。`mkdocs build --strict` と `git diff --check` は成功した。
- 公開承認前は下書きを `awaiting_human_review` のまま保持し、公開ファイルへのコピー、コミット、pushを行わなかった。利用者による原文との最終照合と明示的な公開指示を受けてから公開処理へ進む。
- 2026-10-19の公開承認後、`pip install --upgrade --upgrade-strategy eager -e ".[dev]"` で制約内の依存関係を更新した。`urllib3` は既知脆弱性3件のある2.7.0から修正版2.8.0へ更新され、`pip-audit` は既知脆弱性0件、`pip list --outdated` は更新候補0件、`pip check` は依存不整合0件となった。更新後にRuff、Ruff format、mypy、dmypy、pytest 41件、`mkdocs build --strict` が成功した。pytestとdmypyはWindowsサンドボックスが一時ディレクトリとNamed Pipeを制限するため、専用一時ディレクトリを指定して権限を広げた環境で再検証した。
- 公開コミット `aa0d816` を `origin/main` へpushした。GitHub ActionsのCI（run `39177253469`）とDeploy MkDocs（run `39177253323`）は成功した。公開URL `https://roflsunriz.github.io/translate-misc/articles/inside-the-event-horizon/` はHTTP 200を返し、記事タイトル、`Claude Mythos`、`アライメント`、`Ant A-Fu`、IMF公式動画リンク、PLaMO表示が実配信HTMLに含まれることを確認した。

## 2026-10-20: Dependabot 月末一括処理

- `.github/dependabot.yml` は毎月28日00:00、`.github/workflows/dependabot-automation.yml` は同日18:00（いずれも `Asia/Tokyo`）に設定した。呼び出し先は検証済み共通 workflow の固定 SHA とし、現在の head SHA、Dependabot の資格状態、全 PR チェック成功を merge 前に再確認する。
- YAML 構文、変更差分、空白エラーをローカルで検査した。実際の月末 schedule と Dependabot PR の merge 経路は、次回の毎月28日実行で確認する。
