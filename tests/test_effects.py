# Host-side test of the transition animations (no hardware needed):
#   python3 tests/test_effects.py

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from effects import Burst, Rings

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


if __name__ == "__main__":
    test_burst()
    test_rings()
    print("all effects tests passed")
