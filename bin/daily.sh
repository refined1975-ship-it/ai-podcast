#!/bin/bash
# CAST daily AI radio generation
# LaunchAgent: com.vault.cast-daily (JST 7:00)
#
# 司令塔は本スクリプト。claude -p の責務は「pending_script.json 生成のみ」。
# TTS / git / push は本スクリプトが直接制御する。

set -euo pipefail
source "$HOME/claude/ops/config.sh"

LOG="$HOME/claude/logs/launchd/cast-daily.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

export PATH="$HOME/claude/ops/bin/util:$HOME/claude/ops/bin:$PATH"
SEND="$HOME/claude/apps/mascot/send-sock.sh"

log "=== START ==="
pstate start cast-daily || echo "[WARN] pstate failed" >&2

# Status file for widget (generating indicator)
STATUS_FILE="/tmp/cast-generating"
touch "$STATUS_FILE"
trap 'rm -f "$STATUS_FILE" "${PROMPT_FILE:-}"' EXIT

export PATH="$HOME/.nvm/versions/node/v24.15.0/bin:/usr/local/bin:$PATH"
cd "$HOME/claude/apps/cast"

# Ensure latest code
git pull origin main --no-edit >> "$LOG" 2>&1

TODAY=${CAST_DATE:-$(TZ=Asia/Tokyo date +%Y-%m-%d)}
PENDING="$HOME/claude/apps/cast/scripts/pending_script.json"

# Skip if already generated
if [ -f "audio/episodes/episode-${TODAY}.mp3" ] && grep -q "dair-${TODAY}" feed.xml 2>/dev/null; then
  log "Episode for $TODAY already exists. Skipping."
  pstate skip cast-daily "already generated today" || echo "[WARN] pstate failed" >&2
  exit 0
fi

# Stale pending_script.json (前回の残骸) を除去
rm -f "$PENDING"

# Load policy
CAST_POLICY=$(cat "$HOME/claude/apps/cast/policy.md")

# Build prompt file (claude -p に渡すのは「台本生成だけ」)
PROMPT_FILE=$(mktemp)

cat > "$PROMPT_FILE" <<PROMPT_END
You are the producer of 'AI蒸留ラジオ'. Working directory is ~/claude/apps/cast.
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

print(f'Script OK: encoding OK, {len(sections)} sections, no repeated content')
"
\`\`\`
If encoding fails: rewrite the corrupted parts.
If exit 2: locate the repeated phrases/topics across sections, rewrite those sections to eliminate repetition, then re-run this check.

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

log "Running claude -p (script generation only)..."
EXIT_CODE=0
claude -p --model sonnet --permission-mode bypassPermissions < "$PROMPT_FILE" >> "$LOG" 2>&1 || EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  log "claude -p failed (exit $EXIT_CODE)"
  pstate finish cast-daily "$EXIT_CODE" || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (claude exit $EXIT_CODE)" 2>/dev/null || true
  exit $EXIT_CODE
fi

# pending_script.json が生成されたか確認
if [ ! -f "$PENDING" ]; then
  log "ERROR: pending_script.json not found after claude -p"
  pstate finish cast-daily 1 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (台本未生成)" 2>/dev/null || true
  exit 1
fi

# 台本日付が TODAY と一致するか確認（バックフィル含む）
SCRIPT_DATE=$(GUARD_FILE="$PENDING" python3 -c "import json,os; print(json.load(open(os.environ['GUARD_FILE'])).get('date',''))" 2>/dev/null || echo "")
if [ -z "$SCRIPT_DATE" ] || [ "$SCRIPT_DATE" != "$TODAY" ]; then
  log "ERROR: script date mismatch (got '$SCRIPT_DATE', expected '$TODAY')"
  pstate finish cast-daily 1 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (台本日付不一致)" 2>/dev/null || true
  exit 1
fi

# 台本文字数チェック（短すぎる台本を弾く）
SCRIPT_CHARS=$(python3 -c "import json; d=json.load(open('$PENDING')); print(sum(len(s.get('text','')) for s in d.get('script',[])))" 2>/dev/null) || {
  log "ERROR: failed to count script chars"
  pstate finish cast-daily 1 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (文字数計測エラー)" 2>/dev/null || true
  exit 1
}
if [ "${SCRIPT_CHARS:-0}" -lt 20000 ]; then
  log "ERROR: script too short (${SCRIPT_CHARS:-0} chars, minimum 20000)"
  pstate finish cast-daily 1 || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (台本短すぎ ${SCRIPT_CHARS:-0}文字)" 2>/dev/null || true
  exit 1
fi
log "Script length OK: $SCRIPT_CHARS chars"

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
MP3="$HOME/claude/apps/cast/audio/episodes/episode-${TODAY}.mp3"
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
SCRIPTS_ARCHIVE="$HOME/claude/apps/cast/audio/scripts"
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
  pstate finish cast-daily "$GIT_EXIT" || echo "[WARN] pstate failed" >&2
  bash "$SEND" zundamon "face:surprised\nsay:CAST 失敗 (git exit $GIT_EXIT)" 2>/dev/null || true
  exit $GIT_EXIT
fi

log "=== END (exit: 0) ==="
pstate finish cast-daily 0 || echo "[WARN] pstate failed" >&2
