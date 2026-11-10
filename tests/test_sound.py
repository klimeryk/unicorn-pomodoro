import unittest
from unittest import mock

import config
import sound
from compat import ticks_add
from sound import Sound

MELODY = ((1000, 100), (2000, 200))


class FakeChannel:
    TRIANGLE = "triangle"
    SINE = "sine"

    def __init__(self):
        self.events = []

    def configure(self, **settings):
        pass

    def frequency(self, freq):
        self.events.append(("freq", freq))

    def trigger_attack(self):
        self.events.append(("attack",))

    def trigger_release(self):
        self.events.append(("release",))


class FakeUnicorn:
    def __init__(self):
        self.channels = [FakeChannel(), FakeChannel()]
        self.playing = False

    def synth_channel(self, index):
        return self.channels[index]

    def set_volume(self, volume):
        pass

    def play_synth(self):
        self.playing = True


class SoundTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.multiple(config, TICK_ENABLED=True, BEEP_ENABLED=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.unicorn = FakeUnicorn()
        self.tick_ch, self.beep_ch = self.unicorn.channels
        self.sound = Sound(self.unicorn, FakeChannel)

    def _play_through(self, start, end):
        for now in range(start, end):
            self.sound.update(now)

    def test_melody_plays_notes_in_order_with_gaps(self):
        self.sound.play(MELODY, 0)
        self.sound.update(0)
        self.assertEqual(self.beep_ch.events, [("freq", 1000), ("attack",)])
        self._play_through(1, 100)
        self.assertEqual(len(self.beep_ch.events), 2)
        self.sound.update(100)
        self.assertEqual(self.beep_ch.events[2], ("release",))
        self._play_through(101, 100 + sound._NOTE_GAP_MS)
        self.assertEqual(len(self.beep_ch.events), 3)
        second_start = 100 + sound._NOTE_GAP_MS
        self.sound.update(second_start)
        self.assertEqual(self.beep_ch.events[3:], [("freq", 2000), ("attack",)])
        self._play_through(second_start + 1, second_start + 200)
        self.assertTrue(self.sound.busy())
        self.sound.update(second_start + 200)
        self.assertEqual(self.beep_ch.events[-1], ("release",))
        self.assertFalse(self.sound.busy())

    def test_busy_until_the_last_note_is_released(self):
        self.assertFalse(self.sound.busy())
        self.sound.play(MELODY, 0)
        self.assertTrue(self.sound.busy())
        now = 0
        while self.sound.busy():
            self.sound.update(now)
            now += 1
            self.assertLess(now, 1000, "melody never finished")
        self.assertEqual(self.beep_ch.events.count(("release",)), len(MELODY))

    def test_empty_melody_is_ignored(self):
        self.sound.play((), 0)
        self.sound.update(0)
        self.assertFalse(self.sound.busy())
        self.assertEqual(self.beep_ch.events, [])

    def test_tick_is_released_after_tick_ms(self):
        self.sound.tick(0)
        self.assertTrue(self.sound.busy())
        self.sound.update(config.TICK_MS - 1)
        self.assertEqual(self.tick_ch.events[-1], ("attack",))
        self.sound.update(config.TICK_MS)
        self.assertEqual(self.tick_ch.events[-1], ("release",))
        self.assertFalse(self.sound.busy())

    def test_melody_across_ticks_wraparound(self):
        start = (1 << 30) - 50
        self.sound.play(MELODY, start)
        now = start
        while self.sound.busy():
            self.sound.update(now)
            now = ticks_add(now, 1)
        self.assertEqual(self.beep_ch.events.count(("attack",)), len(MELODY))

    def test_disabled_sound_never_touches_the_synth(self):
        with mock.patch.multiple(config, TICK_ENABLED=False, BEEP_ENABLED=False):
            unicorn = FakeUnicorn()
            quiet = Sound(unicorn, FakeChannel)
            quiet.tick(0)
            quiet.play(MELODY, 0)
            quiet.update(0)
        self.assertFalse(unicorn.playing)
        self.assertFalse(quiet.busy())
