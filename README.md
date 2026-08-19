## このリポジトリについて
このリポジトリには、翻訳済みの記事・論文・メモを統合し、Markdown 化したうえで `mkdocs` で公開するための構成が含まれています。

URLから記事本文を推定し、ローカルの PLaMo 2 translate で英日翻訳したあと、クラウドLLMで常体化と対訳校閲を行うパイプラインも含まれます。人間が下書きを最終確認して明示的に承認するまで、公開ファイルは変更されません。

## 翻訳パイプライン

### GUIで使う（推奨）

初回セットアップ後は、[start-translation-gui.vbs](./start-translation-gui.vbs) をダブルクリックしてください。ターミナルを開かずに「翻訳記事パイプライン」が起動します。

GUIでは次の操作を行えます。

1. 「設定」でCerebras、さくらのAI Engine、OpenRouterのAPIキーをWindowsユーザー環境変数へ恒久保存する。
2. 「PLaMoを起動」で `C:\Users\UserName\Documents\llama.cpp\scripts\pl2.ps1` を実行し、ポート3002への接続を確認する。
3. 「新規翻訳」で記事URL、カテゴリ、校閲サービスを選び、下書きを作成する。
4. 「レビュー・公開」で原文と訳文を比較しながら訂正し、下書きを保存する。
5. 最終確認後、「GitHubへpushして公開」を有効にしたまま公開すると、記事・索引を追加してGitHub Pagesの公開処理を開始する。

APIキーは入力中だけ伏せ字で表示し、保存済みの値を画面やログへ再表示しません。公開操作には確認画面があり、明示的に承認するまでコミットやpushは行いません。

### 1. 初回セットアップ

Python 3.11以降と Git、llama.cpp の `llama-server` が必要です。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

この環境ではポート8080をNicoCache_nlが使用しているため、PLaMo 2 translateのOpenAI互換APIにはポート3002を使います。設定済みの起動スクリプトを実行してください。

```powershell
& C:\Users\UserName\Documents\llama.cpp\scripts\pl2.ps1
```

パイプラインの既定接続先は `http://127.0.0.1:3002/v1` です。別のポートで起動する場合は、`TRANSLATE_TRANSLATOR_URL` で接続先を上書きできます。上段は現在のPowerShellだけ、下段はWindowsユーザー環境変数への恒久設定です。

```powershell
$env:TRANSLATE_TRANSLATOR_URL = "http://127.0.0.1:任意のポート/v1"
[Environment]::SetEnvironmentVariable("TRANSLATE_TRANSLATOR_URL", "http://127.0.0.1:任意のポート/v1", "User")
```

翻訳には、PLaMo 2 translateの公式モデルカードに記載された非チャット用プロンプト形式と、llama.cppの `/v1/completions` を使用します。

### 2. 校閲APIキー

通常はGUIの「設定」から保存してください。CLIを使う場合は、利用するサービスのキーをPowerShellの環境変数へ設定します。キーをファイルへ書き込んだり、Gitへコミットしたりしないでください。

#### 一時的に設定する

次の `$env:` を使う方法は、現在のPowerShellと、そこから起動したプロセスでだけ有効です。PowerShellを閉じると設定は失われます。

```powershell
# Cerebrasを使う場合
$env:CEREBRAS_API_KEY = "取得したAPIキー"

# さくらのAI Engineを使う場合
$env:SAKURA_AI_API_KEY = "取得したAPIキー"

# OpenRouterのFree Models Routerを使う場合
$env:OPENROUTER_API_KEY = "取得したAPIキー"
```

#### 恒久的に設定する（推奨）

毎回入力したくない場合は、Windowsのユーザー環境変数として保存します。利用するサービスの行だけを実行してください。

```powershell
# Cerebrasを使う場合
[Environment]::SetEnvironmentVariable("CEREBRAS_API_KEY", "取得したAPIキー", "User")

# さくらのAI Engineを使う場合
[Environment]::SetEnvironmentVariable("SAKURA_AI_API_KEY", "取得したAPIキー", "User")

# OpenRouterのFree Models Routerを使う場合
[Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", "取得したAPIキー", "User")
```

既定の校閲サービスも固定する場合は、`cerebras`、`sakura`、`openrouter` のいずれかを設定します。これにより、通常は `prepare` の `--review-provider` を省略できます。

```powershell
[Environment]::SetEnvironmentVariable("TRANSLATE_REVIEW_PROVIDER", "openrouter", "User")
```

設定後は、開いているPowerShellやCodexをいったん閉じ、新しく起動してください。値そのものを画面へ表示せず、設定の有無だけを確認するには次を実行します。

```powershell
"CEREBRAS_API_KEY", "SAKURA_AI_API_KEY", "OPENROUTER_API_KEY", "TRANSLATE_REVIEW_PROVIDER" |
  ForEach-Object {
    $value = [Environment]::GetEnvironmentVariable($_, "User")
    "{0}: {1}" -f $_, $(if ($value) { "設定済み" } else { "未設定" })
  }
```

恒久設定を削除する場合は、値に `$null` を指定します。

```powershell
[Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", $null, "User")
[Environment]::SetEnvironmentVariable("TRANSLATE_REVIEW_PROVIDER", $null, "User")
```

ユーザー環境変数は同じWindowsユーザーで動くプロセスから読み取れるため、共有PCでは取り扱いに注意してください。

校閲モデルは次の通り解決します。CerebrasとさくらのAI Engineは認証付きの `GET /v1/models` から毎回のプロセスで利用可能モデルを発見し、音声・埋め込みモデルを除外して安定順で選びます。特定モデルへ固定する場合だけ、対応する環境変数で上書きします。

| プロバイダー | 既定モデル | 上書き用環境変数 |
| --- | --- | --- |
| Cerebras | `GET /v1/models` から自動選択 | `CEREBRAS_MODEL` |
| さくらのAI Engine | `GET /v1/models` から自動選択 | `SAKURA_AI_MODEL` |
| OpenRouter | `openrouter/free` | `OPENROUTER_MODEL` |

OpenRouterの `openrouter/free` は、リクエストごとに利用可能な無料モデルを自動選択します。無料枠はレート制限・可用性・出力品質が一定ではありません。また、選ばれたプロバイダーによって入力と出力が記録・学習利用される場合があるため、秘密情報や未公開情報を含む記事には使用しないでください。

### 3. 下書きの生成

```powershell
translate-article prepare "https://example.com/article" --category Essays --review-provider cerebras
```

`--review-provider` には `cerebras`、`sakura`、`openrouter` を指定できます。指定しない場合は `TRANSLATE_REVIEW_PROVIDER`、それも未設定なら `cerebras` を使います。

処理内容は次の通りです。

1. URLとリダイレクト先を検証し、Trafilaturaで記事本文・タイトル・著者・公開日を推定する。
2. Markdownを意味のあるまとまりへ分割し、コードブロックを除外してPLaMo 2 translateで翻訳する。
3. 選択したクラウドLLMへ原文と訳文を渡し、1回の校閲で敬体から常体への統一、誤訳・訳抜け・過剰な補足の修正を行う。
4. `.translation-work/<slug>/draft.md` に、人間のレビュー待ち下書きを保存する。

クラウドAPIは翻訳チャンクごとに1回呼び出します。既定の3,500文字分割なら約98,000文字の記事で約29回となり、OpenRouter無料アカウントの公開上限である50リクエスト/日に収まりやすい構成です。記事の構造や長さによって呼び出し回数は変わります。

クラウドLLMによる常体化・校閲では記事本文が選択したサービスへ送信されます。各サービスの利用規約、データ保持、料金を確認してから実行してください。

### 4. 人間による最終レビュー

```powershell
translate-article review <slug>
```

既定のエディターで `draft.md` が開きます。隣に保存される `source.md` と原文URLを照合し、タイトル、固有名詞、数値、リンク、訳抜け、文体を確認・修正してください。

### 5. 公開

```powershell
translate-article publish <slug>
```

最終レビュー済みであることを確認したあと、次を自動実行します。

- `docs/articles/<slug>.md` を追加
- `docs/index.md` と `mkdocs.yml` の選択カテゴリへリンクを追加
- `CHANGELOG.md` へ追加内容を記録
- `mkdocs build --strict` で公開物を検証
- 対象4ファイルだけを日本語Conventional Commits形式でコミット
- `origin/main` へpushし、既存のGitHub Pagesワークフローを開始

ビルドまたはコミットに失敗した場合は公開ファイルを実行前へ戻します。pushだけに失敗した場合、コミットは保持されるため次で再試行できます。

```powershell
translate-article push <slug>
```

動作確認だけでpushしたくない場合は `publish <slug> --no-push` を指定します。

### 制約

- ログイン必須ページ、JavaScriptでのみ本文を描画するページ、PDFはURLから直接抽出できません。
- ローカル・プライベート・予約済みIPへのアクセスは既定で拒否します。信頼できるイントラネット記事だけ、`--allow-private-url` で明示的に許可できます。
- 著作権、翻訳公開の許諾、引用要件は自動判定できません。公開前の人間レビューで確認してください。
- PLaMo Community Licenseの公開出力に関する表示要件を満たすため、生成記事にはPLaMo 2 translateの出力を使った旨を記載します。この表示を削除した下書きは公開できません。

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

## 公開
`main` ブランチへ push すると `.github/workflows/pages.yml` で GitHub Pages 用のサイトをビルド・公開します。

## GitHub Pages
<https://roflsunriz.github.io/translate-misc/>

## ライセンス
[MIT ライセンス](./LICENSE)

## 依存更新の自動処理

Dependabot は対象の依存関係を毎週確認します。patch／minor 更新は PR のチェック（CI）が成功した後に自動で squash merge されます。CI の失敗ジョブは 1 回だけ再実行します。再失敗した PR は残して手動で修正します。major 更新は手動で確認します。マージ後はデプロイ workflow を明示起動します。
