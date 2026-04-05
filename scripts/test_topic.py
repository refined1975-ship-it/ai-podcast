#!/usr/bin/env python3
"""Test: 1 topic with male-female dialogue, faster speed."""

import asyncio
import subprocess
from pathlib import Path

import edge_tts

OUT = Path(__file__).resolve().parent.parent / "test_topic.mp3"
RATE = "+15%"  # 少し早め

# 1トピックの台本（男女対話形式、情報密度高め）
SCRIPT = [
    ("female", "今日の最初のトピックです。Googleが新しい大規模言語モデル「Gemini 2.5 Pro」を発表しました。"),
    ("male", "これ、かなりインパクトありますね。特に注目すべきは、100万トークンのコンテキストウィンドウです。これまでの主要モデルが12万8000から20万トークンだったことを考えると、桁違いの拡張です。"),
    ("female", "実際のベンチマークではどうだったんですか？"),
    ("male", "コーディングベンチマークのSWE-benchで63.8パーセントを記録していて、これは現時点で公開されているモデルの中ではトップクラスです。特に面白いのは、いわゆる「思考モデル」と呼ばれるカテゴリで、推論の過程を明示的に出力する設計になっている点です。"),
    ("female", "思考モデルというのは、いわゆるChain of Thoughtの発展形ということですか？"),
    ("male", "そうですね。ただ従来のChain of Thoughtプロンプティングとは違って、モデルの学習段階から推論プロセスを組み込んでいます。OpenAIのo1やo3、Anthropicの拡張思考機能と同じ流れですが、Googleはこれにマルチモーダル対応を組み合わせている点が差別化ポイントです。"),
    ("female", "マルチモーダルというと、画像や動画も扱えるんですか？"),
    ("male", "はい。テキスト、画像、音声、動画、コードを統合的に処理できます。たとえば、設計図の画像を読み込ませてコードを生成したり、動画の内容を要約したりできます。100万トークンのコンテキストがあるので、1時間以上の動画も丸ごと入力できる計算になります。"),
    ("female", "開発者への影響はどう見ていますか？"),
    ("male", "大きく3つあると思います。1つ目は、RAGの設計が変わる可能性。コンテキストが100万トークンあれば、検索拡張生成に頼らなくても大量の文書を直接入力できるケースが増えます。2つ目は、エージェント型AIの実用性向上。長い作業履歴を保持したまま複雑なタスクを遂行できます。3つ目は、価格競争の加速。Googleはこのモデルを比較的安価に提供しているので、他社のAPI価格にも影響するでしょう。"),
    ("female", "一方でリスクや懸念点はありますか？"),
    ("male", "コンテキストが長くなると、いわゆる「迷子問題」が起きやすくなります。中間部分の情報を見落とす、いわゆるLost in the Middle問題ですね。Googleはこれに対してアテンション機構の改良で対応したと主張していますが、実際のプロダクション環境でどこまで安定するかは、まだ検証が必要です。"),
    ("female", "なるほど。コンテキスト長の拡大は便利な反面、使い方にも工夫が必要ということですね。では次のトピックに移りましょう。"),
]


async def generate():
    temp_files = []

    for idx, (speaker, text) in enumerate(SCRIPT):
        voice = "ja-JP-NanamiNeural" if speaker == "female" else "ja-JP-KeitaNeural"
        temp_path = OUT.parent / f"_test_{idx:03d}.mp3"
        temp_files.append(temp_path)
        communicate = edge_tts.Communicate(text, voice, rate=RATE)
        await communicate.save(str(temp_path))
        print(f"  [{speaker}] {idx + 1}/{len(SCRIPT)} done")

    # Concatenate with ffmpeg
    list_file = OUT.parent / "_test_list.txt"
    list_file.write_text("\n".join(f"file '{tf.name}'" for tf in temp_files))

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(OUT)
    ], capture_output=True, cwd=str(OUT.parent))

    list_file.unlink()
    for tf in temp_files:
        tf.unlink()

    # Duration
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(OUT)],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())
    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"\nDone: {OUT.name} ({size_mb:.1f} MB, {duration / 60:.1f} min)")


asyncio.run(generate())
