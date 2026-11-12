import json
import os
import tempfile
import unittest
from unittest import mock

import config
import settings
from compat import ticks_add
from settings import SAVE_DELAY_MS, Settings


class SettingsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "settings.json")

    def _write(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def _defaults(self):
        return (config.DEFAULT_BRIGHTNESS, config.DEFAULT_VOLUME)

    def test_missing_file_loads_defaults(self):
        self.assertEqual(settings.load(self.path), self._defaults())

    def test_corrupt_file_loads_defaults(self):
        for text in ("", "{not json", "[1, 2]", '"text"'):
            self._write(text)
            self.assertEqual(settings.load(self.path), self._defaults(), text)

    def test_missing_or_invalid_key_falls_back_per_key(self):
        self._write('{"brightness": 0.3}')
        self.assertEqual(settings.load(self.path), (0.3, config.DEFAULT_VOLUME))
        self._write('{"brightness": "bright", "volume": 0.2}')
        self.assertEqual(settings.load(self.path), (config.DEFAULT_BRIGHTNESS, 0.2))

    def test_out_of_range_levels_are_clamped(self):
        self._write('{"brightness": 1.7, "volume": -0.4}')
        self.assertEqual(settings.load(self.path), (1.0, 0.0))

    def test_unchanged_levels_are_never_written(self):
        saver = Settings(self.path, 0.5, 0.5)
        for now in range(0, 3 * SAVE_DELAY_MS, 10):
            saver.poll(now, 0.5, 0.5)
        self.assertFalse(os.path.exists(self.path))

    def test_writes_once_after_levels_settle(self):
        saver = Settings(self.path, 0.5, 0.5)
        level = 0.5
        last_change = 0
        for now in range(0, 2 * SAVE_DELAY_MS, 10):
            level += 0.001
            saver.poll(now, level, 0.5)
            last_change = now
        self.assertFalse(os.path.exists(self.path))
        saver.poll(last_change + SAVE_DELAY_MS - 1, level, 0.5)
        self.assertFalse(os.path.exists(self.path))
        with mock.patch("builtins.open", wraps=open) as opened:
            saver.poll(last_change + SAVE_DELAY_MS, level, 0.5)
            saver.poll(last_change + 2 * SAVE_DELAY_MS, level, 0.5)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(settings.load(self.path), (level, 0.5))

    def test_saved_file_round_trips(self):
        saver = Settings(self.path, 0.5, 0.5)
        saver.poll(0, 0.25, 0.75)
        saver.poll(SAVE_DELAY_MS, 0.25, 0.75)
        with open(self.path) as f:
            self.assertEqual(json.load(f), {"brightness": 0.25, "volume": 0.75})
        self.assertEqual(settings.load(self.path), (0.25, 0.75))

    def test_settle_delay_spans_ticks_wraparound(self):
        changed_at = ticks_add(0, -SAVE_DELAY_MS // 2)
        saver = Settings(self.path, 0.5, 0.5)
        saver.poll(changed_at, 0.6, 0.5)
        saver.poll(ticks_add(changed_at, SAVE_DELAY_MS - 1), 0.6, 0.5)
        self.assertFalse(os.path.exists(self.path))
        saver.poll(ticks_add(changed_at, SAVE_DELAY_MS), 0.6, 0.5)
        self.assertEqual(settings.load(self.path), (0.6, 0.5))

    def test_failed_write_is_not_retried_every_frame(self):
        saver = Settings(self.path, 0.5, 0.5)
        saver.poll(0, 0.6, 0.5)
        with mock.patch("builtins.open", side_effect=OSError) as opened:
            for now in range(SAVE_DELAY_MS, 3 * SAVE_DELAY_MS, 10):
                saver.poll(now, 0.6, 0.5)
        self.assertEqual(opened.call_count, 1)
