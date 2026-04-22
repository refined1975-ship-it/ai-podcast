# CAST
AI関連ニュース → claude -p 台本生成 → Edge TTS → MP3 → GitHub Pages配信。LaunchAgent(7:00)→bin/daily.sh。

## ナビ
entry: bin/daily.sh
ok: [bin/, scripts/, app.js, style.css, index.html]
skip: [audio/, feed.xml, artwork.jpg]
test: null
git: true
tasks:
  台本プロンプト: bin/daily.sh (PROMPT_FILEヒアドキュメント)
  ニュースフィード: scripts/generate.py (NEWS_FEEDS + generate_script)
  音声パイプライン: scripts/generate.py
  フロントエンド: [app.js, style.css, index.html]
  フィードスキーマ: scripts/generate.py update_feed()
  LaunchAgent: plist変更後 launchctl bootout→bootstrap→list

## 制約（変えるな）
- feed.xml手編集禁止: generate.pyのupdate_feed()が自動生成・管理
- ffmpeg -write_xing 0 削除禁止: ID3ヘッダ不具合対策
- audioタグ1要素のみ: iOS Safariバックグラウンド再生が壊れる
- bin/daily.shにexec >> LOG 2>&1を入れるな: stdinが/dev/nullになりclaudeに台本が渡らない
- claude -p は台本生成専用（fetch-only → pending_script.json まで）。TTS・git・deployをプロンプトに含めるな: 司令塔はdaily.sh、claudeセッション内の副作用を制御不能にしない

## 負債
- RemoteTrigger(trig_01DXPBow1Mw9mQqYK2rgoTZR)はdisabled: ローカルLaunchAgentで運用中
