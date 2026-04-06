#!/bin/bash
# デイリーAIラジオ - ローカル音声生成スクリプト
# リモートトリガーが生成した台本JSONからTTS→feed更新→pushまで行う

set -e

REPO_DIR="$HOME/ai-podcast"
PENDING="$REPO_DIR/scripts/pending_script.json"
LOG="$REPO_DIR/scripts/generate.log"

exec > "$LOG" 2>&1
echo "[$(date)] Starting local generate..."

cd "$REPO_DIR"

# 最新を取得
git pull origin main

# 台本がなければ終了
if [ ! -f "$PENDING" ]; then
    echo "[$(date)] No pending script found. Exiting."
    exit 0
fi

echo "[$(date)] Found pending script. Generating audio..."

# 音声生成
python3 scripts/generate.py --script "$PENDING"

# 使用済み台本を削除
rm -f "$PENDING"

# commit & push
git add -A
git commit -m "Add episode for $(date +%Y-%m-%d)"
git push origin main

echo "[$(date)] Done!"
