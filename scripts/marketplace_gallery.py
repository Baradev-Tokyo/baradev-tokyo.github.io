"""Create original scope cards for owner review. No screenshots or client media."""

import argparse
import os
from pathlib import Path
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bara_home"))
from services.catalog import PACKAGES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    arial = Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts/arial.ttf"

    def font(size):
        return ImageFont.truetype(str(arial), size) if arial.is_file() else ImageFont.load_default(size=size)

    for package in PACKAGES:
        image = Image.new("RGB", (1280, 769), "#0D2036")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 16, 769), fill="#5B9BD1")
        draw.text((80, 64), "Bara Development", font=font(33), fill="#A9BAC9")
        title = textwrap.fill(package.name, width=29)
        draw.multiline_text((80, 145), title, font=font(72), fill="#F6F7F9", spacing=8)
        draw.rectangle((80, 340, 1200, 343), fill="#5B9BD1")
        y = 383
        for scope in package.scope:
            draw.ellipse((81, y + 13, 94, y + 26), fill="#E2793D")
            line = textwrap.fill(scope, width=52)
            draw.multiline_text((119, y), line, font=font(34), fill="#F6F7F9", spacing=5)
            y += 58 + 40 * line.count("\n")
        image.save(args.directory / f"{package.slug}.png", optimize=True)


if __name__ == "__main__":
    main()
