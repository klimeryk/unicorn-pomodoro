# Unicorn Pomodoro — a garmodoro-style Pomodoro timer for Pimoroni Unicorn
# boards. Board selection and all tunables live in config.py.
#
# Buttons:
#   A        start a session (Ready state) / back to Pomodoro (clock mode)
#   B        reset: press once for "Reset?", again to confirm
#   D        clock mode (stops and resets any running Pomodoro)
#   LUX +/-  brightness, VOL +/- volume

import gc
import time

from picographics import PicoGraphics

import board
import config
import effects
import settings
from net_time import NetworkTime
from pomodoro import BREAK_DONE, READY, WORK, WORK_DONE, Pomodoro
from sound import Sound
from ui import BLACK, UI

MODE_POMODORO = "pomodoro"
MODE_CLOCK = "clock"

LEVEL_STEP = 0.01
GC_INTERVAL_MS = 1000
DEBOUNCE_MS = 30
FRAME_MS = 1000 // config.FPS


def read_file(path):
    with open(path, "rb") as f:
        return f.read()


class Button:
    def __init__(self, unicorn, switch):
        self._unicorn = unicorn
        self._switch = switch
        self._was_down = False
        self._changed_at = 0

    def just_pressed(self, now):
        down = self._unicorn.is_pressed(self._switch)
        if down == self._was_down:
            return False
        # Negative diffs mean the last change was so long ago that ticks
        # wrapped; only a recent change counts as contact bounce.
        if 0 <= time.ticks_diff(now, self._changed_at) < DEBOUNCE_MS:
            return False
        self._was_down = down
        self._changed_at = now
        return down


class App:
    def __init__(self):
        self.unicorn = board.Unicorn()
        self.graphics = PicoGraphics(display=board.DISPLAY)
        brightness, volume = settings.load(config.SETTINGS_FILE)
        self.unicorn.set_brightness(brightness)
        self.ui = UI(
            self.graphics,
            board.WIDTH,
            board.HEIGHT,
            board.BUTTON_A_HINT_PIXELS,
            read_file("3x5.bitmapfont"),
            read_file("MatrixChunky8x6.bitmapfont"),
            read_file("MatrixLight8x6.bitmapfont"),
        )
        self.sound = Sound(self.unicorn, board.Channel, volume)
        # Seeded from the firmware's readback so its float rounding doesn't
        # look like a change and rewrite the file on every boot.
        self.settings = settings.Settings(
            config.SETTINGS_FILE,
            self.unicorn.get_brightness(),
            self.unicorn.get_volume(),
        )
        self.burst = effects.Burst(
            self.graphics,
            board.WIDTH,
            board.HEIGHT,
            config.TOMATO_RED,
            config.STEM_GREEN,
        )
        self.rings = effects.Rings(
            self.graphics, board.WIDTH, board.HEIGHT, config.COLOR_READY
        )
        self.hour_flash = effects.HourFlash() if config.CLOCK_HOURLY_FLASH else None
        self.pomodoro = Pomodoro(
            config.WORK_S,
            config.SHORT_BREAK_S,
            config.LONG_BREAK_S,
            config.SESSIONS_PER_CYCLE,
        )
        self.network_time = NetworkTime()

        self.button_a = Button(self.unicorn, board.Unicorn.SWITCH_A)
        self.button_b = Button(self.unicorn, board.Unicorn.SWITCH_B)
        self.button_c = Button(self.unicorn, board.Unicorn.SWITCH_C)
        self.button_d = Button(self.unicorn, board.Unicorn.SWITCH_D)

        self.mode = MODE_CLOCK if config.BOOT_MODE == MODE_CLOCK else MODE_POMODORO
        self.reset_prompt_deadline = None
        self.effect = None
        self.last_ticked_s = None
        self.last_gc = 0

    def run(self):
        self.ui.render_boot()
        self.unicorn.update(self.graphics)
        # The first poll powers up the WiFi chip; let that happen behind
        # the boot screen.
        self.network_time.poll(time.ticks_ms())
        gc.collect()
        self.last_gc = time.ticks_ms()
        next_frame = time.ticks_ms()
        while True:
            now = time.ticks_ms()
            self._collect_garbage(now)
            self._handle_buttons(now)
            self._adjust_while_held(
                board.Unicorn.SWITCH_BRIGHTNESS_UP,
                board.Unicorn.SWITCH_BRIGHTNESS_DOWN,
                self.unicorn.adjust_brightness,
            )
            self._adjust_while_held(
                board.Unicorn.SWITCH_VOLUME_UP,
                board.Unicorn.SWITCH_VOLUME_DOWN,
                self.unicorn.adjust_volume,
            )
            # A flash write stalls the loop, which would hold a sounding note.
            if not self.sound.busy():
                self.settings.poll(
                    now, self.unicorn.get_brightness(), self.unicorn.get_volume()
                )
            self._advance_timer(now)
            if self.effect is not None and self.effect.done(now):
                self.effect = None
            if self._idle():
                self.network_time.poll(now)
            self._render(now)
            next_frame = time.ticks_add(next_frame, FRAME_MS)
            delay_ms = time.ticks_diff(next_frame, time.ticks_ms())
            if delay_ms > 0:
                time.sleep_ms(delay_ms)
            else:
                next_frame = time.ticks_ms()

    def _idle(self):
        # The synth plays from an IRQ, so a note sounding during a blocking
        # NTP attempt would hang until the loop resumes.
        return (
            (self.mode == MODE_CLOCK or self.pomodoro.state == READY)
            and self.effect is None
            and not self.sound.busy()
        )

    def _collect_garbage(self, now):
        if time.ticks_diff(now, self.last_gc) >= GC_INTERVAL_MS:
            gc.collect()
            self.last_gc = now

    def _reset_session(self):
        self.pomodoro.reset()
        self.effect = None

    def _handle_buttons(self, now):
        a = self.button_a.just_pressed(now)
        b = self.button_b.just_pressed(now)
        c = self.button_c.just_pressed(now)
        d = self.button_d.just_pressed(now)
        if self.reset_prompt_deadline is not None:
            if b:
                self._reset_session()
                self.reset_prompt_deadline = None
            elif a or c or d or time.ticks_diff(self.reset_prompt_deadline, now) <= 0:
                self.reset_prompt_deadline = None
        elif self.mode == MODE_CLOCK:
            if a:
                self.mode = MODE_POMODORO
        else:
            if a:
                self.pomodoro.start(now)
            if b:
                self.reset_prompt_deadline = time.ticks_add(
                    now, config.RESET_CONFIRM_TIMEOUT_S * 1000
                )
            if d:
                self._reset_session()
                self.mode = MODE_CLOCK

    def _adjust_while_held(self, up_switch, down_switch, adjust):
        if self.unicorn.is_pressed(up_switch):
            adjust(LEVEL_STEP)
        if self.unicorn.is_pressed(down_switch):
            adjust(-LEVEL_STEP)

    def _play_transition(self, melody, effect, now):
        self.sound.play(melody, now)
        self.effect = effect
        effect.start(now)

    def _advance_timer(self, now):
        event = self.pomodoro.poll(now)
        if event == WORK_DONE:
            self._play_transition(config.WORK_DONE_MELODY, self.burst, now)
            self.pomodoro.postpone(int(self.burst.DURATION_S * 1000))
        elif event == BREAK_DONE:
            self._play_transition(config.BREAK_DONE_MELODY, self.rings, now)

        remaining_s = self.pomodoro.remaining_seconds(now)
        if self.pomodoro.state == WORK and remaining_s != self.last_ticked_s:
            self.last_ticked_s = remaining_s
            self.sound.tick(now)
        self.sound.update(now)

    def _render(self, now):
        hms = self.network_time.local_hms()
        digit_color, background = config.COLOR_CLOCK_BIG, BLACK
        if self.hour_flash is not None:
            digit_color, background = self.hour_flash.update(now, hms)

        if self.reset_prompt_deadline is not None:
            self.ui.render_reset_confirm(now)
        elif self.effect is not None:
            self.effect.draw(now)
        elif self.mode == MODE_CLOCK:
            self.ui.render_clock(hms, digit_color, background)
        else:
            self.ui.render_pomodoro(
                now,
                self.pomodoro.state,
                self.pomodoro.remaining_seconds(now),
                self.pomodoro.remaining_fraction(now),
                self.pomodoro.completed_sessions,
                hms,
            )
        self.unicorn.update(self.graphics)


App().run()
