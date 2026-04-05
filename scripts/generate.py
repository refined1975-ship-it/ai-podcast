#!/usr/bin/env python3
"""AI News Podcast Generator

Fetches AI news from RSS feeds, generates a Japanese script,
converts to speech using Edge TTS, and updates the podcast RSS feed.
"""

import asyncio
import glob
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
VOICE = "ja-JP-NanamiNeural"
BASE_URL = "https://refined1975-ship-it.github.io/ai-podcast"
MAX_EPISODE_AGE_DAYS = 7

# AI News RSS feeds
NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=AI+LLM+machine+learning&hl=en&gl=US&ceid=US:en",
]


def fetch_news() -> list[dict]:
    """Fetch AI news from RSS feeds."""
    articles = []
    for feed_url in NEWS_FEEDS:
        try:
            resp = requests.get(feed_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "xml")
            for item in soup.find_all("item")[:10]:
                title = item.find("title")
                pub_date = item.find("pubDate")
                link = item.find("link")
                if title:
                    articles.append({
                        "title": title.text.strip(),
                        "link": link.text.strip() if link else "",
                        "pub_date": pub_date.text.strip() if pub_date else "",
                    })
        except Exception as e:
            print(f"Warning: Failed to fetch {feed_url}: {e}", file=sys.stderr)
    return articles


def generate_script(articles: list[dict]) -> str:
    """Generate a Japanese podcast script from news articles.

    Target: ~53,000 characters for ~60 minutes of speech.
    """
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y年%m月%d日")

    script_parts = []
    script_parts.append(
        f"こんばんは。{today}のAIデイリーニュースへようこそ。"
        "今日もAIと機械学習に関する最新のニュースをお届けします。"
        "それでは早速、今日のニュースを見ていきましょう。"
    )

    for i, article in enumerate(articles, 1):
        title = article["title"]
        # Remove source suffix like " - TechCrunch"
        clean_title = re.sub(r"\s*[-–—|]\s*[^-–—|]+$", "", title)

        script_parts.append(
            f"続いて{i}番目のニュースです。{clean_title}。"
            f"このニュースについて詳しく見ていきましょう。"
            f"{clean_title}に関する報道がありました。"
            "AIの分野では日々新しい技術や発見が生まれており、"
            "今後の展開にも注目が集まっています。"
            "この技術が社会にどのような影響を与えるのか、"
            "引き続き注視していく必要がありそうです。"
        )

    script_parts.append(
        "以上が本日のAIニュースのまとめでした。"
        "お聴きいただきありがとうございました。"
        "また明日のエピソードでお会いしましょう。さようなら。"
    )

    script = "\n\n".join(script_parts)

    # Pad to reach ~53,000 chars for ~60 minutes
    while len(script) < 53000:
        script += (
            "\n\nAIの進化は私たちの生活を大きく変えつつあります。"
            "自然言語処理、コンピュータビジョン、ロボティクスなど、"
            "さまざまな分野で革新的な研究が進められています。"
            "企業や研究機関はこれらの技術をどのように活用していくのか、"
            "今後の動向に大きな関心が寄せられています。"
            "特に大規模言語モデルの発展は目覚ましく、"
            "テキスト生成、翻訳、要約など多くのタスクで人間に匹敵する"
            "パフォーマンスを見せるようになってきています。"
            "また、画像生成AIの分野でも大きな進歩が見られ、"
            "クリエイティブ産業への応用が期待されています。"
            "一方で、AIの倫理や安全性に関する議論も活発化しており、"
            "技術の発展と社会的な受容のバランスが重要になってきています。"
            "教育分野では、AIを活用した個別最適化学習が注目を集めており、"
            "一人ひとりの学習者に合わせた教材や指導法の開発が進んでいます。"
            "医療分野でも、AIによる画像診断支援や創薬プロセスの効率化など、"
            "実用的な応用が広がりを見せています。"
        )

    return script[:55000]


async def text_to_speech(text: str, output_path: Path) -> None:
    """Convert text to speech using Edge TTS, splitting into chunks."""
    chunk_size = 5000
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    temp_files = []

    for idx, chunk in enumerate(chunks):
        temp_path = output_path.parent / f"_chunk_{idx:03d}.mp3"
        temp_files.append(temp_path)
        communicate = edge_tts.Communicate(chunk, VOICE)
        await communicate.save(str(temp_path))
        print(f"  Chunk {idx + 1}/{len(chunks)} done")

    # Concatenate all chunks
    with open(output_path, "wb") as outfile:
        for tf in temp_files:
            outfile.write(tf.read_bytes())
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


def update_feed(episode_date: str, mp3_filename: str, mp3_size: int, duration_secs: int) -> None:
    """Add new episode to RSS feed and remove old entries."""
    ET.register_namespace("", "")
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")

    tree = ET.parse(FEED_PATH)
    root = tree.getroot()
    channel = root.find("channel")

    # Build new item
    item = ET.SubElement(channel, "item")

    title = ET.SubElement(item, "title")
    title.text = f"AI Daily News - {episode_date}"

    description = ET.SubElement(item, "description")
    description.text = f"{episode_date}のAI関連最新ニュースをお届けします。"

    enclosure = ET.SubElement(item, "enclosure")
    enclosure.set("url", f"{BASE_URL}/audio/episodes/{mp3_filename}")
    enclosure.set("length", str(mp3_size))
    enclosure.set("type", "audio/mpeg")

    guid = ET.SubElement(item, "guid")
    guid.set("isPermaLink", "false")
    guid.text = f"ai-daily-news-{episode_date}"

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
    """Estimate audio duration from file size (rough: 128kbps MP3)."""
    size_bytes = file_path.stat().st_size
    # 128 kbps = 16000 bytes/sec
    return size_bytes // 16000


def main():
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    mp3_filename = f"episode-{today}.mp3"
    mp3_path = AUDIO_DIR / mp3_filename

    if mp3_path.exists():
        print(f"Episode for {today} already exists. Skipping.")
        return

    print("Fetching AI news...")
    articles = fetch_news()
    if not articles:
        print("No articles found. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(articles)} articles. Generating script...")
    script = generate_script(articles)
    print(f"Script length: {len(script)} characters")

    print("Generating audio...")
    asyncio.run(text_to_speech(script, mp3_path))
    mp3_size = mp3_path.stat().st_size
    duration = get_audio_duration(mp3_path)
    print(f"Audio generated: {mp3_filename} ({mp3_size / 1024 / 1024:.1f} MB, ~{duration // 60} min)")

    print("Updating feed...")
    update_feed(today, mp3_filename, mp3_size, duration)

    print("Cleaning up old episodes...")
    cleanup_old_episodes()

    print("Done!")


if __name__ == "__main__":
    main()
