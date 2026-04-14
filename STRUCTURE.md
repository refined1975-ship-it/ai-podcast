# CAST 構造ガイド

## 概要
CAST（デイリーAIラジオ）は、AI関連ニュースを毎日自動収集してポッドキャスト化するシステム。毎日 7:00 JST に LaunchAgent で起動し、ニュース取得→スクリプト生成→TTS音声化→RSS更新→GitHub Pages 配信まで全自動で行う。iOS PWA 対応の Web UI で再生可能。

## ディレクトリ構造

```
cast/
├── app.js                          # フロントエンド：プレイヤー・タブUI・キャッシュ管理
├── index.html                      # HTML テンプレート（PWA対応）
├── style.css                       # スタイルシート（暗色・レスポンシブ）
├── sw.js                           # Service Worker（キャッシュ戦略）
├── manifest.json                   # PWA マニフェスト
├── feed.xml                        # RSS 2.0 フィード（自動生成・日々更新）
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
```

## データフロー / アーキテクチャ

### ワークフロー全体

```
毎日 7:00 JST
  ↓
LaunchAgent ( ~/.local/bin/cast-daily.sh )
  ├─ Claude API (claude -p) で NEWS_FEEDS → スクリプト JSON生成
  ├─ pending_script.json に保存
  └─ local_generate.sh を呼ぶ
       ↓
local_generate.sh
  ├─ pending_script.json を読む（日付チェック・文字数チェック）
  ├─ generate.py --script で実行
  │   ├─ Edge TTS で JP 男女声をMP3に分割化
  │   ├─ ffmpeg で結合・再符号化（CBR 64kbps）
  │   ├─ feed.xml に <item> 追加
  │   └─ 7日以上前のエピソードを削除
  ├─ git commit & push
  ├─ GitHub Pages デプロイ確認（最大5分待機）
  └─ ローカルログ書き込み

毎日 8:00 JST
  ↓
daily-check.sh（ローカル監視、補完確認）
```

### ニュース収集パイプライン

```
generate.py --fetch-only
  ↓
NEWS_FEEDS (6つのRSSフィード)
  ├─ Google News (日本語＋英語)
  ├─ TechCrunch
  ├─ The Verge
  └─ arXiv (CS.AI, CS.LG)
  ↓
重複排除 (seen_titles)
  ↓
articles[] (最大 60 件)
```

### 音声生成パイプライン

```
pending_script.json (Claude生成)
  ↓
generate.py --script
  ├─ speaker (female/male) と text[] の配列
  └─ description（トピック・クレジット）
  ↓
Edge TTS (asyncio 並列化)
  ├─ 女性声: ja-JP-NanamiNeural (+15% 速度)
  ├─ 男性声: ja-JP-KeitaNeural (+15% 速度)
  ├─ 分割: _chunk_000.mp3, _chunk_001.mp3, ...
  └─ 各セグメント: ~1-5秒
  ↓
ffmpeg concat (複数MP3結合)
  ├─ -c copy で無損失結合
  └─ 再符号化: CBR 64kbps, 24kHz, Mono
  ↓
episode-YYYY-MM-DD.mp3 (~8-18 MB)
```

### フロントエンド (app.js)

```
index.html
  ├─ 2 タブ
  │  ├─ ラジオ（RSS フィードの episodes）
  │  └─ YouTube音声（YouTube チャンネル統合・開発中）
  │
  └─ Floating Player UI
     ├─ Mini bar（固定）
     ├─ Full player（オーバーレイ）
     └─ オーディオ要素（iOS対応：1つだけ）

キャッシュ戦略 (sw.js)
  ├─ MP3: cache-only（ユーザー主動DL）
  ├─ HTML/JS/CSS: network-first + cache fallback（オフライン対応）
  └─ CACHE_NAME = 'cast-v6'（バージョン管理）
```

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

### 設定ファイル

| ファイル | 役割 | 変更時の注意点 |
|---------|------|-------------|
| `CLAUDE.md` | このPJ特有の約束事 | launchd, permission-mode, TTS パラメータ記載 |
| `feed.xml` | RSS 2.0 フィード | 自動生成：手編集禁止 |
| `manifest.json` | PWA マニフェスト | icon path 正確に |

### 資産

| ファイル | 役割 | 変更時の注意点 |
|---------|------|-------------|
| `artwork.jpg` | Podcast artwork | 3000x3000px 推奨（Apple Podcasts） |
| `icon-*.png` | PWA アイコン | 192, 512px 両方必須 |

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

### ローカル依存

- `ffmpeg`, `ffprobe`: MP3 結合・符号化
- Python 3.7+
- `edge-tts`, `requests`, `beautifulsoup4`, `dateutil`: `requirements.txt`

### 外部スクリプト

- `~/.local/bin/cast-daily.sh`: LaunchAgent で毎日 7:00 呼ぶ
- `daily-check.sh`: 補完・監視用（8:00 実行）
- `claude -p`: 台本生成プロンプト実行（stdin 指定）

## 修正時の注意点

### RSS フィード周り

- `feed.xml` は **自動生成**（手編集禁止）→ `generate.py` の `update_feed()` を修正
- 古いエピソード削除ロジック: `MAX_EPISODE_AGE_DAYS = 7`
- ニュースソースクレジット: `get_source_names()` で自動生成

### 音声生成周り

- **TTS 品質**: VOICE_FEMALE, VOICE_MALE, RATE の変更で変わる
- **ファイルサイズ**: ffmpeg の `-b:a` (64k) を変更するとサイズ変動（最小 100KB チェックあり）
- **再符号化**: `-write_xing 0` は ID3 ヘッダ不具合対策（削除禁止）

### フロントエンド周り

- **iOS Safari 制約**: `audio` 要素は 1 つだけ（複数あるとバックグラウンド再生が壊れる）
- **play() 呼び出し**: 必ず `.catch()` で ユーザージェスチャ制約対応
- **Service Worker**: `CACHE_NAME` を変えない限り古いキャッシュが残る

### LaunchAgent / スクリプト周り

- **stdin 汚染**: `exec >> LOG 2>&1` で stdout リダイレクトすると stdin が /dev/null になる → `<` で台本ファイル渡す
- **バックグラウンド実行**: `&` 付きで呼ぶと stdin が /dev/null になる → 使わない
- **permission-mode**: `--permission-mode bypassPermissions` 必須

### Git/Deploy

- commit メッセージは `"Add episode for YYYY-MM-DD"` 固定
- `git push origin main` で GitHub Pages デプロイ
- デプロイ確認は最大 5 分（10 回 × 30 秒 sleep）

### テンプレート vs Claude 生成

- `pending_script.json` に `date` フィールドがあれば Claude 生成
- `date` がなければテンプレート（削除される）
- 文字数チェック: `< 1000` なら失敗

---

## Quick Reference

### ファイル追加・削除時の影響

| 変更 | 影響箇所 |
|------|--------|
| `scripts/generate.py` の `NEWS_FEEDS` | `generate_script()` の背景説明も更新必要 |
| `VOICE_FEMALE` or `VOICE_MALE` 変更 | TTS 出力品質・ファイルサイズ変動 |
| `MAX_EPISODE_AGE_DAYS` | feed.xml・audio/episodes/ の削除タイミング |
| `app.js` の `CACHE_NAME` | Service Worker キャッシュキー（変更時は古いキャッシュ削除） |
| `manifest.json` 更新 | PWA 再インストール必要（キャッシュ無効化） |
| `icon-*.png` 更新 | `create_icons.py` で再生成 |

### トラブルシューティング

| 症状 | 原因 | 対策 |
|------|------|------|
| MP3 生成失敗 | TTS API レート制限 | 時間をおいて再実行 |
| Deploy 確認タイムアウト | GitHub Pages ビルド遅延 | 手動確認 (`curl` で HTTP 200 確認) |
| iOS 再生できない | audio 要素複数存在 | app.js で1要素に統一 |
| Service Worker 古いキャッシュ残る | CACHE_NAME 変わらず | ブラウザキャッシュ手動削除 |
| 台本が短すぎる | Claude 生成失敗 | 1000 文字チェック→再トライ |

