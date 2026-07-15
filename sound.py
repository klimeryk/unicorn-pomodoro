from time import ticks_add, ticks_diff

import config

_NOTE_GAP_MS = 40


class Sound:
    def __init__(self, su, channel_cls):
        self.enabled = config.TICK_ENABLED or config.BEEP_ENABLED
        self._tick_off_at = None
        self._note_off_at = None
        self._next_note_at = None
        self._queue = []
        if not self.enabled:
            return
        self._tick_ch = su.synth_channel(0)
        self._tick_ch.configure(
            waveforms=channel_cls.TRIANGLE,
            attack=0.002,
            decay=0.02,
            sustain=0.0,
            release=0.02,
            volume=config.TICK_VOLUME,
        )
        self._beep_ch = su.synth_channel(1)
        self._beep_ch.configure(
            waveforms=channel_cls.SINE,
            attack=0.005,
            decay=0.05,
            sustain=0.6,
            release=0.05,
            volume=config.BEEP_VOLUME,
        )
        su.set_volume(config.DEFAULT_VOLUME)
        su.play_synth()

    def tick(self, now):
        if not config.TICK_ENABLED:
            return
        self._tick_ch.frequency(config.TICK_FREQ)
        self._tick_ch.trigger_attack()
        self._tick_off_at = ticks_add(now, config.TICK_MS)

    def play(self, melody, now):
        if not config.BEEP_ENABLED:
            return
        self._queue = list(melody)
        self._note_off_at = None
        self._next_note_at = now

    def update(self, now):
        if not self.enabled:
            return
        if self._tick_off_at is not None and ticks_diff(now, self._tick_off_at) >= 0:
            self._tick_ch.trigger_release()
            self._tick_off_at = None
        if self._note_off_at is not None and ticks_diff(now, self._note_off_at) >= 0:
            self._beep_ch.trigger_release()
            self._note_off_at = None
            if self._queue:
                self._next_note_at = ticks_add(now, _NOTE_GAP_MS)
        if self._next_note_at is not None and ticks_diff(now, self._next_note_at) >= 0:
            self._next_note_at = None
            freq, duration_ms = self._queue.pop(0)
            self._beep_ch.frequency(freq)
            self._beep_ch.trigger_attack()
            self._note_off_at = ticks_add(now, duration_ms)
