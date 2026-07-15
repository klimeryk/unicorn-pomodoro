# Host-side test of the Pomodoro state machine (no hardware needed):
#   python3 tests/test_pomodoro.py

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pomodoro import (
    BREAK_DONE,
    LONG_BREAK,
    READY,
    SHORT_BREAK,
    WORK,
    WORK_DONE,
    Pomodoro,
)

WORK_S, SHORT_S, LONG_S, CYCLE = 25 * 60, 5 * 60, 25 * 60, 4


def test_full_cycle():
    p = Pomodoro(WORK_S, SHORT_S, LONG_S, CYCLE)
    t = 1000
    assert p.state == READY and p.session == 1 and p.completed == 0

    for session in range(1, CYCLE + 1):
        assert p.state == READY and p.session == session
        p.start(t)
        assert p.state == WORK
        assert p.remaining_seconds(t) == WORK_S
        assert p.poll(t + WORK_S * 1000 - 1) is None

        t += WORK_S * 1000
        assert p.poll(t) == WORK_DONE
        assert p.completed == session
        expected_break = LONG_BREAK if session == CYCLE else SHORT_BREAK
        assert p.state == expected_break, p.state
        break_s = LONG_S if session == CYCLE else SHORT_S
        assert p.remaining_seconds(t) == break_s

        t += break_s * 1000
        assert p.poll(t) == BREAK_DONE
        assert p.state == READY

    assert p.session == 1 and p.completed == 0
    print("full cycle: OK")


def test_ceil_countdown():
    p = Pomodoro(WORK_S, SHORT_S, LONG_S, CYCLE)
    p.start(0)
    assert p.remaining_seconds(1) == WORK_S
    assert p.remaining_seconds(1000) == WORK_S - 1
    assert p.remaining_seconds(WORK_S * 1000 + 5000) == 0
    print("ceil countdown: OK")


def test_reset_mid_work():
    p = Pomodoro(WORK_S, SHORT_S, LONG_S, CYCLE)
    for _ in range(2):
        p.start(0)
        p.poll(WORK_S * 1000)
        p.poll((WORK_S + SHORT_S) * 1000)
    assert p.session == 3 and p.completed == 2
    p.start(0)
    p.reset()
    assert p.state == READY and p.session == 1 and p.completed == 0
    assert p.remaining_seconds(1000) == 0
    assert p.poll(WORK_S * 2000) is None
    print("reset mid-work: OK")


def test_remaining_fraction():
    p = Pomodoro(WORK_S, SHORT_S, LONG_S, CYCLE)
    assert p.remaining_fraction(0) == 0.0
    p.start(0)
    assert p.remaining_fraction(0) == 1.0
    assert p.remaining_fraction(WORK_S * 500) == 0.5
    assert p.remaining_fraction(WORK_S * 1000 + 5000) == 0.0
    print("remaining fraction: OK")


def test_no_drift_between_phases():
    p = Pomodoro(WORK_S, SHORT_S, LONG_S, CYCLE)
    p.start(0)
    assert p.poll(WORK_S * 1000 + 900) == WORK_DONE
    assert p.remaining_seconds(WORK_S * 1000 + 1000) == SHORT_S - 1
    print("no drift between phases: OK")


def test_postpone_shifts_deadline():
    p = Pomodoro(WORK_S, SHORT_S, LONG_S, CYCLE)
    p.start(0)
    assert p.poll(WORK_S * 1000) == WORK_DONE
    p.postpone(1800)
    assert p.remaining_seconds(WORK_S * 1000 + 1800) == SHORT_S
    assert p.poll((WORK_S + SHORT_S) * 1000 + 1799) is None
    assert p.poll((WORK_S + SHORT_S) * 1000 + 1800) == BREAK_DONE
    print("postpone shifts deadline: OK")


def test_postpone_noop_when_ready():
    p = Pomodoro(WORK_S, SHORT_S, LONG_S, CYCLE)
    p.postpone(1800)
    assert p._deadline == 0
    p.start(0)
    assert p.remaining_seconds(0) == WORK_S
    print("postpone no-op when ready: OK")


if __name__ == "__main__":
    test_full_cycle()
    test_ceil_countdown()
    test_reset_mid_work()
    test_remaining_fraction()
    test_no_drift_between_phases()
    test_postpone_shifts_deadline()
    test_postpone_noop_when_ready()
    print("all pomodoro tests passed")
