import unittest
from unittest import mock

import config
from pomodoro import LONG_BREAK, READY, SHORT_BREAK, WORK
from tests.fakes import FakeGraphics
from ui import BLACK, UI

BOARD_SIZES = {"stellar": (16, 16), "galactic": (53, 11), "cosmic": (32, 32)}
BUTTON_A_HINT_PIXELS = ((0, 2), (0, 3), (0, 4))
TIMES_OF_DAY = (None, (0, 0, 0), (9, 5, 7), (13, 59, 58), (23, 7, 1))
REMAINING_SECONDS = (25 * 60, 12 * 60 + 34, 9 * 60 + 5, 60, 59, 1, 0)
FULL_SECONDS = 25 * 60


def make_ui(board="stellar"):
    width, height = BOARD_SIZES[board]
    graphics = FakeGraphics(width, height)
    with mock.patch.object(config, "LAYOUT", config.LAYOUTS[board]):
        return UI(graphics, width, height, BUTTON_A_HINT_PIXELS), graphics


class UILayoutTest(unittest.TestCase):
    def test_every_screen_stays_on_every_board(self):
        for board in BOARD_SIZES:
            with self.subTest(board=board):
                ui, _ = make_ui(board)
                ui.render_boot()
                for now in range(0, 10_000, 37):
                    ui.render_pomodoro(now, READY, 0, 0.0, now // 2500, (9, 5, 7))
                    ui.render_reset_confirm(now)
                for state in (WORK, SHORT_BREAK, LONG_BREAK):
                    for remaining_s in REMAINING_SECONDS:
                        for hms in TIMES_OF_DAY:
                            ui.render_pomodoro(
                                remaining_s * 7,
                                state,
                                remaining_s,
                                remaining_s / FULL_SECONDS,
                                3,
                                hms,
                            )
                for hms in TIMES_OF_DAY:
                    ui.render_clock(hms, config.COLOR_CLOCK_BIG, BLACK)
                    ui.render_clock(hms, BLACK, (200, 40, 90))


class UITextTest(unittest.TestCase):
    def setUp(self):
        self.ui, self.graphics = make_ui()

    def _drawn_texts(self, render, *args):
        self.graphics.texts.clear()
        render(*args)
        return self.graphics.texts

    def _timer_digits(self, remaining_s):
        texts = self._drawn_texts(
            self.ui.render_pomodoro, 0, WORK, remaining_s, 1.0, 0, None
        )
        return "".join(texts)

    def _clock_digits(self, hms):
        texts = self._drawn_texts(
            self.ui.render_clock, hms, config.COLOR_CLOCK_BIG, BLACK
        )
        return "".join(texts)

    def test_timer_shows_minutes_and_seconds(self):
        self.assertEqual(self._timer_digits(12 * 60 + 34), "1234")

    def test_timer_pads_single_digit_minutes(self):
        self.assertEqual(self._timer_digits(9 * 60 + 5), config.TIME_PAD_CHAR + "905")

    def test_timer_shows_small_clock_when_time_is_known(self):
        texts = self._drawn_texts(
            self.ui.render_pomodoro, 0, WORK, 12 * 60 + 34, 1.0, 0, (14, 3, 0)
        )
        self.assertEqual("".join(texts), "12341403")

    def test_clock_uses_24h_time(self):
        with mock.patch.object(config, "CLOCK_24H", True):
            self.assertEqual(self._clock_digits((13, 5, 0)), "1305")
            self.assertEqual(
                self._clock_digits((0, 0, 0)), config.TIME_PAD_CHAR + "000"
            )

    def test_clock_uses_12h_time(self):
        with mock.patch.object(config, "CLOCK_24H", False):
            self.assertEqual(
                self._clock_digits((13, 5, 0)), config.TIME_PAD_CHAR + "105"
            )
            self.assertEqual(self._clock_digits((0, 0, 0)), "1200")
            self.assertEqual(self._clock_digits((12, 0, 0)), "1200")

    def test_clock_shows_dashes_until_time_is_synced(self):
        self.assertEqual(self._clock_digits(None), "----")
