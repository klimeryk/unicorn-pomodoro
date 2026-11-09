# Hardware-free so it runs on host CPython too; every timestamp is a
# ticks_ms value supplied by the caller.

from compat import ticks_add, ticks_diff

READY = "ready"
WORK = "work"
SHORT_BREAK = "short_break"
LONG_BREAK = "long_break"

WORK_DONE = "work_done"
BREAK_DONE = "break_done"


class Pomodoro:
    def __init__(self, work_s, short_break_s, long_break_s, sessions_per_cycle):
        self._durations_ms = {
            WORK: work_s * 1000,
            SHORT_BREAK: short_break_s * 1000,
            LONG_BREAK: long_break_s * 1000,
        }
        self.sessions_per_cycle = sessions_per_cycle
        self.state = READY
        self.completed_sessions = 0
        self._deadline = 0

    def start(self, now):
        if self.state == READY:
            self.state = WORK
            self._deadline = ticks_add(now, self._durations_ms[WORK])

    def postpone(self, ms):
        if self.state != READY:
            self._deadline = ticks_add(self._deadline, ms)

    def reset(self):
        self.state = READY
        self.completed_sessions = 0

    def poll(self, now):
        if self.state == READY or ticks_diff(self._deadline, now) > 0:
            return None
        if self.state == WORK:
            self.completed_sessions += 1
            if self.completed_sessions >= self.sessions_per_cycle:
                self.state = LONG_BREAK
            else:
                self.state = SHORT_BREAK
            self._deadline = ticks_add(self._deadline, self._durations_ms[self.state])
            return WORK_DONE
        if self.state == LONG_BREAK:
            self.completed_sessions = 0
        self.state = READY
        return BREAK_DONE

    def _remaining_ms(self, now):
        return max(0, ticks_diff(self._deadline, now))

    def remaining_seconds(self, now):
        if self.state == READY:
            return 0
        return (self._remaining_ms(now) + 999) // 1000

    def remaining_fraction(self, now):
        if self.state == READY:
            return 0.0
        phase_ms = self._durations_ms[self.state]
        return min(self._remaining_ms(now), phase_ms) / phase_ms
