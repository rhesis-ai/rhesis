"""Rebuilds the TTF font subsets used by the social preview cards (/api/og).

satori — the renderer inside next/og — cannot read woff2, and renders a
variable font at its default instance only. So each face the site already ships
as woff2 is decompressed, pinned to a single weight, and subset to latin.

Run from the repo root after changing a font in src/public/fonts:

    uv run --with fonttools --with brotli python docs/scripts/generate-og-fonts.py

Output goes to docs/src/public/fonts/og/ and is committed — the docs image has
no Python in it. Sizes stay around 25 KB per face; keep them there, because
every card render loads all four.
"""

import pathlib
import sys

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

# Latin, punctuation (en/em dash, curly quotes, ellipsis), arrows, minus.
UNICODES = "U+0000-00FF,U+2000-206F,U+2190-21FF,U+2212"

# (source woff2, weight to pin for variable fonts, output name)
JOBS = [
    ("Sora-700.woff2", None, "Sora-700.ttf"),
    ("Geist-VariableFont_wght.woff2", 400, "Geist-400.ttf"),
    ("Geist-VariableFont_wght.woff2", 500, "Geist-500.ttf"),
    ("GeistMono-VariableFont_wght.woff2", 500, "GeistMono-500.ttf"),
]


def parse_unicodes(spec):
    codepoints = set()
    for part in spec.split(","):
        part = part.strip().removeprefix("U+")
        if "-" in part:
            low, high = part.split("-")
            codepoints.update(range(int(low, 16), int(high, 16) + 1))
        else:
            codepoints.add(int(part, 16))
    return codepoints


def main():
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    fonts_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "docs/src/public/fonts"
    out_dir = fonts_dir / "og"
    out_dir.mkdir(exist_ok=True)

    wanted = parse_unicodes(UNICODES)

    for source, weight, target in JOBS:
        font = TTFont(fonts_dir / source)
        font.flavor = None  # drop woff2 compression
        if weight is not None:
            font = instantiateVariableFont(font, {"wght": weight}, updateFontNames=True)

        options = Options()
        options.layout_features = ["kern", "liga", "calt"]
        options.name_IDs = ["*"]
        options.notdef_outline = True

        subsetter = Subsetter(options=options)
        subsetter.populate(unicodes=wanted)
        subsetter.subset(font)

        font.save(out_dir / target)
        print(f"{target}: {(out_dir / target).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
