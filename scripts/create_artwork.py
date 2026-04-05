#!/usr/bin/env python3
"""Generate podcast artwork (3000x3000 JPEG) - monochrome design."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = REPO_ROOT / "artwork.svg"
PNG_PATH = REPO_ROOT / "artwork.png"
JPG_PATH = REPO_ROOT / "artwork.jpg"

SVG_CONTENT = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3000 3000" width="3000" height="3000">
  <!-- White background -->
  <rect width="3000" height="3000" fill="#ffffff"/>

  <!-- Top text -->
  <text x="1500" y="520" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-size="200" font-weight="700" fill="#1a1a1a" letter-spacing="30">AI DAILY NEWS</text>

  <!-- Top separator -->
  <line x1="1100" y1="620" x2="1900" y2="620" stroke="#1a1a1a" stroke-width="4"/>

  <!-- Headphone icon -->
  <g transform="translate(1500, 1450)" fill="none" stroke="#1a1a1a" stroke-width="50" stroke-linecap="round" stroke-linejoin="round">
    <path d="M-400,100 A400,400 0 0,1 400,100"/>
    <rect x="-450" y="50" width="120" height="300" rx="60" fill="#1a1a1a"/>
    <rect x="330" y="50" width="120" height="300" rx="60" fill="#1a1a1a"/>
    <line x1="-400" y1="100" x2="-400" y2="200"/>
    <line x1="400" y1="100" x2="400" y2="200"/>
  </g>

  <!-- Sound waves left -->
  <g transform="translate(900, 1450)" fill="none" stroke="#333333" stroke-width="6" stroke-linecap="round">
    <path d="M0,-80 Q-30,0 0,80" opacity="0.6"/>
    <path d="M-40,-130 Q-80,0 -40,130" opacity="0.4"/>
    <path d="M-80,-180 Q-130,0 -80,180" opacity="0.2"/>
  </g>

  <!-- Sound waves right -->
  <g transform="translate(2100, 1450)" fill="none" stroke="#333333" stroke-width="6" stroke-linecap="round">
    <path d="M0,-80 Q30,0 0,80" opacity="0.6"/>
    <path d="M40,-130 Q80,0 40,130" opacity="0.4"/>
    <path d="M80,-180 Q130,0 80,180" opacity="0.2"/>
  </g>

  <!-- Bottom separator -->
  <line x1="1100" y1="2300" x2="1900" y2="2300" stroke="#1a1a1a" stroke-width="4"/>

  <!-- Bottom Japanese text -->
  <text x="1500" y="2480" text-anchor="middle" font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif" font-size="140" font-weight="600" fill="#1a1a1a" letter-spacing="20">デイリーニュース</text>

  <!-- Tagline -->
  <text x="1500" y="2650" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-size="80" font-weight="300" fill="#666666" letter-spacing="15">POWERED BY AI</text>
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
