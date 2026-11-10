# Stand-ins for MicroPython builtins so the hardware-free modules also run
# (and are tested) on host CPython.

try:
    from time import ticks_add, ticks_diff
except ImportError:
    # Same wraparound as MicroPython's ticks_ms (period 2**30) so host tests
    # exercise it.
    _TICKS_PERIOD = 1 << 30
    _TICKS_HALF = _TICKS_PERIOD // 2

    def ticks_add(ticks, delta):
        return (ticks + delta) % _TICKS_PERIOD

    def ticks_diff(end, start):
        return (end - start + _TICKS_HALF) % _TICKS_PERIOD - _TICKS_HALF


try:
    import micropython
except ImportError:
    # Importers must keep spelling the decorator `@micropython.native`: the
    # MicroPython compiler only recognizes that exact name.
    class micropython:
        @staticmethod
        def native(function):
            return function


__all__ = ["micropython", "ticks_add", "ticks_diff"]
