# Stand-ins for MicroPython builtins so the hardware-free modules also run
# (and are tested) on host CPython.

try:
    from time import ticks_add, ticks_diff
except ImportError:

    def ticks_add(ticks, delta):
        return ticks + delta

    def ticks_diff(end, start):
        return end - start


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
