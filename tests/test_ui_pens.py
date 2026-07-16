# Host-side test that the UI pen cache stays bounded (no hardware needed):
#   python3 tests/test_ui_pens.py

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pomodoro import READY, WORK
from ui import UI


class MockGraphics:
    def __init__(self):
        self.pens_created = 0

    def create_pen(self, r, g, b):
        self.pens_created += 1
        return self.pens_created

    def set_pen(self, pen):
        pass

    def set_font(self, font):
        pass

    def clear(self):
        pass

    def pixel(self, x, y):
        pass

    def rectangle(self, x, y, w, h):
        pass

    def text(self, text, x, y, wordwrap, scale):
        pass

    def measure_text(self, text, scale):
        return len(text) * 4 * scale


def test_pen_cache_bounded():
    g = MockGraphics()
    ui = UI(g, 16, 16, ((15, 3), (15, 4)))
    frame_ms = 40
    now = 0
    total = 25 * 60
    for _ in range(5 * 60 * 1000 // frame_ms):
        ui.render_pomodoro(now, READY, 0, 0.0, 0, (12, 34, 56))
        now += frame_ms
    for secs in range(total, 0, -1):
        for _ in range(1000 // frame_ms):
            ui.render_pomodoro(now, WORK, secs, secs / total, 1, (12, 34, 56))
            now += frame_ms
    assert len(ui._pens) < 100, len(ui._pens)
    assert g.pens_created == len(ui._pens)
    print(f"pen cache bounded ({len(ui._pens)} pens): OK")


def test_clock_pen_cache():
    g = MockGraphics()
    ui = UI(g, 16, 16, ((15, 3), (15, 4)))
    for i in range(5000):
        fg = ((i * 3) % 256, (i * 5) % 256, (i * 11) % 256)
        bg = (i % 256, (i * 7) % 256, (i * 13) % 256) if i % 2 else None
        ui.render_clock((12, 34, i % 60), fg, bg)
    assert len(ui._pens) < 10, len(ui._pens)
    print(f"clock fg/bg keep pen cache bounded ({len(ui._pens)} pens): OK")


if __name__ == "__main__":
    test_pen_cache_bounded()
    test_clock_pen_cache()
    print("all ui pen tests passed")
