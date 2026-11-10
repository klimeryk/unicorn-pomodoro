import random
import unittest
from unittest import mock

import config
from compat import ticks_add, ticks_diff
from effects import BLACK, Burst, HourFlash, Rings
from tests.fakes import FakeGraphics

BOARD_SIZES = ((16, 16), (53, 11), (32, 32))
FRAME_MS = 20
START_MS = 1000


def play_to_completion(effect, start=START_MS):
    effect.start(start)
    now = start
    while not effect.done(now):
        effect.draw(now)
        now = ticks_add(now, FRAME_MS)
        if ticks_diff(now, start) > 10_000:
            raise AssertionError("effect never finished")
    return ticks_diff(now, start)


class TransitionEffectTest(unittest.TestCase):
    def setUp(self):
        random.seed(1)

    def _assert_plays_on_every_board(self, make_effect):
        for width, height in BOARD_SIZES:
            with self.subTest(board=(width, height)):
                graphics = FakeGraphics(width, height)
                effect = make_effect(graphics, width, height)
                self.assertFalse(effect.done(START_MS))
                duration_ms = play_to_completion(effect)
                self.assertGreaterEqual(duration_ms, effect.DURATION_S * 1000)
                frames = duration_ms // FRAME_MS
                self.assertGreater(graphics.pixels_drawn, frames)

    def test_burst_plays_on_screen(self):
        self._assert_plays_on_every_board(
            lambda g, w, h: Burst(g, w, h, config.TOMATO_RED, config.STEM_GREEN)
        )

    def test_effects_finish_on_time_across_ticks_wraparound(self):
        start = (1 << 30) - 500
        for effect in (
            Burst(FakeGraphics(16, 16), 16, 16, config.TOMATO_RED, config.STEM_GREEN),
            Rings(FakeGraphics(16, 16), 16, 16, config.COLOR_READY),
        ):
            with self.subTest(effect=type(effect).__name__):
                duration_ms = play_to_completion(effect, start)
                self.assertGreaterEqual(duration_ms, effect.DURATION_S * 1000)
                self.assertLess(duration_ms, effect.DURATION_S * 1000 + FRAME_MS)

    def test_rings_play_on_screen(self):
        self._assert_plays_on_every_board(
            lambda g, w, h: Rings(g, w, h, config.COLOR_READY)
        )


class HourFlashTest(unittest.TestCase):
    TRANSITION_MS = int(
        (config.CLOCK_FLASH_S + config.CLOCK_SETTLE_S + config.CLOCK_INVERT_S) * 1000
    )

    def setUp(self):
        random.seed(1)
        patcher = mock.patch.object(config, "TEST_MODE", False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.flash = HourFlash()

    def _assert_valid_color(self, color):
        self.assertEqual(len(color), 3)
        for channel in color:
            self.assertIsInstance(channel, int)
            self.assertTrue(0 <= channel <= 255, color)

    def test_steady_within_an_hour(self):
        digit_color, background = self.flash.update(0, (9, 59, 58))
        self.assertEqual(background, BLACK)
        self.assertGreater(max(digit_color), 0)
        self.assertEqual(self.flash.update(100, (9, 59, 59)), (digit_color, BLACK))

    def test_unknown_time_keeps_current_colors(self):
        steady = self.flash.update(0, (9, 59, 58))
        self.assertEqual(self.flash.update(100, None), steady)

    def test_new_hour_flashes_then_settles_on_new_digit_color(self):
        old_digit_color, _ = self.flash.update(0, (9, 59, 59))
        start = 100
        end = start + self.TRANSITION_MS
        frames_seen = set()
        for now in range(start, end, FRAME_MS):
            digit_color, background = self.flash.update(now, (10, 0, 0))
            self._assert_valid_color(digit_color)
            self._assert_valid_color(background)
            frames_seen.add((digit_color, background))
        self.assertGreater(len(frames_seen), 10)
        _, mid_transition_background = self.flash.update(
            start + self.TRANSITION_MS // 2, (10, 0, 0)
        )
        self.assertNotEqual(mid_transition_background, BLACK)

        settled = self.flash.update(end + 100, (10, 0, 1))
        self.assertEqual(settled, self.flash.update(end + 200, (10, 30, 0)))
        new_digit_color, background = settled
        self.assertEqual(background, BLACK)
        self.assertNotEqual(new_digit_color, old_digit_color)

    def test_test_mode_flashes_every_minute(self):
        with mock.patch.object(config, "TEST_MODE", True):
            self.flash.update(0, (9, 0, 59))
            self.flash.update(100, (9, 1, 0))
            _, background = self.flash.update(100 + FRAME_MS * 10, (9, 1, 0))
        self.assertNotEqual(background, BLACK)
