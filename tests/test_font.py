import os
import unittest

import config
import ui

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STELLAR_WIDTH = 16
FIRST_CHAR = 32
# PicoGraphics bitmap fonts store printable ASCII plus 9 extra glyphs.
GLYPH_COUNT = 96 + 9
LETTER_SPACING = 1

DIGITS = "0123456789"
SMALL_FONT_TEXT = (
    ui.BOOT_LABEL,
    ui.READY_LABEL,
    ui.RESET_LABEL,
    ui.RESET_LABEL_SHORT,
    DIGITS,
    config.TIME_PAD_CHAR,
)
CLOCK_FONT_TEXT = DIGITS + "-" + config.TIME_PAD_CHAR


class BitmapFont:
    def __init__(self, filename):
        with open(os.path.join(ROOT, filename), "rb") as f:
            data = f.read()
        self.name = filename
        self.height = data[0]
        self.max_width = data[1]
        self._widths = data[2 : 2 + GLYPH_COUNT]

    def glyph_width(self, ch):
        return self._widths[ord(ch) - FIRST_CHAR]

    def measure(self, text):
        return sum(self.glyph_width(ch) + LETTER_SPACING for ch in text)


class FontTest(unittest.TestCase):
    def _assert_has_glyphs(self, font, text):
        for ch in text:
            with self.subTest(font=font.name, ch=ch):
                self.assertGreater(font.glyph_width(ch), 0)

    def test_small_font_has_every_glyph_the_ui_draws(self):
        font = BitmapFont("3x5.bitmapfont")
        self.assertEqual((font.height, font.max_width), (6, 3))
        for text in SMALL_FONT_TEXT:
            self._assert_has_glyphs(font, text)

    def test_ready_label_scrolls_on_stellar(self):
        font = BitmapFont("3x5.bitmapfont")
        self.assertGreater(font.measure(ui.READY_LABEL), STELLAR_WIDTH)

    def test_clock_fonts_have_digits_dash_and_padding(self):
        for filename in ("MatrixChunky8x6.bitmapfont", "MatrixLight8x6.bitmapfont"):
            font = BitmapFont(filename)
            self.assertEqual((font.height, font.max_width), (8, 6), filename)
            self._assert_has_glyphs(font, CLOCK_FONT_TEXT)
