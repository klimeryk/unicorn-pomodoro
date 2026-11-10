import unittest

from compat import ticks_add
from pomodoro import (
    BREAK_DONE,
    LONG_BREAK,
    READY,
    SHORT_BREAK,
    WORK,
    WORK_DONE,
    Pomodoro,
)

WORK_S = 25 * 60
SHORT_BREAK_S = 5 * 60
LONG_BREAK_S = 15 * 60
SESSIONS_PER_CYCLE = 4

WORK_MS = WORK_S * 1000
SHORT_BREAK_MS = SHORT_BREAK_S * 1000
LONG_BREAK_MS = LONG_BREAK_S * 1000
EFFECT_PAD_MS = 1800


class PomodoroTest(unittest.TestCase):
    def setUp(self):
        self.pomodoro = Pomodoro(
            WORK_S, SHORT_BREAK_S, LONG_BREAK_S, SESSIONS_PER_CYCLE
        )

    def _run_session(self, start):
        self.pomodoro.start(start)
        work_end = start + WORK_MS
        self.assertEqual(self.pomodoro.poll(work_end), WORK_DONE)
        break_ms = (
            LONG_BREAK_MS if self.pomodoro.state == LONG_BREAK else SHORT_BREAK_MS
        )
        break_end = work_end + break_ms
        self.assertEqual(self.pomodoro.poll(break_end), BREAK_DONE)
        return break_end

    def test_starts_ready_with_no_completed_sessions(self):
        self.assertEqual(self.pomodoro.state, READY)
        self.assertEqual(self.pomodoro.completed_sessions, 0)
        self.assertEqual(self.pomodoro.remaining_seconds(0), 0)
        self.assertEqual(self.pomodoro.remaining_fraction(0), 0.0)

    def test_poll_does_nothing_while_ready(self):
        self.assertIsNone(self.pomodoro.poll(10 * WORK_MS))
        self.assertEqual(self.pomodoro.state, READY)

    def test_work_runs_for_its_full_duration(self):
        self.pomodoro.start(1000)
        self.assertEqual(self.pomodoro.state, WORK)
        self.assertEqual(self.pomodoro.remaining_seconds(1000), WORK_S)
        self.assertIsNone(self.pomodoro.poll(1000 + WORK_MS - 1))
        self.assertEqual(self.pomodoro.poll(1000 + WORK_MS), WORK_DONE)

    def test_full_cycle_ends_with_long_break_then_starts_over(self):
        now = 0
        for session in range(1, SESSIONS_PER_CYCLE + 1):
            self.pomodoro.start(now)
            now += WORK_MS
            self.assertEqual(self.pomodoro.poll(now), WORK_DONE)
            self.assertEqual(self.pomodoro.completed_sessions, session)
            if session < SESSIONS_PER_CYCLE:
                self.assertEqual(self.pomodoro.state, SHORT_BREAK)
                self.assertEqual(self.pomodoro.remaining_seconds(now), SHORT_BREAK_S)
                now += SHORT_BREAK_MS
            else:
                self.assertEqual(self.pomodoro.state, LONG_BREAK)
                self.assertEqual(self.pomodoro.remaining_seconds(now), LONG_BREAK_S)
                now += LONG_BREAK_MS
            self.assertEqual(self.pomodoro.poll(now), BREAK_DONE)
            self.assertEqual(self.pomodoro.state, READY)
        self.assertEqual(self.pomodoro.completed_sessions, 0)

    def test_break_waits_in_ready_for_next_start(self):
        end = self._run_session(0)
        self.assertIsNone(self.pomodoro.poll(end + WORK_MS))
        self.assertEqual(self.pomodoro.state, READY)
        self.assertEqual(self.pomodoro.completed_sessions, 1)

    def test_countdown_rounds_up_to_whole_seconds(self):
        self.pomodoro.start(0)
        self.assertEqual(self.pomodoro.remaining_seconds(1), WORK_S)
        self.assertEqual(self.pomodoro.remaining_seconds(1000), WORK_S - 1)
        self.assertEqual(self.pomodoro.remaining_seconds(WORK_MS + 5000), 0)

    def test_start_is_ignored_while_running(self):
        self.pomodoro.start(0)
        self.pomodoro.start(60_000)
        self.assertEqual(self.pomodoro.poll(WORK_MS), WORK_DONE)

    def test_reset_mid_session_returns_to_ready(self):
        now = self._run_session(0)
        now = self._run_session(now)
        self.assertEqual(self.pomodoro.completed_sessions, 2)
        self.pomodoro.start(now)
        self.pomodoro.reset()
        self.assertEqual(self.pomodoro.state, READY)
        self.assertEqual(self.pomodoro.completed_sessions, 0)
        self.assertEqual(self.pomodoro.remaining_seconds(now + 1000), 0)
        self.assertIsNone(self.pomodoro.poll(now + 2 * WORK_MS))

    def test_remaining_fraction_tracks_current_phase(self):
        self.pomodoro.start(0)
        self.assertEqual(self.pomodoro.remaining_fraction(0), 1.0)
        self.assertEqual(self.pomodoro.remaining_fraction(WORK_MS // 2), 0.5)
        self.pomodoro.poll(WORK_MS)
        self.assertEqual(self.pomodoro.remaining_fraction(WORK_MS), 1.0)
        halfway_through_break = WORK_MS + SHORT_BREAK_MS // 2
        self.assertEqual(self.pomodoro.remaining_fraction(halfway_through_break), 0.5)
        self.assertEqual(self.pomodoro.remaining_fraction(2 * WORK_MS), 0.0)

    def test_next_phase_is_timed_from_deadline_not_poll_time(self):
        self.pomodoro.start(0)
        late_poll = WORK_MS + 900
        self.assertEqual(self.pomodoro.poll(late_poll), WORK_DONE)
        self.assertEqual(
            self.pomodoro.remaining_seconds(WORK_MS + 1000), SHORT_BREAK_S - 1
        )

    def test_postpone_extends_current_phase(self):
        self.pomodoro.start(0)
        self.pomodoro.poll(WORK_MS)
        self.pomodoro.postpone(EFFECT_PAD_MS)
        break_end = WORK_MS + SHORT_BREAK_MS + EFFECT_PAD_MS
        self.assertEqual(
            self.pomodoro.remaining_seconds(WORK_MS + EFFECT_PAD_MS), SHORT_BREAK_S
        )
        self.assertIsNone(self.pomodoro.poll(break_end - 1))
        self.assertEqual(self.pomodoro.poll(break_end), BREAK_DONE)

    def test_postponed_phase_shows_full_progress_until_pad_elapses(self):
        self.pomodoro.start(0)
        self.pomodoro.poll(WORK_MS)
        self.pomodoro.postpone(EFFECT_PAD_MS)
        self.assertEqual(self.pomodoro.remaining_fraction(WORK_MS), 1.0)

    def test_postpone_is_ignored_while_ready(self):
        self.pomodoro.postpone(EFFECT_PAD_MS)
        self.pomodoro.start(0)
        self.assertEqual(self.pomodoro.remaining_seconds(0), WORK_S)
        self.assertEqual(self.pomodoro.poll(WORK_MS), WORK_DONE)

    def test_phases_run_across_ticks_wraparound(self):
        start = (1 << 30) - WORK_MS // 2
        self.pomodoro.start(start)
        work_end = ticks_add(start, WORK_MS)
        self.assertLess(work_end, start)
        self.assertEqual(self.pomodoro.remaining_seconds(start), WORK_S)
        self.assertIsNone(self.pomodoro.poll(ticks_add(work_end, -1)))
        self.assertEqual(self.pomodoro.poll(work_end), WORK_DONE)
        break_end = ticks_add(work_end, SHORT_BREAK_MS)
        self.assertEqual(self.pomodoro.remaining_seconds(work_end), SHORT_BREAK_S)
        self.assertIsNone(self.pomodoro.poll(ticks_add(break_end, -1)))
        self.assertEqual(self.pomodoro.poll(break_end), BREAK_DONE)
