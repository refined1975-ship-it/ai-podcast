#!/bin/bash
# AI蒸留ラジオ - ローカル音声生成スクリプト
# リモートトリガーが生成した台本JSONからTTS→feed更新→pushまで行う

set -e

REPO_DIR="$HOME/claude/cast"
PENDING="$REPO_DIR/scripts/pending_script.json"
LOG="$REPO_DIR/scripts/generate.log"
TODAY=$(date +%Y-%m-%d)
BASE_URL="https://refined1975-ship-it.github.io/ai-podcast"

exec > "$LOG" 2>&1
echo "[$(date)] Starting local generate..."

cd "$REPO_DIR"

# 最新を取得
git pull origin main

# 台本がなければ終了
if [ ! -f "$PENDING" ]; then
    echo "[$(date)] FAIL: No pending script found. Exiting."
    exit 0
fi

# 台本の日付チェック
SCRIPT_DATE=$(python3 -c "import json; d=json.load(open('$PENDING')); print(d.get('date',''))")
if [ -n "$SCRIPT_DATE" ] && [ "$SCRIPT_DATE" != "$TODAY" ]; then
    echo "[$(date)] FAIL: Script date ($SCRIPT_DATE) does not match today ($TODAY). Removing stale script."
    rm -f "$PENDING"
    git add -A && git diff --cached --quiet || git commit -m "Remove stale script ($SCRIPT_DATE)" && git push origin main
    exit 0
fi

# 台本チェック
CHARS=$(python3 -c "import json; d=json.load(open('$PENDING')); print(sum(len(x['text']) for x in d['script']))")
echo "[$(date)] Script: ${CHARS} characters"
if [ "$CHARS" -lt 1000 ]; then
    echo "[$(date)] FAIL: Script too short (${CHARS} chars). Aborting."
    exit 1
fi

echo "[$(date)] Found pending script. Generating audio..."

# Claude台本かテンプレートかチェック（dateフィールドがあればClaude生成）
HAS_DATE=$(python3 -c "import json; d=json.load(open('$PENDING')); print('yes' if d.get('date') else 'no')")
if [ "$HAS_DATE" = "no" ]; then
    echo "[$(date)] SKIP: Template script (not Claude-generated). Removing."
    rm -f "$PENDING"
    exit 0
fi

# 音声生成
python3 scripts/generate.py --script "$PENDING"

# 音声チェック
MP3="$REPO_DIR/audio/episodes/episode-${TODAY}.mp3"
if [ ! -f "$MP3" ]; then
    echo "[$(date)] FAIL: MP3 not created."
    exit 1
fi
SIZE=$(stat -f%z "$MP3" 2>/dev/null || stat -c%s "$MP3" 2>/dev/null)
echo "[$(date)] MP3: ${SIZE} bytes"
if [ "$SIZE" -lt 100000 ]; then
    echo "[$(date)] FAIL: MP3 too small (${SIZE} bytes). Aborting."
    exit 1
fi

# feedチェック
if ! grep -q "dair-${TODAY}" "$REPO_DIR/feed.xml"; then
    echo "[$(date)] FAIL: Episode not found in feed.xml."
    exit 1
fi
echo "[$(date)] Feed: OK (episode ${TODAY} found)"

# 使用済み台本を削除
rm -f "$PENDING"

# commit & push
git add -A
git commit -m "Add episode for ${TODAY}"
git push origin main

# デプロイ確認 (最大5分待つ)
echo "[$(date)] Waiting for GitHub Pages deploy..."
for i in $(seq 1 10); do
    sleep 30
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/audio/episodes/episode-${TODAY}.mp3")
    if [ "$HTTP" = "200" ]; then
        echo "[$(date)] DEPLOY OK: episode-${TODAY}.mp3 is live (attempt ${i})"
        break
    fi
    echo "[$(date)] Deploy check ${i}/10: HTTP ${HTTP}"
done

if [ "$HTTP" != "200" ]; then
    echo "[$(date)] WARN: Deploy not confirmed after 5 min. May still be building."
fi

echo "[$(date)] Done!"
echo ""
echo "=== SUMMARY ==="
echo "Script:  ${CHARS} chars"
echo "Audio:   $(( SIZE / 1024 / 1024 )) MB"
echo "Feed:    OK"
echo "Deploy:  HTTP ${HTTP}"
echo "==============="
