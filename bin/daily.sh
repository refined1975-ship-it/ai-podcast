#!/bin/bash
# CAST daily AI radio generation
# LaunchAgent: com.vault.cast-daily (JST 7:00)
#
# 司令塔は本スクリプト。claude -p の責務は「pending_script.json 生成のみ」。
# TTS / git / push は本スクリプトが直接制御する。

set -euo pipefail
source "$HOME/claude/ops/config.sh"

LOG="$LAUNCHD_LOGS/com.vault.cast-daily.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

# macOS: GNU timeout not available; portable fallback
command -v timeout &>/dev/null || timeout() {
  local secs="$1"; shift
  "$@" &
  local _pid=$!
  ( sleep "$secs" && kill "$_pid" 2>/dev/null ) &
  wait "$_pid"
}

export PATH="$OPS/bin/util:$OPS/bin:$PATH"
SEND="$MASCOT_SEND"

log "=== START ==="
pstate start cast-daily || echo "[WARN] pstate failed" >&2

# Status file for widget (generating indicator)
STATUS_FILE="/tmp/cast-generating"
touch "$STATUS_FILE"
trap 'rm -f "$STATUS_FILE" "${PROMPT_FILE:-}"' EXIT

export PATH="$HOME/.nvm/versions/node/v24.15.0/bin:/usr/local/bin:$PATH"
cd "$APPS/cast"

TODAY=${CAST_DATE:-$(TZ=Asia/Tokyo date +%Y-%m-%d)}
PENDING="$APPS/cast/scripts/pending_script.json"

# Cleanup: stale pending_script.json + old pstate running flag (before any logic)
rm -f "$PENDING"
pstate reset cast-daily 2>/dev/null || true

# Ensure latest code
git pull origin main --no-edit >> "$LOG" 2>&1

# Skip if already generated
if [ -f "audio/episodes/episode-${TODAY}.mp3" ] && grep -q "dair-${TODAY}" feed.xml 2>/dev/null; then
  log "Episode for $TODAY already exists. Skipping."
  pstate skip cast-daily "already generated today" || echo "[WARN] pstate failed" >&2
  exit 0
fi

# Load policy
CAST_POLICY=$(cat "$APPS/cast/policy.md")

# Build prompt file (claude -p に渡すのは「台本生成だけ」)
PROMPT_FILE=$(mktemp)

cat > "$PROMPT_FILE" <<PROMPT_END
You are the producer of 'AI蒸留ラジオ'. Working directory is ${APPS}/cast.
Target date for this episode: ${TODAY} (use this date in the script JSON, not today's actual date).

Your ONLY job: produce \`scripts/pending_script.json\`. Do NOT run TTS, git, or deploy.
The orchestrator (bin/daily.sh) will handle audio generation, commit, and push after you finish.

## Step 1: Setup
\`\`\`bash
pip install --break-system-packages edge-tts requests beautifulsoup4 python-dateutil lxml 2>/dev/null
\`\`\`

## Step 2: Fetch news
\`\`\`bash
python3 scripts/generate.py --fetch-only
\`\`\`
Read the output carefully.

## Step 3: Write podcast script
Follow the policy below for topic selection and script style:

${CAST_POLICY}

Write to \`scripts/pending_script.json\`:
\`\`\`json
{
  "date": "YYYY-MM-DD",
  "script": [{"speaker": "female", "text": "..."}, ...],
  "description": "..."
}
\`\`\`

## Step 4: Validate script (encoding + duplicate topics + repeated phrases)
\`\`\`bash
python3 -c "
import json, sys, re
from collections import defaultdict

with open('scripts/pending_script.json') as f:
    text = f.read()

# --- Encoding check ---
bad = [c for c in text if c == '\ufffd']
if bad:
    print(f'ERROR: {len(bad)} replacement chars found', file=sys.stderr)
    sys.exit(1)
try:
    text.encode('utf-8')
except UnicodeEncodeError as e:
    print(f'ERROR: encoding issue: {e}', file=sys.stderr)
    sys.exit(1)

data = json.loads(text)
script = data.get('script', [])
TRANSITION = ['次のトピック', 'テーマです', '続いては', '次は', 'では次', 'トピックへ']

# --- Split script into topic sections ---
sections = []
current = []
for item in script:
    t = item.get('text', '')
    if any(p in t for p in TRANSITION) and current:
        sections.append(current)
        current = [t]
    else:
        current.append(t)
if current:
    sections.append(current)

# --- Check 1: duplicate topic introductions ---
STOPWORDS = {'this','that','with','from','have','will','more','also','into','than','they','said','using'}
def keywords(s):
    entities = set(re.findall(r'[A-Z][a-zA-Z]{1,}|[A-Z]{2,}', s))
    en = {w for w in re.findall(r'[a-zA-Z]{4,}', s.lower()) if w not in STOPWORDS}
    cjk = set(re.findall(r'[\u4e00-\u9fa5\u30a0-\u30ff\u3040-\u309f]{3,}', s))
    return frozenset(entities | en | cjk)

intros = [sec[0][:150] for sec in sections if sec]
topic_dups = []
for i in range(len(intros)):
    for j in range(i+1, len(intros)):
        ki, kj = keywords(intros[i]), keywords(intros[j])
        union = len(ki | kj)
        if union and len(ki & kj) / union >= 0.40:
            topic_dups.append((i+1, j+1, ki & kj))

# --- Check 2: repeated phrases across different sections ---
CHUNK = 25  # chars
phrase_map = defaultdict(list)
for sec_i, section in enumerate(sections):
    full_text = ' '.join(section)
    for start in range(0, len(full_text) - CHUNK + 1, 5):
        chunk = full_text[start:start+CHUNK]
        if re.search(r'[\u4e00-\u9fa5\u30a0-\u30ff\u3040-\u309f]', chunk):  # CJK含む
            phrase_map[chunk].append(sec_i)

phrase_dups = []
seen_reports = set()
for phrase, sec_ids in phrase_map.items():
    unique_secs = sorted(set(sec_ids))
    if len(unique_secs) >= 2:
        key = tuple(unique_secs)
        if key not in seen_reports:
            seen_reports.add(key)
            phrase_dups.append((phrase, unique_secs))

errors = 0
if topic_dups:
    for a, b, shared in topic_dups:
        print(f'DUPLICATE TOPIC: section {a} and {b} share: {shared}', file=sys.stderr)
    errors += 1

if phrase_dups:
    print(f'REPEATED PHRASES across sections ({len(phrase_dups)} patterns):', file=sys.stderr)
    for phrase, secs in phrase_dups[:5]:
        print(f'  「{phrase}」 in sections {secs}', file=sys.stderr)
    errors += 1

if errors:
    print('ERROR: Fix all repeated content before proceeding.', file=sys.stderr)
    sys.exit(2)

total_chars = sum(len(item.get('text', '')) for item in script)
if total_chars < 25000:
    deficit = 25000 - total_chars
    n = len(script)
    per_entry = (deficit // n + 1) if n else deficit
    male_lines = [i for i, item in enumerate(script) if item.get('speaker') == 'male']
    print(f'ERROR: script too short ({total_chars}/25000 chars). '
          f'Deficit: {deficit} chars across {n} entries ({per_entry} chars/entry on average). '
          f'There are {len(male_lines)} male lines — prioritize expanding those with technical depth, concrete examples, and real-world implications. '
          f'Each male utterance should be a substantive paragraph (300+ chars). '
          f'Rewrite pending_script.json with all entries expanded, then re-run this validation.', file=sys.stderr)
    sys.exit(3)

print(f'Script OK: encoding OK, {len(sections)} sections, no repeated content, {total_chars} chars')
"
\`\`\`
If encoding fails: rewrite the corrupted parts.
If exit 2: locate the repeated phrases/topics across sections, rewrite those sections to eliminate repetition, then re-run this check.
If exit 3: read the error message carefully — it shows the exact deficit in chars, the per-entry expansion target, and how many male lines to prioritize. Rewrite pending_script.json: expand every male utterance to 300+ chars with technical depth and concrete examples, then expand female lines to match. Re-run this check after rewriting.

When validation passes, STOP. Do not run TTS, git add, commit, or push. The orchestrator takes over.
PROMPT_END

# Inject recent episode topics to prevent duplication
RECENT_TOPICS=$(python3 -c "
import xml.etree.ElementTree as ET, re
tree = ET.parse('feed.xml')
for item in tree.findall('.//item'):
    t = item.find('title')
    d = item.find('description')
    if t is None or d is None: continue
    m = re.search(r'\d{4}-\d{2}-\d{2}', t.text or '')
    if not m: continue
    topics = re.findall(r'^- (.+)$', d.text or '', re.MULTILINE)
    if not topics:
        first = (d.text or '').split('\n')[0].strip()
        if first: topics = [first]
    if topics: print(f\"{m.group()}: {', '.join(topics)}\")
" 2>/dev/null || echo "")

if [ -n "$RECENT_TOPICS" ]; then
  cat >> "$PROMPT_FILE" <<DEDUP_END

## IMPORTANT: Topic deduplication
These topics were already covered in recent episodes. Do NOT select them or semantically similar topics:
$RECENT_TOPICS

Only revisit a topic if there is a genuinely NEW development (not the same story from a different source).
DEDUP_END
fi

STOCK="$APPS/cast/scripts/stock_script.json"

# 台本生成を1回試みる。失敗/短すぎ → stock 昇格 → stock なし → 1回リトライ
try_generate() {
  rm -f "$PENDING"
  if ! timeout 1500 bash -c "CLAUDE_PIPELINE_MODE=1 claude -p --model \"$CLAUDE_MODEL_SONNET\" --permission-mode bypassPermissions < \"$PROMPT_FILE\"" >> "$LOG" 2>&1; then
    return 1
  fi
  if [ ! -f "$PENDING" ]; then return 1; fi
  SCRIPT_DATE=$(GUARD_FILE="$PENDING" python3 -c "import json,os; print(json.load(open(os.environ['GUARD_FILE'])).get('date',''))" 2>/dev/null || echo "")
  if [ -z "$SCRIPT_DATE" ] || [ "$SCRIPT_DATE" != "$TODAY" ]; then return 1; fi
  SCRIPT_CHARS=$(python3 -c "import json; d=json.load(open('$PENDING')); print(sum(len(s.get('text','')) for s in d.get('script',[])))" 2>/dev/null || echo "0")
  if [ "${SCRIPT_CHARS:-0}" -lt 20000 ]; then return 1; fi
  return 0
}

log "Running claude -p (script generation only)..."
GEN_OK=false
SCRIPT_CHARS=0
USED_STOCK=false

if try_generate; then
  GEN_OK=true
  log "Script OK: ${SCRIPT_CHARS} chars"
else
  log "Script generation failed or too short (${SCRIPT_CHARS:-0} chars)"
  if [ -f "$STOCK" ]; then
    log "Promoting stock script (date → $TODAY)..."
    python3 -c "
import json
with open('$STOCK') as f:
    d = json.load(f)
d['date'] = '$TODAY'
with open('$PENDING', 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
" >> "$LOG" 2>&1
    SCRIPT_CHARS=$(python3 -c "import json; d=json.load(open('$PENDING')); print(sum(len(s.get('text','')) for s in d.get('script',[])))" 2>/dev/null || echo "0")
    log "Stock promoted: ${SCRIPT_CHARS} chars"
    GEN_OK=true
    USED_STOCK=true
  else
    log "No stock. Retrying in 30s..."
    sleep 30
    if try_generate; then
      GEN_OK=true
      log "Retry succeeded: ${SCRIPT_CHARS} chars"
    fi
  fi
fi

if [ "$GEN_OK" != "true" ]; then
  log "Script generation failed (no stock, retry failed, last: ${SCRIPT_CHARS:-0} chars)"
  pstate step cast-daily gen failed 1 || true
  pstate finish cast-daily 1 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (台本生成・stock なし)" 2>/dev/null || true
  exit 1
fi

pstate step cast-daily gen done || true
pstate step cast-daily validate done || true

log "Generating audio (TTS + feed.xml)..."
TTS_EXIT=0
python3 scripts/generate.py --script "$PENDING" >> "$LOG" 2>&1 || TTS_EXIT=$?

if [ $TTS_EXIT -ne 0 ]; then
  log "TTS failed (exit $TTS_EXIT)"
  pstate finish cast-daily "$TTS_EXIT" || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (TTS exit $TTS_EXIT)" 2>/dev/null || true
  exit $TTS_EXIT
fi

# 生成物確認
MP3="$APPS/cast/audio/episodes/episode-${TODAY}.mp3"
if [ ! -f "$MP3" ]; then
  log "ERROR: MP3 not created at $MP3"
  pstate finish cast-daily 1 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (MP3未生成)" 2>/dev/null || true
  exit 1
fi
if ! grep -q "dair-${TODAY}" feed.xml 2>/dev/null; then
  log "ERROR: feed.xml does not contain episode dair-${TODAY}"
  pstate finish cast-daily 1 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (feed未更新)" 2>/dev/null || true
  exit 1
fi

# 台本をアーカイブして削除
SCRIPTS_ARCHIVE="$APPS/cast/audio/scripts"
mkdir -p "$SCRIPTS_ARCHIVE"
cp "$PENDING" "$SCRIPTS_ARCHIVE/script-${TODAY}.json"
rm -f "$PENDING"

log "Committing and pushing..."
GIT_EXIT=0
{
  git add -A && \
  git commit -m "Add episode for ${TODAY}" && \
  git push origin main
} >> "$LOG" 2>&1 || GIT_EXIT=$?

if [ $GIT_EXIT -ne 0 ]; then
  log "git operation failed (exit $GIT_EXIT)"
  pstate step cast-daily publish failed "$GIT_EXIT" || true
  pstate finish cast-daily "$GIT_EXIT" || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (git exit $GIT_EXIT)" 2>/dev/null || true
  exit $GIT_EXIT
fi
pstate step cast-daily publish done || true

# Verify: GitHub Pages から MP3 が HTTP 200 で取れるか確認（最大5分待機）
CAST_URL="https://refined1975-ship-it.github.io/ai-podcast/audio/episodes/episode-${TODAY}.mp3"
log "Verifying deploy at $CAST_URL..."
pstate step cast-daily verify running || true
HTTP_CODE="0"
VERIFY_OK=false
for _vi in 1 2 3 4 5; do
  HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 "$CAST_URL" 2>/dev/null || echo "0")
  if [ "$HTTP_CODE" = "200" ]; then
    VERIFY_OK=true
    log "Verify OK: HTTP 200 (attempt $_vi)"
    break
  fi
  log "Verify attempt $_vi: HTTP $HTTP_CODE"
  [ "$_vi" -lt 5 ] && sleep 60
done

log "=== END ==="
if [ "$VERIFY_OK" = "true" ]; then
  pstate step cast-daily verify done || true
  pstate verify cast-daily || echo "[WARN] pstate failed" >&2
  bash "$SEND" tsumugi "face:happy\nsay:CAST 完了！配信OK" 2>/dev/null || true
else
  log "WARNING: deploy verify failed (HTTP $HTTP_CODE). Episode may appear soon."
  pstate step cast-daily verify failed || true
  pstate finish cast-daily 0 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 配信確認待ち" 2>/dev/null || true
fi

# --- 次弾装填（バックグラウンド）---
# 配信完了後、明日の日付で台本を先生成して stock_script.json に保存する。
# 次回実行時に今日の生成が失敗/短すぎた場合の即時フォールバックとして使用。
# nohup + disown で親プロセスから完全に切り離す（macOS互換）。
STOCK_TOMORROW=$(TZ=Asia/Tokyo date -v+1d +%Y-%m-%d)
STOCK_PROMPT=$(mktemp)
sed "s|${TODAY}|${STOCK_TOMORROW}|g" "$PROMPT_FILE" > "$STOCK_PROMPT" 2>/dev/null || true
nohup bash -c '{
  set +euo pipefail
  _log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [stock] $*" >> "$LOG"; }
  _log "次弾装填開始 (date=${STOCK_TOMORROW})"
  rm -f "$PENDING"
  if timeout 1500 bash -c "CLAUDE_PIPELINE_MODE=1 claude -p --model \"$CLAUDE_MODEL_SONNET\" --permission-mode bypassPermissions < \"$STOCK_PROMPT\"" >> "$LOG" 2>&1; then
    if [ -f "$PENDING" ]; then
      _sc=$(python3 -c "import json; d=json.load(open(\"$PENDING\")); print(sum(len(s.get(\"text\",\"\")) for s in d.get(\"script\",[])))" 2>/dev/null || echo "0")
      if [ "${_sc:-0}" -ge 20000 ]; then
        mv "$PENDING" "$STOCK"
        _log "装填完了: ${_sc}chars → stock_script.json"
      else
        _log "短すぎ (${_sc}chars)、stock 更新せず"
        rm -f "$PENDING"
      fi
    else
      _log "pending_script.json 未生成"
    fi
  else
    _log "claude -p 失敗、次回実行まで stock なし"
    rm -f "$PENDING"
  fi
  rm -f "$STOCK_PROMPT"
}' > /dev/null 2>&1 &
disown
