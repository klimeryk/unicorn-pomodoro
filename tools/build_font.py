# Builds 3x5.bitmapfont (Pimoroni PicoGraphics custom font) from
# tom-thumb-new.png, the Tom Thumb 3x5 font sheet (CC0/CC-BY 3.0,
# https://opengameart.org/content/tom-thumb-tiny-ascii-font-3x5): a 32x4 grid
# of 4x6 cells covering chars 0-127, black ink, glyph in the left 3 columns,
# descenders on the 6th row. Needs `pip install pgfutil pillow`.
#
#   python3 tools/build_font.py

import os
import tempfile

from pgfutil.core import Image2Font
from PIL import Image

GLYPH_W = 3
GLYPH_H = 6
CELL_W = 4
SHEET_COLS = 32
FIRST_CHAR = 32
LAST_CHAR = 126  # 127 is a solid placeholder block in the sheet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, "tom-thumb-new.png")
OUT = os.path.join(ROOT, "3x5.bitmapfont")


def sheet_glyphs(sheet):
    for ch in range(FIRST_CHAR, LAST_CHAR + 1):
        gx = (ch % SHEET_COLS) * CELL_W
        gy = (ch // SHEET_COLS) * GLYPH_H
        cols = [
            [sheet.getpixel((gx + x, gy + y)) < 128 for y in range(GLYPH_H)]
            for x in range(GLYPH_W)
        ]
        # pgfutil derives each width by trimming empty columns from the right
        # edge only, so glyphs must hug the left edge of their cell.
        if any(any(col) for col in cols):
            while not any(cols[0]):
                cols = [*cols[1:], [False] * GLYPH_H]
        yield ch - FIRST_CHAR, cols


def main():
    sheet = Image.open(SHEET).convert("L")
    canvas = Image.new(
        "RGBA",
        (
            (GLYPH_W + 1) * Image2Font.LAYOUT_COLS,
            (GLYPH_H + 1) * Image2Font.LAYOUT_ROWS,
        ),
        Image2Font.WHITE,
    )
    for c, cols in sheet_glyphs(sheet):
        cx = (c % Image2Font.LAYOUT_COLS) * (GLYPH_W + 1)
        cy = (c // Image2Font.LAYOUT_COLS) * (GLYPH_H + 1)
        for x, col in enumerate(cols):
            for y, ink in enumerate(col):
                if ink:
                    canvas.putpixel((cx + x, cy + y), Image2Font.BLACK)
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        canvas.save(tmp.name)
        font = Image2Font(filename=tmp.name)
    font.save_data(OUT)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
