import math

import config
from pomodoro import LONG_BREAK, READY, SHORT_BREAK, WORK

SMALL_GLYPH_H = 5
SMALL_DIGIT_PITCH = 4
BIG_GLYPH_H = 7
BIG_DIGIT_PITCH = 6

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

BOOT_LABEL = "....."
READY_LABEL = "Ready"
RESET_LABEL = "Reset?"
RESET_LABEL_SHORT = "RST?"

STATE_COLORS = {
    READY: config.COLOR_READY,
    WORK: config.COLOR_WORK,
    SHORT_BREAK: config.COLOR_BREAK,
    LONG_BREAK: config.COLOR_LONG_BREAK,
}


def _pad_leading(n):
    # str.rjust isn't in Pimoroni's MicroPython; values are always 1-2 digits.
    digits = str(n)
    return config.TIME_PAD_CHAR + digits if len(digits) < 2 else digits


def _two_digits(n):
    return f"{n:02d}"


class UI:
    def __init__(
        self,
        graphics,
        width,
        height,
        button_a_hint_pixels,
        small_font=None,
        hour_font=None,
        minute_font=None,
    ):
        self.g = graphics
        self.w = width
        self.h = height
        self.button_a_hint_pixels = button_a_hint_pixels
        self.border_rings = min(config.LAYOUT["rings"], len(config.RING_FADE))
        self.scale = config.LAYOUT["scale"]
        self.horizontal = config.LAYOUT["horizontal"]
        self._small_font = small_font
        self._hour_font = hour_font
        self._minute_font = minute_font
        self._current_font = None
        self._set_font(small_font)

        self.x_dots = width // 2
        if self.horizontal:
            self.x_main = width * 3 // 10
            self.y_main = self._y_centered(self.scale)
            self.x_clock = width * 3 // 4
            self.y_clock = self._y_centered(1)
            self.y_dots = height - 3
            self.y_bar = height - 1
        else:
            self.x_main = width // 2
            self.y_main = 1
            self.x_clock = width // 2
            self.y_clock = height - SMALL_GLYPH_H
            self.y_bar = self.y_clock - 1 - self.scale
            self.y_dots = (self.y_main + SMALL_GLYPH_H * self.scale + self.y_bar) // 2

    def _y_centered(self, scale):
        return (self.h - SMALL_GLYPH_H * scale) // 2

    def _set_font(self, font):
        if font is not self._current_font:
            self.g.set_font(font)
            self._current_font = font

    def _pen(self, color, brightness=1.0):
        return self.g.create_pen(
            int(color[0] * brightness),
            int(color[1] * brightness),
            int(color[2] * brightness),
        )

    def _clear(self, color=BLACK):
        self.g.set_pen(self._pen(color))
        self.g.clear()

    def _border(self, color):
        for ring in range(self.border_rings):
            self.g.set_pen(self._pen(color, config.RING_FADE[ring]))
            w = self.w - 2 * ring
            h = self.h - 2 * ring
            self.g.rectangle(ring, ring, w, 1)
            self.g.rectangle(ring, self.h - 1 - ring, w, 1)
            self.g.rectangle(ring, ring + 1, 1, h - 2)
            self.g.rectangle(self.w - 1 - ring, ring + 1, 1, h - 2)

    def _pulse(self, now):
        low = config.PULSE_MIN_BRIGHTNESS
        half_range = (config.PULSE_MAX_BRIGHTNESS - low) / 2
        # Reduce in ints first: rp2 floats are single precision, and raw
        # ticks (up to 2**30) would make the phase step visibly.
        period = config.PULSE_PERIOD_MS
        phase = (now % period) * 2 * math.pi / period
        return low + half_range * (math.sin(phase) + 1)

    def _draw_digits(self, text, x, y, step, scale):
        for ch in text:
            self.g.text(ch, x, y, -1, scale)
            x += step
        return x

    def _draw_colon(self, x, y, glyph_h, scale, pen):
        middle = glyph_h // 2
        self.g.set_pen(pen)
        self.g.rectangle(x, y + (middle - 1) * scale, scale, scale)
        self.g.rectangle(x, y + (middle + 1) * scale, scale, scale)

    def _draw_time(
        self, major, minor, x_center, y, scale, color, minor_brightness, colon_visible
    ):
        step = SMALL_DIGIT_PITCH * scale
        width = step * (len(major) + len(minor)) - scale
        x = max(0, x_center - (width + 1) // 2)
        self.g.set_pen(self._pen(color))
        x = self._draw_digits(major, x, y, step, scale)
        self.g.set_pen(self._pen(color, minor_brightness))
        self._draw_digits(minor, x, y, step, scale)
        if colon_visible:
            colon_pen = self._pen(config.COLOR_CLOCK, config.CLOCK_COLON_BRIGHTNESS)
            self._draw_colon(x - scale, y, SMALL_GLYPH_H, scale, colon_pen)

    def _draw_label(self, text, x_center, y, color, scale, now):
        width = self.g.measure_text(text, scale)
        self.g.set_pen(self._pen(color))
        if width <= self.w:
            self.g.text(text, x_center - width // 2, y, -1, scale)
        else:
            offset = (now // config.SCROLL_MS) % (width + self.w)
            self.g.text(text, self.w - offset, y, -1, scale)

    def _draw_button_a_hint(self, now):
        self.g.set_pen(self._pen(WHITE, self._pulse(now)))
        for x, y in self.button_a_hint_pixels:
            self.g.pixel(x, y)

    def _draw_session_dots(self, completed_sessions, working, now):
        total = config.SESSIONS_PER_CYCLE
        s = self.scale
        x = self.x_dots - ((2 * total - 1) * s) // 2
        for i in range(total):
            if i < completed_sessions:
                pen = self._pen(config.COLOR_DOT_DONE)
            elif i == completed_sessions and working:
                pen = self._pen(config.COLOR_DOT_DONE, self._pulse(now))
            else:
                pen = self._pen(config.COLOR_DOT_PENDING)
            self.g.set_pen(pen)
            self.g.rectangle(x, self.y_dots, s, s)
            x += 2 * s

    def _draw_progress_bar(self, fraction, color):
        lit = fraction * self.w
        full = int(lit)
        if full:
            self.g.set_pen(self._pen(color))
            self.g.rectangle(0, self.y_bar, full, self.scale)
        tip = lit - full
        if full < self.w and tip:
            self.g.set_pen(self._pen(color, tip))
            self.g.rectangle(full, self.y_bar, 1, self.scale)

    def _clock_digits(self, hms):
        hours = hms[0]
        if not config.CLOCK_24H:
            hours = (hours + 11) % 12 + 1
        return _pad_leading(hours), _two_digits(hms[1])

    def render_boot(self):
        self._set_font(self._small_font)
        self._clear()
        y = self._y_centered(1)
        self._draw_label(BOOT_LABEL, self.w // 2, y, config.COLOR_CLOCK, 1, 0)

    def render_pomodoro(
        self, now, state, remaining_s, remaining_fraction, completed_sessions, hms
    ):
        self._set_font(self._small_font)
        self._clear()
        color = STATE_COLORS[state]
        if state == READY:
            self._draw_label(
                READY_LABEL, self.x_main, self.y_main, color, self.scale, now
            )
            self._draw_button_a_hint(now)
        else:
            self._draw_time(
                _pad_leading(remaining_s // 60),
                _two_digits(remaining_s % 60),
                self.x_main,
                self.y_main,
                self.scale,
                color,
                config.POMODORO_SECONDS_BRIGHTNESS,
                remaining_s % 2 == 0,
            )
            self._draw_progress_bar(remaining_fraction, color)
        self._draw_session_dots(completed_sessions, state == WORK, now)
        if hms:
            hours, minutes = self._clock_digits(hms)
            self._draw_time(
                hours,
                minutes,
                self.x_clock,
                self.y_clock,
                1,
                config.COLOR_CLOCK,
                1.0,
                True,
            )

    def render_reset_confirm(self, now):
        self._set_font(self._small_font)
        self._clear()
        self._border(config.COLOR_RESET)
        label = RESET_LABEL
        if self.g.measure_text(label, self.scale) > self.w:
            label = RESET_LABEL_SHORT
        y = self._y_centered(self.scale)
        self._draw_label(label, self.w // 2, y, config.COLOR_RESET, self.scale, now)

    def _draw_big_digits(self, text, x, y, font, pen):
        self._set_font(font)
        self.g.set_pen(pen)
        return self._draw_digits(text, x, y, BIG_DIGIT_PITCH * self.scale, self.scale)

    def render_clock(self, hms, digit_color, background):
        self._clear(background)
        hours, minutes = self._clock_digits(hms) if hms else ("--", "--")
        hour_pen = self._pen(digit_color)
        minute_pen = self._pen(digit_color, config.CLOCK_MINUTE_BRIGHTNESS)
        s = self.scale
        if self.horizontal:
            width = BIG_DIGIT_PITCH * s * 4 - s
            x = (self.w - width) // 2
            y = (self.h - BIG_GLYPH_H * s) // 2
            x = self._draw_big_digits(hours, x, y, self._hour_font, hour_pen)
            self._draw_big_digits(minutes, x, y, self._minute_font, minute_pen)
            if hms is None or hms[2] % 2 == 0:
                colon_pen = self._pen(digit_color, config.CLOCK_COLON_BRIGHTNESS)
                self._draw_colon(x - s, y, BIG_GLYPH_H, s, colon_pen)
        else:
            self._draw_big_digits(hours, s, 0, self._hour_font, hour_pen)
            self._draw_big_digits(
                minutes,
                self.w - 2 * BIG_DIGIT_PITCH * s,
                self.h - BIG_GLYPH_H * s,
                self._minute_font,
                minute_pen,
            )
