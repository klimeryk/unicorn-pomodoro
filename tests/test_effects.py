# Host-side test of the transition animations (no hardware needed):
#   python3 tests/test_effects.py

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from effects import Burst, HourFlash, Rings

W = H = 16


class MockGraphics:
    def __init__(self):
        self.pixels_drawn = 0

    def create_pen(self, r, g, b):
        assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255, (r, g, b)
        return (r, g, b)

    def set_pen(self, pen):
        pass

    def clear(self):
        pass

    def pixel(self, x, y):
        assert 0 <= x < W and 0 <= y < H, (x, y)
        self.pixels_drawn += 1

    def rectangle(self, x, y, w, h):
        assert x >= 0 and x + w <= W and y >= 0 and y + h <= H, (x, y, w, h)
        self.pixels_drawn += w * h


def run_effect(make):
    g = MockGraphics()
    fx = make(g)
    fx.start(1000)
    assert not fx.done(1000)
    now = 1000
    frames = 0
    while not fx.done(now):
        fx.draw(now)
        now += 20
        frames += 1
        assert frames < 1000, "effect never finished"
    duration = (now - 1000) / 1000
    assert 1.0 < duration < 5.0, duration
    assert g.pixels_drawn > frames, g.pixels_drawn
    print(f"{type(fx).__name__}: {frames} frames, {g.pixels_drawn} px: OK")


def test_burst():
    run_effect(lambda g: Burst(g, W, H, (255, 60, 40), (30, 150, 40)))


def test_rings():
    run_effect(lambda g: Rings(g, W, H, (0, 255, 0)))


def test_hour_flash():
    config.TEST_MODE = False
    fx = HourFlash()
    fg0, bg0 = fx.update(0, (9, 59, 58))
    assert bg0 is None
    assert fx.update(100, (9, 59, 59)) == (fg0, None)
    assert fx.update(200, None) == (fg0, None)
    assert max(fg0) > 0, fg0

    total_ms = int(
        (config.CLOCK_FLASH_S + config.CLOCK_SETTLE_S + config.CLOCK_INVERT_S) * 1000
    )
    seen = set()
    now = 300
    end = now + total_ms
    while now < end:
        fg, bg = fx.update(now, (10, 0, 0))
        assert bg is not None
        for c in (fg, bg):
            for ch in c:
                assert isinstance(ch, int) and 0 <= ch <= 255, c
        seen.add((fg, bg))
        now += 20
    assert len(seen) > 10, len(seen)

    settled = fx.update(end + 100, (10, 0, 1))
    assert settled == fx.update(end + 200, (10, 30, 0))
    assert settled[1] is None
    assert settled[0] != fg0
    print(f"HourFlash: {len(seen)} states during transition: OK")


if __name__ == "__main__":
    test_burst()
    test_rings()
    test_hour_flash()
    print("all effects tests passed")
