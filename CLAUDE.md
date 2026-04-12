## CAST — AIニュースポッドキャスト
- GitHub Pages配信 (refined1975-ship-it/ai-podcast)
- 毎日 7:00 JST LaunchAgent (`~/.local/bin/cast-daily.sh`) → `claude -p` でスクリプト生成+TTS+push
- 7日で自動削除、8:00 JST にローカル監視 (`daily-check.sh`)
- ニュースソースのクレジットはgenerate.pyのNEWS_FEEDSから自動生成

## iOS Safari制約
- audio要素は1つだけ (複数だとiOSバックグラウンド再生が壊れる)
- play()は必ず.catch()

## コンテンツ方針
- 研究論文・技術展望を最優先。「何が起きた」より「こうなりそう」「こういう仕組み」
- 専門的であるほど面白い — 噛み砕いた解説付きで

## claude -p 注意点
- `exec >> "$LOG" 2>&1` を使わない — stdoutリダイレクトがstdinを汚染する
- `--permission-mode bypassPermissions` を付ける
- プロンプトはtmpファイルに書いてから `< "$PROMPT_FILE"` で渡す
- スクリプトを `&` 付きで呼ばない — バックグラウンドのstdinは /dev/null になる

## ワークフロー
- フロントエンド変更はpush前にローカルで動作確認する
- UIボタンに絵文字を使わない。SVGアイコンを使う
