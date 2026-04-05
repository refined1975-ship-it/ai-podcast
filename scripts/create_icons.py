#!/usr/bin/env python3
"""Generate PWA icons from artwork."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "artwork.jpg"

for size in [192, 512]:
    out = REPO / f"icon-{size}.png"
    subprocess.run([
        "sips", "-z", str(size), str(size),
        "--setProperty", "format", "png",
        str(SRC), "--out", str(out)
    ], capture_output=True)
    print(f"Created {out.name}")

if __name__ == "__main__":
    pass
