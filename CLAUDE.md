# CAST 技術仕様書

## 変更後チェック
- cast-daily.sh を変更したら: `bash -n ~/.local/bin/cast-daily.sh` で構文チェック
- claude -p の呼び出しを変更したら: 手動で1回走らせて osascript 通知が来ることを確認
- LaunchAgent を変更したら: `launchctl bootout gui/$(id -u)/com.local.cast-daily && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.cast-daily.plist && launchctl list com.local.cast-daily` で exit 0 を確認

## コンテンツ方針
- 研究論文・技術展望を最優先。「何が起きた」より「こうなりそう」「こういう仕組み」
- 専門的であるほど面白い — 噛み砕いた解説付きで

## ワークフロー
- フロントエンド変更はpush前にローカルで動作確認する
- UIボタンに絵文字を使わない。SVGアイコンを使う


AI蒸留ラジオ（旧デイリーAIラジオ）。AI関連ニュースを毎日自動収集し、Claude AIが台本を生成、Edge TTSで音声化してGitHub Pagesで配信するポッドキャスト自動化システム。

## 概要

| 項目 | 内容 |
|------|------|
| リポジトリ | `refined1975-ship-it/ai-podcast` |
| 公開URL | `https://refined1975-ship-it.github.io/ai-podcast/` |
| 音声合成 | Microsoft Edge TTS（NanamiNeural / KeitaNeural、+15%速度） |
| 台本生成 | Claude CLI（claude -p） |
| 保持期間 | 7日（古いエピソードは自動削除） |

## アーキテクチャ

```
LaunchAgent (07:00 JST)
    │
    └─→ cast-daily.sh
            │
            ├─ claude -p → pending_script.json（台本生成）
            │
            └─→ local_generate.sh
                    │
                    ├─ pending_script.json 読み込み
                    ├─ generate.py --script → Edge TTS → ffmpeg concat → MP3
                    ├─ feed.xml 更新（RSS 2.0）
                    ├─ 7日超の古いエピソード削除
                    ├─ pending_script.json 削除
                    └─ git add + commit + push → GitHub Pages デプロイ
                          │
                          └─ デプロイ確認ループ（最大5分）
```

## ディレクトリ構造

```
cast/
├── app.js                          # フロントエンド：プレイヤー・タブUI・キャッシュ管理
├── index.html                      # HTML テンプレート（PWA対応）
├── style.css                       # スタイルシート（暗色・レスポンシブ）
├── sw.js                           # Service Worker（キャッシュ戦略）
├── manifest.json                   # PWA マニフェスト
├── feed.xml                        # RSS 2.0 フィード（自動生成・日々更新）
├── .nojekyll                       # Jekyll無効化
├── CLAUDE.md                       # このプロジェクトの注意点・パラメータ
│
├── audio/
│   └── episodes/                   # MP3 ファイルストレージ
│       ├── episode-2026-04-08.mp3
│       ├── episode-2026-04-09.mp3
│       └── ...（最大7日分、古いものは自動削除）
│
├── icons/
│   ├── artwork.jpg                 # Podcast artwork (3000x3000px)
│   ├── artwork.svg                 # ベクターロゴ
│   ├── favicon.svg                 # ブラウザアイコン
│   ├── icon-192.png               # PWA 192x192
│   └── icon-512.png               # PWA 512x512
│
└── scripts/
    ├── generate.py                 # メインパイプライン（RSS, TTS, cleanup）
    ├── local_generate.sh           # pending_script.json → MP3→push
    ├── create_artwork.py           # サムネイル自動生成スクリプト
    ├── create_icons.py             # アイコン生成スクリプト
    ├── test_topic.py               # トピック抽出テスト用
    ├── pending_script.json         # Claude生成の台本（generate.py の--script で消費）
    ├── requirements.txt            # Python 依存（requests, beautifulsoup4, edge-tts, dateutil）
    └── generate.log                # TTS 実行ログ

~/.local/bin/
├── cast-daily.sh ........... 台本生成 + local_generate.sh呼び出し
└── daily-check.sh .......... 08:00 生成完了監視
```

## 音声生成パイプライン（generate.py）

### ニュース取得（--fetch-only時）

| ソース | 件数 |
|--------|------|
| Google News (ja/en) | AIキーワード |
| TechCrunch AI | カテゴリ |
| The Verge AI | カテゴリ |
| arXiv cs.AI / cs.LG | 論文 |

各フィード最大10件、重複排除（seen_titles）。合計最大60件。

### 台本JSONフォーマット

```json
{
  "date": "YYYY-MM-DD",
  "description": "エピソード説明",
  "script": [
    {"speaker": "female", "text": "..."},
    {"speaker": "male",   "text": "..."}
  ]
}
```

目標25,000文字。不足時はフィラー会話を挿入。

### TTS処理

1. Edge TTS（asyncio）でチャンクMP3生成
2. ffmpegでconcat
3. CBR 64kbps / 24kHz / Mono に再符号化（`-write_xing 0`でID3ヘッダ問題対策）
4. ffprobeで再生時間取得

### ボイス

| 役割 | Voice ID | 速度 |
|------|---------|------|
| 女性 | ja-JP-NanamiNeural | +15% |
| 男性 | ja-JP-KeitaNeural | +15% |

## PWA構成

| ファイル | 役割 |
|---------|------|
| index.html | 2タブ（ラジオ / YouTube音声） |
| app.js | プレーヤー、feed.xml解析、SW連携、ローカルサーバー検索 |
| style.css | ダークモード（#0a0a0a） |
| sw.js | MP3=cache-only、HTML/JS/CSS=network-first |
| feed.xml | RSS 2.0（iTunes互換） |

### iOS Safari制約

- `<audio>` 要素は1つのみ（バックグラウンド再生のため）
- `play()` は必ず `.catch()` 付き
- silence unlock用の無音WAV data URI

### ローカルサーバー連携（YouTube音声タブ）

優先順位付きでサーバー探索: `192.168.10.14:8443` → `localhost:8443` → `localhost:8888`

## RSS フィード（feed.xml）

- チャンネル名: AI蒸留ラジオ（ブランド: 蒸留ラジオ）
- iTunes カテゴリ: Technology
- GUID形式: `dair-YYYY-MM-DD`
- pubDate: JST 23:00 → UTC変換
- description: トピックリスト + クレジット（`get_source_names()`で自動生成）
- **自動生成のため手編集禁止**。`generate.py` の `update_feed()` を修正すること
- 古いエピソード削除ロジック: `MAX_EPISODE_AGE_DAYS = 7`

## 配信プラットフォーム

| プラットフォーム | 状態 | 備考 |
|---|---|---|
| GitHub Pages | ✅ 稼働中 | `refined1975-ship-it.github.io/ai-podcast/` |
| Apple Podcasts | ✅ 承認済（2026-04-17） | 検索インデックス未反映、直リンクで聴取可 |
| Spotify | ✅ 承認済（2026-04-17） | 検索インデックス未反映、直リンクで聴取可 |

- RSS: `https://refined1975-ship-it.github.io/ai-podcast/feed.xml`
- feed.xmlにitunes:owner設定済み（refined1975@gmail.com）
- 番組説明にTTSクレジット＋AI生成免責を明記
- ブランド拡張設計: ジャンルプレフィックス方式（AI蒸留ラジオ / 経済蒸留ラジオ / ...）
- アートワーク: 3000×3000px JPEG、スマホサムネ最適化済み（create_artwork.py）

## 自動実行

```
~/Library/LaunchAgents/com.local.cast-daily.plist
  Hour=7, Minute=0

daily-check.sh: 08:00 JST（生成完了の監視）
```

### 冪等性・安全策

- `pending_script.json` の日付チェック（当日以外はstaleとして削除）
- 文字数チェック（1000文字未満なら失敗）
- MP3サイズチェック（100,000 bytes未満なら失敗）
- feed.xmlに当日GUIDが含まれるか確認
- `/tmp/cast-generating` フラグ（dash/collect.shがステータス判定に使用）

### テンプレート vs Claude 生成

- `pending_script.json` に `date` フィールドがあれば Claude 生成
- `date` がなければテンプレート（削除される）
- 文字数チェック: `< 1000` なら失敗

## 主要ファイル

### フロントエンド

| ファイル | 役割 | 変更時の注意点 |
|---------|------|-------------|
| `index.html` | PWA エントリポイント | メタタグ（PWA対応）、audio要素は1つだけ（iOS制約） |
| `app.js` | メイン UI・プレイヤー・API | `play().catch()` 必須、silence unlock 工夫 |
| `style.css` | レスポンシブデザイン | iPhone safe-area対応、暗色テーマ |
| `sw.js` | Service Worker キャッシュ | `CACHE_NAME` はバージョン管理 |
| `manifest.json` | PWA 設定 | start_url に /ai-podcast/ 指定 |

### バックエンド（Python）

| ファイル | 役割 | 変更時の注意点 |
|---------|------|-------------|
| `generate.py` | メインパイプライン | `NEWS_FEEDS` 追加は両方に（generate_script も対応必要） |
| `local_generate.sh` | 台本→MP3 フロー | `exec >> LOG` で stdin 汚染注意（CLAUDE.md 参照） |
| `pending_script.json` | Claude 生成台本 | `{"script": [...], "description": ""}` 形式固定 |

## 依存関係・外部連携

### 外部 API・サービス

| 連携先 | 用途 | 認証・レート制限 |
|--------|------|----------------|
| **Google News RSS** | AI ニュース収集 | なし、ただし高頻度アクセスで制限あり |
| **TechCrunch RSS** | テック記事 | なし |
| **The Verge RSS** | AI 記事 | なし |
| **arXiv RSS** | 研究論文 | なし、ただし高頻度で 403 |
| **Edge TTS** | 音声生成 | Azure Cognitive Services、無料（レート制限あり） |
| **GitHub Pages** | 配信ホスト | Git push でデプロイ |
| **Claude API** | 台本生成 | `claude -p` コマンド（ローカル） |

### Python依存

```
edge-tts          # Microsoft Edge TTS
requests          # HTTP
beautifulsoup4    # HTMLパース
python-dateutil   # 日付パース
lxml              # XMLパース
```

### ローカル依存

- `ffmpeg`, `ffprobe`: MP3 結合・符号化
- Python 3.7+

## git

リモート: `refined1975-ship-it/ai-podcast` (GitHub)、Git LFS設定済み

- commit メッセージは `"Add episode for YYYY-MM-DD"` 固定
- `git push origin main` で GitHub Pages デプロイ
- デプロイ確認は最大 5 分（10 回 × 30 秒 sleep）

## 修正時の注意点

### 音声生成周り

- **TTS 品質**: VOICE_FEMALE, VOICE_MALE, RATE の変更で変わる
- **ファイルサイズ**: ffmpeg の `-b:a` (64k) を変更するとサイズ変動（最小 100KB チェックあり）
- **再符号化**: `-write_xing 0` は ID3 ヘッダ不具合対策（削除禁止）

### フロントエンド周り

- **iOS Safari 制約**: `audio` 要素は 1 つだけ（複数あるとバックグラウンド再生が壊れる）
- **play() 呼び出し**: 必ず `.catch()` でユーザージェスチャ制約対応
- **Service Worker**: `CACHE_NAME` を変えない限り古いキャッシュが残る

### LaunchAgent / スクリプト周り

- **stdin 汚染**: `exec >> LOG 2>&1` で stdout リダイレクトすると stdin が /dev/null になる → `<` で台本ファイル渡す
- **バックグラウンド実行**: `&` 付きで呼ぶと stdin が /dev/null になる → 使わない
- **permission-mode**: `--permission-mode bypassPermissions` 必須

## Quick Reference

### ファイル変更時の影響

| 変更 | 影響箇所 |
|------|--------|
| `scripts/generate.py` の `NEWS_FEEDS` | `generate_script()` の背景説明も更新必要 |
| `VOICE_FEMALE` or `VOICE_MALE` 変更 | TTS 出力品質・ファイルサイズ変動 |
| `MAX_EPISODE_AGE_DAYS` | feed.xml・audio/episodes/ の削除タイミング |
| `app.js` の `CACHE_NAME` | Service Worker キャッシュキー（変更時は古いキャッシュ削除） |
| `manifest.json` 更新 | PWA 再インストール必要（キャッシュ無効化） |
| `icon-*.png` 更新 | `create_icons.py` で再生成 |

### 再生位置復元

`localStorage['cast_positions']` にURL別で再生位置を保存（2026-04-16実装）。

- pauseイベント: 即時保存（5秒以上再生済みの場合のみ）
- timeupdate: 5秒スロットルで保存
- startPlayback: `loadedmetadata` 後にシーク復元（末尾5秒前まで）
- ended: 位置クリア（次回は先頭から）
- ラジオ・YouTubeタブ両方に効く
- **注意**: YouTubeタブのURLはサーバーIPを含む。IP変更時は位置リセット

### トラブルシューティング

| 症状 | 原因 | 対策 |
|------|------|------|
| MP3 生成失敗 | TTS API レート制限 | 時間をおいて再実行 |
| Deploy 確認タイムアウト | GitHub Pages ビルド遅延 | 手動確認 (`curl` で HTTP 200 確認) |
| iOS 再生できない | audio 要素複数存在 | app.js で1要素に統一 |
| Service Worker 古いキャッシュ残る | CACHE_NAME 変わらず | ブラウザキャッシュ手動削除 |
| 台本が短すぎる | Claude 生成失敗 | 1000 文字チェック→再トライ |
| 途中から再生できない | 位置復元ロジックなし | app.js に Position Persistence 実装済み（2026-04-16） |

## コスト分析（2026-04-17調査）
- 実行: `claude -p --model sonnet`（毎日7:00 JST）
- 推定コスト: ~$0.40/回、~$12/月
- Gemini分離による半額化は可能だが、「記事選別→文脈理解→原稿構成」の一貫性が品質の源泉。現状維持推奨
- CAST/FEEDのRemoteTrigger（trig_01DXPBow1Mw9mQqYK2rgoTZR）はdisabled状態。ローカルLaunchAgentで運用中
