import json

import config
from compat import ticks_diff

# Holding LUX/VOL changes the level every frame; waiting until it settles
# turns a long press into a single flash write.
SAVE_DELAY_MS = 1000


def _read_level(data, key, default):
    try:
        value = float(data[key])
    except (KeyError, TypeError, ValueError):
        return default
    return min(max(value, 0.0), 1.0)


def load(path):
    try:
        with open(path) as f:
            data = json.loads(f.read())
    except (OSError, ValueError):
        data = {}
    return (
        _read_level(data, "brightness", config.DEFAULT_BRIGHTNESS),
        _read_level(data, "volume", config.DEFAULT_VOLUME),
    )


class Settings:
    def __init__(self, path, brightness, volume):
        self._path = path
        self._saved = (brightness, volume)
        self._pending = self._saved
        self._changed_at = 0

    def poll(self, now, brightness, volume):
        if brightness != self._pending[0] or volume != self._pending[1]:
            self._pending = (brightness, volume)
            self._changed_at = now
            return
        if self._pending == self._saved:
            return
        if ticks_diff(now, self._changed_at) < SAVE_DELAY_MS:
            return
        # Marked saved even if the write fails, so a full or read-only
        # filesystem costs one attempt rather than one per frame.
        self._saved = self._pending
        try:
            with open(self._path, "w") as f:
                f.write(json.dumps({"brightness": brightness, "volume": volume}))
        except OSError:
            pass
