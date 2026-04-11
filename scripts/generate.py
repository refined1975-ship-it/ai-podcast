#!/usr/bin/env python3
"""デイリーAIラジオ - Podcast Generator

Fetches AI news from RSS feeds, generates a Japanese script,
converts to speech using Edge TTS, and updates the podcast RSS feed.
"""

import argparse
import asyncio
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import formatdate
from pathlib import Path
from time import mktime

import edge_tts
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

# Config
REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = REPO_ROOT / "audio" / "episodes"
FEED_PATH = REPO_ROOT / "feed.xml"
VOICE_FEMALE = "ja-JP-NanamiNeural"
VOICE_MALE = "ja-JP-KeitaNeural"
RATE = "+15%"
BASE_URL = "https://refined1975-ship-it.github.io/ai-podcast"
MAX_EPISODE_AGE_DAYS = 7

# AI News RSS feeds
NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+LLM+machine+learning&hl=en&gl=US&ceid=US:en",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://rss.arxiv.org/rss/cs.AI",
    "https://rss.arxiv.org/rss/cs.LG",
]

# URL → display name (deduplicated by name)
_SOURCE_NAMES = {
    "news.google.com": "Google News",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "arxiv.org": "arXiv",
}


def get_source_names() -> str:
    """Return comma-separated source names derived from NEWS_FEEDS."""
    from urllib.parse import urlparse
    seen = []
    for url in NEWS_FEEDS:
        host = urlparse(url).hostname or ""
        for domain, name in _SOURCE_NAMES.items():
            if domain in host and name not in seen:
                seen.append(name)
    return ", ".join(seen) if seen else "各種ニュースソース"


def fetch_news() -> list[dict]:
    """Fetch AI news from RSS feeds."""
    articles = []
    seen_titles = set()
    for feed_url in NEWS_FEEDS:
        try:
            resp = requests.get(feed_url, timeout=15, headers={"User-Agent": "DailyAIRadio/1.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "xml")
            # RSS <item> or Atom <entry>
            items = soup.find_all("item")[:10] or soup.find_all("entry")[:10]
            for item in items:
                title = item.find("title")
                if not title:
                    continue
                title_text = title.text.strip()
                if title_text in seen_titles:
                    continue
                seen_titles.add(title_text)
                pub_date = item.find("pubDate") or item.find("published") or item.find("updated")
                link = item.find("link")
                link_text = ""
                if link:
                    link_text = link.get("href") or link.text or ""
                    link_text = link_text.strip()
                articles.append({
                    "title": title_text,
                    "link": link_text,
                    "pub_date": pub_date.text.strip() if pub_date else "",
                })
        except Exception as e:
            print(f"Warning: Failed to fetch {feed_url}: {e}", file=sys.stderr)
    return articles


def generate_script(articles: list[dict]) -> list[tuple[str, str]]:
    """Generate a male-female dialogue podcast script.

    Returns list of (speaker, text) tuples.
    speaker is "female" (host/questions) or "male" (commentary/analysis).
    Target total chars: ~25,000 for ~60 minutes at +15% speed.
    """
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y年%m月%d日")

    script = []

    # Opening
    script.append(("female", f"こんばんは。{today}のデイリーAIラジオへようこそ。今日も注目のAIニュースをお届けします。"))
    script.append(("male", "よろしくお願いします。今日もいくつか面白いニュースが入ってきていますね。早速見ていきましょう。"))

    for i, article in enumerate(articles, 1):
        title = article["title"]
        clean_title = re.sub(r"\s*[-–—|]\s*[^-–—|]+$", "", title)

        # Female introduces the topic
        script.append(("female", f"{i}番目のトピックです。{clean_title}。これはどういうニュースですか？"))

        # Male explains in detail
        script.append(("male",
            f"はい。{clean_title}ということですが、"
            "これはAI業界にとって重要な動きだと思います。"
            "背景としては、この分野では各社が技術開発を加速させていて、"
            "競争が非常に激しくなっています。"
        ))

        # Female asks follow-up
        script.append(("female", "実際のところ、開発者や一般ユーザーにはどんな影響がありそうですか？"))

        # Male gives analysis
        script.append(("male",
            "短期的には、関連するサービスやツールの選択肢が増えるということですね。"
            "中長期的には、この技術が標準化されることで、"
            "ソフトウェア開発のワークフローそのものが変わる可能性があります。"
            "ただし、技術的な課題やコスト面での問題もまだ残っているので、"
            "すぐに全面的に置き換わるというわけではないと思います。"
        ))

        # Female wraps up topic
        script.append(("female", "なるほど、引き続き注目していきたいですね。"))

    # Closing
    script.append(("female", "以上が本日のデイリーAIラジオでした。お聴きいただきありがとうございました。"))
    script.append(("male", "また明日のエピソードでお会いしましょう。おやすみなさい。"))

    # Check total length and pad if needed
    total_chars = sum(len(text) for _, text in script)
    while total_chars < 25000:
        script.insert(-2, ("female", "ところで、最近のAI業界全体のトレンドとして、何か気になることはありますか？"))
        script.insert(-2, ("male",
            "そうですね。やはりエージェント型AIの進化が目覚ましいです。"
            "単にテキストを生成するだけでなく、ツールを使い、計画を立て、"
            "自律的にタスクを遂行できるAIが実用段階に入りつつあります。"
            "コーディング、リサーチ、データ分析など、"
            "知的労働のかなりの部分を自動化できる可能性が出てきています。"
            "一方で、AIの判断をどこまで信頼するか、"
            "人間のチェックをどの段階で入れるかという設計の問題は"
            "まだ業界としてベストプラクティスが確立されていません。"
        ))
        script.insert(-2, ("female",
            "たしかにそうですね。技術の進歩とガバナンスのバランスが"
            "ますます重要になってきていると感じます。"
        ))
        total_chars = sum(len(text) for _, text in script)

    return script


async def text_to_speech(script: list[tuple[str, str]], output_path: Path) -> None:
    """Convert dialogue script to speech using Edge TTS."""
    temp_files = []
    total = len(script)

    for idx, (speaker, text) in enumerate(script):
        voice = VOICE_FEMALE if speaker == "female" else VOICE_MALE
        temp_path = output_path.parent / f"_chunk_{idx:03d}.mp3"
        temp_files.append(temp_path)
        communicate = edge_tts.Communicate(text, voice, rate=RATE)
        await communicate.save(str(temp_path))
        print(f"  [{speaker}] {idx + 1}/{total} done")

    # Concatenate with ffmpeg
    list_file = output_path.parent / "_concat_list.txt"
    list_file.write_text("\n".join(f"file '{tf.name}'" for tf in temp_files))

    import subprocess
    temp_concat = output_path.parent / "_concat_raw.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(temp_concat)
    ], capture_output=True, cwd=str(output_path.parent))

    # Re-encode as CBR with correct headers
    subprocess.run([
        "ffmpeg", "-y", "-i", str(temp_concat),
        "-codec:a", "libmp3lame", "-b:a", "64k", "-ar", "24000", "-ac", "1",
        "-write_xing", "0",
        str(output_path)
    ], capture_output=True)
    temp_concat.unlink()

    list_file.unlink()
    for tf in temp_files:
        tf.unlink()



def cleanup_old_episodes() -> list[str]:
    """Remove episodes older than MAX_EPISODE_AGE_DAYS. Returns removed filenames."""
    cutoff = datetime.now() - timedelta(days=MAX_EPISODE_AGE_DAYS)
    removed = []
    for mp3_file in AUDIO_DIR.glob("episode-*.mp3"):
        # Extract date from filename: episode-YYYY-MM-DD.mp3
        match = re.search(r"episode-(\d{4}-\d{2}-\d{2})", mp3_file.name)
        if match:
            file_date = datetime.strptime(match.group(1), "%Y-%m-%d")
            if file_date < cutoff:
                mp3_file.unlink()
                removed.append(mp3_file.name)
                print(f"Removed old episode: {mp3_file.name}")
    return removed


def update_feed(episode_date: str, mp3_filename: str, mp3_size: int, duration_secs: int, episode_description: str = "") -> None:
    """Add new episode to RSS feed and remove old entries."""
    ET.register_namespace("", "")
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")

    tree = ET.parse(FEED_PATH)
    root = tree.getroot()
    channel = root.find("channel")

    # Remove existing entry for same date (prevent duplicates)
    guid_text = f"dair-{episode_date}"
    for existing in channel.findall("item"):
        g = existing.find("guid")
        if g is not None and g.text == guid_text:
            channel.remove(existing)

    # Build new item
    item = ET.SubElement(channel, "item")

    title = ET.SubElement(item, "title")
    title.text = f"デイリーAIラジオ - {episode_date}"

    description = ET.SubElement(item, "description")
    description.text = episode_description or f"{episode_date}のAI関連最新ニュースをお届けします。"

    enclosure = ET.SubElement(item, "enclosure")
    enclosure.set("url", f"{BASE_URL}/audio/episodes/{mp3_filename}")
    enclosure.set("length", str(mp3_size))
    enclosure.set("type", "audio/mpeg")

    guid = ET.SubElement(item, "guid")
    guid.set("isPermaLink", "false")
    guid.text = f"dair-{episode_date}"

    pub_date = ET.SubElement(item, "pubDate")
    dt = datetime.strptime(episode_date, "%Y-%m-%d").replace(
        hour=23, minute=0, second=0,
        tzinfo=timezone(timedelta(hours=9))
    )
    pub_date.text = formatdate(dt.timestamp(), usegmt=True)

    hours = duration_secs // 3600
    minutes = (duration_secs % 3600) // 60
    seconds = duration_secs % 60
    itunes_duration = ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
    itunes_duration.text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # Remove old episodes from feed
    cutoff = datetime.now() - timedelta(days=MAX_EPISODE_AGE_DAYS)
    items_to_remove = []
    for existing_item in channel.findall("item"):
        g = existing_item.find("guid")
        if g is not None and g.text:
            match = re.search(r"(\d{4}-\d{2}-\d{2})", g.text)
            if match:
                item_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if item_date < cutoff:
                    items_to_remove.append(existing_item)

    for old_item in items_to_remove:
        channel.remove(old_item)
        print(f"Removed old feed entry: {old_item.find('guid').text}")

    tree.write(FEED_PATH, encoding="unicode", xml_declaration=True)


def get_audio_duration(file_path: Path) -> int:
    """Get audio duration using ffprobe."""
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
        capture_output=True, text=True
    )
    return int(float(result.stdout.strip()))


def load_script_from_json(script_path: str) -> tuple[list[tuple[str, str]], str]:
    """Load script and description from a JSON file.

    Expected format:
    {
      "script": [{"speaker": "female", "text": "..."}, ...],
      "description": "episode description text"
    }
    """
    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    script = [(item["speaker"], item["text"]) for item in data["script"]]
    description = data.get("description", "")
    return script, description


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=str, help="Path to script JSON file (skip template generation)")
    parser.add_argument("--fetch-only", action="store_true", help="Fetch news and print as JSON, then exit")
    args = parser.parse_args()

    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")

    # --fetch-only: output news as JSON for external script generation
    if args.fetch_only:
        articles = fetch_news()
        print(json.dumps(articles, ensure_ascii=False, indent=2))
        return

    mp3_filename = f"episode-{today}.mp3"
    mp3_path = AUDIO_DIR / mp3_filename

    if mp3_path.exists():
        print(f"Episode for {today} already exists. Skipping.")
        return

    if args.script:
        # Load script from external JSON (written by Claude agent)
        print(f"Loading script from {args.script}...")
        script, raw_desc = load_script_from_json(args.script)
        # Strip any existing credit block and rebuild it from code
        # to prevent stale/incomplete source attribution
        desc_body = re.split(r"\n*【クレジット】.*", raw_desc, flags=re.DOTALL)[0].rstrip()
        if not desc_body:
            desc_body = f"{today}のAI関連最新ニュースをお届けします。"
        description = (
            f"{desc_body}\n\n"
            "【クレジット】\n"
            "音声: Microsoft Edge TTS\n"
            f"ニュースソース: {get_source_names()}\n"
            "制作: Claude Code による自動生成\n\n"
            "※この番組はAIによる自動生成です。内容の正確性は保証されません。"
            "情報の利用は自己責任でお願いします。"
        )
    else:
        # Fallback: fetch news + template generation
        print("Fetching AI news...")
        articles = fetch_news()
        if not articles:
            print("No articles found. Exiting.", file=sys.stderr)
            sys.exit(1)

        print(f"Found {len(articles)} articles. Generating script...")
        script = generate_script(articles)

        topics = []
        for article in articles:
            clean = re.sub(r"\s*[-–—|]\s*[^-–—|]+$", "", article["title"])
            topics.append(clean)
        topic_list = "\n".join(f"- {t}" for t in topics)
        description = (
            f"{today}のAI関連最新ニュースをお届けします。\n\n"
            f"【トピック】\n{topic_list}\n\n"
            "【クレジット】\n"
            "音声: Microsoft Edge TTS\n"
            f"ニュースソース: {get_source_names()}\n"
            "制作: Claude Code による自動生成\n\n"
            "※この番組はAIによる自動生成です。内容の正確性は保証されません。"
            "情報の利用は自己責任でお願いします。"
        )

    total_chars = sum(len(text) for _, text in script)
    print(f"Script: {len(script)} segments, {total_chars} characters")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating audio...")
    asyncio.run(text_to_speech(script, mp3_path))
    mp3_size = mp3_path.stat().st_size
    duration = get_audio_duration(mp3_path)
    print(f"Audio generated: {mp3_filename} ({mp3_size / 1024 / 1024:.1f} MB, ~{duration // 60} min)")

    print("Updating feed...")
    update_feed(today, mp3_filename, mp3_size, duration, description)

    print("Cleaning up old episodes...")
    cleanup_old_episodes()

    print("Done!")


if __name__ == "__main__":
    main()
