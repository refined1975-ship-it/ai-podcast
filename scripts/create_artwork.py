#!/usr/bin/env python3
"""Generate podcast artwork (3000x3000 JPEG) - monochrome design."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = REPO_ROOT / "artwork.svg"
PNG_PATH = REPO_ROOT / "artwork.png"
JPG_PATH = REPO_ROOT / "artwork.jpg"

SVG_CONTENT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3000 3000">
  <rect width="3000" height="3000" fill="#0a0a0a"/>

  <!-- Sound waveform bars - center group -->
  <g transform="translate(1500, 1500)">
    <rect x="-520" y="-80" width="40" height="160" rx="20" fill="#fff"/>
    <rect x="-440" y="-140" width="40" height="280" rx="20" fill="#fff"/>
    <rect x="-360" y="-220" width="40" height="440" rx="20" fill="#fff"/>
    <rect x="-280" y="-320" width="40" height="640" rx="20" fill="#fff"/>
    <rect x="-200" y="-180" width="40" height="360" rx="20" fill="#fff"/>
    <rect x="-120" y="-400" width="40" height="800" rx="20" fill="#fff"/>
    <rect x="-40" y="-500" width="40" height="1000" rx="20" fill="#fff"/>
    <rect x="0" y="-500" width="40" height="1000" rx="20" fill="#fff"/>
    <rect x="80" y="-400" width="40" height="800" rx="20" fill="#fff"/>
    <rect x="160" y="-180" width="40" height="360" rx="20" fill="#fff"/>
    <rect x="240" y="-320" width="40" height="640" rx="20" fill="#fff"/>
    <rect x="320" y="-220" width="40" height="440" rx="20" fill="#fff"/>
    <rect x="400" y="-140" width="40" height="280" rx="20" fill="#fff"/>
    <rect x="480" y="-80" width="40" height="160" rx="20" fill="#fff"/>
  </g>

  <!-- Title text -->
  <text x="1500" y="580" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-weight="700" font-size="200" letter-spacing="20" fill="#fff">DISTILL RADIO</text>

  <!-- Thin line under title -->
  <line x1="1200" y1="640" x2="1800" y2="640" stroke="#fff" stroke-width="3"/>

  <!-- Bottom text -->
  <line x1="1200" y1="2300" x2="1800" y2="2300" stroke="#fff" stroke-width="3"/>
  <text x="1500" y="2400" text-anchor="middle" font-family="'Hiragino Kaku Gothic ProN', 'Hiragino Sans', sans-serif" font-weight="500" font-size="160" fill="#fff">蒸留ラジオ AI</text>
  <text x="1500" y="2520" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-weight="300" font-size="80" letter-spacing="16" fill="#888">POWERED BY AI</text>
</svg>'''


def main():
    SVG_PATH.write_text(SVG_CONTENT)

    subprocess.run(
        ["qlmanage", "-t", "-s", "3000", "-o", str(REPO_ROOT), str(SVG_PATH)],
        capture_output=True,
    )

    ql_output = REPO_ROOT / "artwork.svg.png"
    if ql_output.exists():
        ql_output.rename(PNG_PATH)

    if PNG_PATH.exists():
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90",
             str(PNG_PATH), "--out", str(JPG_PATH)],
            capture_output=True,
        )
        PNG_PATH.unlink()
        SVG_PATH.unlink()
        print(f"Artwork saved: {JPG_PATH} ({JPG_PATH.stat().st_size / 1024:.0f} KB)")
    else:
        print("Error: PNG conversion failed")


if __name__ == "__main__":
    main()
