# 調査知見

- YouTube自動字幕は固有名詞・専門用語の誤認識が多く、全文翻訳の正本にしない。Whisper Desktopでは英語固定、翻訳なし、CUDA、`ggml-large-v3-turbo-q8_0`、16kHzモノラルPCM WAV、SRT出力を使う。
- 長時間SRTは無音・拍手付近で連続反復や0秒区間を生じ得る。元SRTを保存し、重複・話者名・公式表記を補正し、欠落は動画と別文字起こしで照合する。
- `pl2.ps1` の `ContextSize=4096` と `Parallel=32` では各要求が256トークン相当になった。長文翻訳時だけ専用サーバーを `Parallel=1`、`ContextSize=8192` で起動し、終了後は元設定へ戻す。
- 2026-10-19の実測では、さくらAI Engineの対象モデルは対訳校閲で説明や捏造を混ぜ、OpenRouter freeは長文本文が空になった。別案件へ流用せず、実チャンクで再試験する。今回の正本はPLaMO 2 translate初稿と原文対照校閲。
