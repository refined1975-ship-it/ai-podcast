# CAST
AI関連ニュース → claude -p 台本生成（失敗時はstock昇格） → Edge TTS → MP3 → GitHub Pages配信 → 次弾装填。LaunchAgent(7:00)→bin/daily.sh。

## 目的
AIの最前線を毎日インプットしたいが、長文記事を読む集中力が続かない。作業中・移動中に聴いて消化するためにポッドキャスト形式にした。「読む」ではなく「聴いて流す」ことで情報摂取のコストを下げる。

## ナビ
entry: bin/daily.sh
stack: Shell + Python 3(venv, edge-tts) + HTML/CSS/JS
ok: [bin/, scripts/, app.js, style.css, index.html]
skip: [audio/, feed.xml, artwork.jpg]
test: null
git: true
tasks:
  台本プロンプト: bin/daily.sh (PROMPT_FILEヒアドキュメント + Step 4バリデーション)
  ニュースフィード: scripts/generate.py (NEWS_FEEDS + generate_script)
  音声パイプライン: scripts/generate.py
  フロントエンド: [app.js, style.css, index.html]
  フィードスキーマ: scripts/generate.py update_feed()
  LaunchAgent: plist変更後 launchctl bootout→bootstrap→list
  stock操作: scripts/stock_script.json（配信後バックグラウンド生成・手動削除でリセット可）

## 制約（変えるな）
- feed.xml手編集禁止: generate.pyのupdate_feed()が自動生成・管理する。手編集すると次回生成時に上書きされ消える
- ffmpeg -write_xing 0 削除禁止: ID3ヘッダ不具合対策。消すとApple Podcastsで再生位置がずれる
- audioタグ1要素のみ: iOS Safariバックグラウンド再生が壊れる。複数要素に「改善」しない
- bin/daily.shにexec >> LOG 2>&1を入れるな: stdinが/dev/nullになりclaudeに台本が渡らない。ログ集約したくても別手段を取ること
- claude -p は台本生成専用（fetch-only → pending_script.json まで）。TTS・git・deployをプロンプトに含めるな。
  理由: claudeセッション内の失敗はdaily.shから検知不能。ステップが増えるほど沈黙する障害点が増える。
  2026-04に「claude: command not found」で2日間サイレント失敗した実例あり。
  統合したくなったら: 先にこのCLAUDE.mdの制約を消す理由を書いてからにすること
- claude -p リトライは daily.sh 内で完結させる: 外部cronやLaunchAgent再起動で代替すると「失敗を検知してから」ではなく「時刻が来たら」の再実行になり、同日エピソード重複チェック（already exists）に依存した静かなスキップが増える
- 生成フロー（2026-04-28改訂）: try_generate()1回 → 失敗/短すぎ → stock昇格(date上書き) → stockなし → 30s後リトライ1回 → 全滅でexit 1。配信完了後バックグラウンドで翌日stock生成
- Step 4バリデーションに文字数チェックあり(exit 3 / 25,000文字未満): Claudeが生成中に自己修正するためのフィードバックループ。daily.shの20,000文字チェックと二重になっているが役割が違う（プロンプト内=Claude自己修正用、daily.sh側=最終安全弁）。どちらも消すな
- Step 4 exit 3フィードバックは数値付き（不足字数・per-entry目標・male行数）: 抽象的指示ではClaudeが展開量を判断できない。2026-04-28/29の2日連続失敗から得た教訓

## 負債
- generate.py 502行・多モード混在: --fetch-only/--script/no-args の3モードが1ファイルに同居。モード分岐は意図的設計（daily.shが直接呼び分ける）。test:null・本番ポッドキャストのため大規模分割は凍結。Promote: バグ修正で触るとき。s Divergent Change: 許容済み・再検査スルー
- daily.sh 385行・オーケストレータ: gen→validate→TTS→deploy→verify→prefetch の6ステップが1ファイルに同居。daily.shはステップを繋ぐ司令塔として意図的設計。分割するとステップ間の状態（exit code・ファイルパス）受け渡しが複雑化するため凍結。s Divergent Change: 許容済み・再検査スルー
