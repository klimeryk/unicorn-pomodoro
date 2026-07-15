# Pomodoro state machine. No hardware imports so it also runs on host
# CPython (see tests/test_pomodoro.py). All timestamps are ticks_ms values
# supplied by the caller.

try:
    from time import ticks_add, ticks_diff
except ImportError:

    def ticks_add(t, delta):
        return t + delta

    def ticks_diff(a, b):
        return a - b


READY = "ready"
WORK = "work"
SHORT_BREAK = "short_break"
LONG_BREAK = "long_break"

WORK_DONE = "work_done"
BREAK_DONE = "break_done"

BREAK_STATES = (SHORT_BREAK, LONG_BREAK)


class Pomodoro:
    def __init__(self, work_s, short_break_s, long_break_s, sessions_per_cycle):
        self._durations_ms = {
            WORK: work_s * 1000,
            SHORT_BREAK: short_break_s * 1000,
            LONG_BREAK: long_break_s * 1000,
        }
        self.sessions_per_cycle = sessions_per_cycle
        self.state = READY
        self.session = 1
        self.completed = 0
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
        self.session = 1
        self.completed = 0

    def poll(self, now):
        if self.state == READY or ticks_diff(self._deadline, now) > 0:
            return None
        if self.state == WORK:
            self.completed += 1
            next_state = (
                LONG_BREAK if self.session >= self.sessions_per_cycle else SHORT_BREAK
            )
            self.state = next_state
            self._deadline = ticks_add(self._deadline, self._durations_ms[next_state])
            return WORK_DONE
        if self.state == LONG_BREAK:
            self.session = 1
            self.completed = 0
        else:
            self.session += 1
        self.state = READY
        return BREAK_DONE

    def remaining_seconds(self, now):
        if self.state == READY:
            return 0
        ms = ticks_diff(self._deadline, now)
        if ms < 0:
            ms = 0
        return (ms + 999) // 1000

    def remaining_fraction(self, now):
        if self.state == READY:
            return 0.0
        total = self._durations_ms[self.state]
        ms = ticks_diff(self._deadline, now)
        if ms < 0:
            ms = 0
        elif ms > total:
            ms = total
        return ms / total
