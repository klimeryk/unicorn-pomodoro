import math

import config
from pomodoro import LONG_BREAK, READY, SHORT_BREAK, WORK

GLYPH_H = 5
DIGIT_PITCH = 4
BIG_GLYPH_H = 7
BIG_DIGIT_PITCH = 6
_PULSE_LEVELS = 32
_BAR_LEVELS = 16

STATE_COLORS = {
    READY: config.COLOR_READY,
    WORK: config.COLOR_WORK,
    SHORT_BREAK: config.COLOR_BREAK,
    LONG_BREAK: config.COLOR_LONG_BREAK,
}


def _pad_time(n):
    # str.rjust isn't in Pimoroni's MicroPython; values are always 1-2 digits.
    s = str(n)
    return config.TIME_PAD_CHAR + s if len(s) < 2 else s


class UI:
    def __init__(
        self,
        graphics,
        width,
        height,
        a_zone,
        font=None,
        clock_hour_font=None,
        clock_minute_font=None,
    ):
        self.g = graphics
        self.w = width
        self.h = height
        self.a_zone = a_zone
        self.rings = min(config.LAYOUT["rings"], len(config.RING_FADE))
        self.scale = config.LAYOUT["scale"]
        self._pens = {}
        self._black = self._pen((0, 0, 0))
        self._font = font
        self._hour_font = clock_hour_font
        self._minute_font = clock_minute_font
        self._font_active = None
        self._set_font(font)

        if config.LAYOUT["horizontal"]:
            self.x_main = width * 3 // 10
            self.y_main = self._y_center(self.scale)
            self.x_clock = width * 3 // 4
            self.y_clock = self._y_center(1)
            self.x_dots = width // 2
            self.y_dots = height - 3
            self.y_bar = height - 1
        else:
            self.x_main = width // 2
            self.y_main = 1
            self.x_clock = width // 2
            self.y_clock = height - GLYPH_H
            self.y_bar = self.y_clock - 1 - self.scale
            self.x_dots = width // 2
            self.y_dots = (self.y_main + GLYPH_H * self.scale + self.y_bar) // 2

    def _y_center(self, scale):
        return (self.h - GLYPH_H * scale) // 2

    def _set_font(self, font):
        if font is not self._font_active:
            self.g.set_font(font)
            self._font_active = font

    def _pen(self, color, brightness=1.0):
        key = (
            int(color[0] * brightness),
            int(color[1] * brightness),
            int(color[2] * brightness),
        )
        pen = self._pens.get(key)
        if pen is None:
            pen = self.g.create_pen(key[0], key[1], key[2])
            self._pens[key] = pen
        return pen

    def _clear(self):
        self.g.set_pen(self._black)
        self.g.clear()

    def _border(self, color):
        for i in range(self.rings):
            self.g.set_pen(self._pen(color, config.RING_FADE[i]))
            w = self.w - 2 * i
            h = self.h - 2 * i
            self.g.rectangle(i, i, w, 1)
            self.g.rectangle(i, self.h - 1 - i, w, 1)
            self.g.rectangle(i, i + 1, 1, h - 2)
            self.g.rectangle(self.w - 1 - i, i + 1, 1, h - 2)

    def _pulse(self, now):
        lo = config.PULSE_MIN_BRIGHTNESS
        half = (config.PULSE_MAX_BRIGHTNESS - lo) / 2
        b = lo + half * (math.sin(now * 2 * math.pi / config.PULSE_PERIOD_MS) + 1)
        return round(b * _PULSE_LEVELS) / _PULSE_LEVELS

    def _draw_time(
        self,
        left,
        right,
        x_center,
        y,
        color,
        colon_on,
        scale,
        colon_brightness=1.0,
        right_brightness=1.0,
        colon_color=None,
    ):
        s = scale
        total = DIGIT_PITCH * s * (len(left) + len(right)) - s
        x = x_center - (total + 1) // 2
        if x < 0:
            x = 0
        self.g.set_pen(self._pen(color))
        for ch in left:
            self.g.text(ch, x, y, -1, s)
            x += DIGIT_PITCH * s
        colon_x = x - s
        self.g.set_pen(self._pen(color, right_brightness))
        for ch in right:
            self.g.text(ch, x, y, -1, s)
            x += DIGIT_PITCH * s
        if colon_on:
            pen_color = colon_color if colon_color is not None else color
            self.g.set_pen(self._pen(pen_color, colon_brightness))
            self.g.rectangle(colon_x, y + s, s, s)
            self.g.rectangle(colon_x, y + 3 * s, s, s)

    def _draw_label(self, text, x_center, y, color, scale, now):
        w = self.g.measure_text(text, scale)
        self.g.set_pen(self._pen(color))
        if w <= self.w:
            self.g.text(text, x_center - w // 2, y, -1, scale)
        else:
            offset = (now // config.SCROLL_MS) % (w + self.w)
            self.g.text(text, self.w - offset, y, -1, scale)

    def _draw_a_hint(self, now):
        self.g.set_pen(self._pen((255, 255, 255), self._pulse(now)))
        for x, y in self.a_zone:
            self.g.pixel(x, y)

    def _draw_dots(self, completed, working, now):
        total = config.SESSIONS_PER_CYCLE
        s = self.scale
        x = self.x_dots - ((2 * total - 1) * s) // 2
        for i in range(total):
            if i < completed:
                pen = self._pen(config.COLOR_DOT_DONE)
            elif i == completed and working:
                pen = self._pen(config.COLOR_DOT_DONE, self._pulse(now))
            else:
                pen = self._pen(config.COLOR_DOT_PENDING)
            self.g.set_pen(pen)
            self.g.rectangle(x, self.y_dots, s, s)
            x += 2 * s

    def _draw_bar(self, fraction, color):
        lit = fraction * self.w
        full = int(lit)
        if full:
            self.g.set_pen(self._pen(color))
            self.g.rectangle(0, self.y_bar, full, self.scale)
        if full < self.w:
            tip = round((lit - full) * _BAR_LEVELS) / _BAR_LEVELS
            if tip:
                self.g.set_pen(self._pen(color, tip))
                self.g.rectangle(full, self.y_bar, 1, self.scale)

    def _hhmm(self, hms):
        h = hms[0]
        if not config.CLOCK_24H:
            h = ((h + 11) % 12) + 1
        return _pad_time(h), f"{hms[1]:02d}"

    def render_boot(self):
        self._set_font(self._font)
        self._clear()
        self._draw_label(
            ".....", self.w // 2, self._y_center(1), config.COLOR_CLOCK, 1, 0
        )

    def render_pomodoro(self, now, state, secs, frac, completed, hms):
        self._set_font(self._font)
        self._clear()
        color = STATE_COLORS[state]
        if state == READY:
            self._draw_label("Ready", self.x_main, self.y_main, color, self.scale, now)
            self._draw_a_hint(now)
        else:
            self._draw_time(
                _pad_time(secs // 60),
                f"{secs % 60:02d}",
                self.x_main,
                self.y_main,
                color,
                secs % 2 == 0,
                self.scale,
                config.CLOCK_COLON_BRIGHTNESS,
                config.POMODORO_SECONDS_BRIGHTNESS,
                config.COLOR_CLOCK,
            )
            self._draw_bar(frac, color)
        self._draw_dots(completed, state == WORK, now)
        if hms:
            left, right = self._hhmm(hms)
            self._draw_time(
                left,
                right,
                self.x_clock,
                self.y_clock,
                config.COLOR_CLOCK,
                True,
                1,
                config.CLOCK_COLON_BRIGHTNESS,
            )

    def render_reset_confirm(self, now):
        self._set_font(self._font)
        self._clear()
        self._border(config.COLOR_RESET)
        label = "Reset?"
        if self.g.measure_text(label, self.scale) > self.w:
            label = "RST?"
        y = self._y_center(self.scale)
        self._draw_label(label, self.w // 2, y, config.COLOR_RESET, self.scale, now)

    def _draw_big(self, text, x, y, pen, font):
        self._set_font(font)
        self.g.set_pen(pen)
        for ch in text:
            self.g.text(ch, x, y, -1, self.scale)
            x += BIG_DIGIT_PITCH * self.scale
        return x

    def render_clock(self, hms, fg=None, bg=None):
        if fg is None:
            fg = config.COLOR_CLOCK_BIG
        if bg is None:
            self._clear()
        else:
            self.g.set_pen(self.g.create_pen(bg[0], bg[1], bg[2]))
            self.g.clear()
        if hms:
            left, right = self._hhmm(hms)
        else:
            left = right = "--"
        dim = config.CLOCK_MINUTE_BRIGHTNESS
        hour_pen = self.g.create_pen(fg[0], fg[1], fg[2])
        minute_pen = self.g.create_pen(
            int(fg[0] * dim), int(fg[1] * dim), int(fg[2] * dim)
        )
        s = self.scale
        if config.LAYOUT["horizontal"]:
            total = BIG_DIGIT_PITCH * s * 4 - s
            x = (self.w - total) // 2
            y = (self.h - BIG_GLYPH_H * s) // 2
            x = self._draw_big(left, x, y, hour_pen, self._hour_font)
            self._draw_big(right, x, y, minute_pen, self._minute_font)
            if hms is None or hms[2] % 2 == 0:
                cb = config.CLOCK_COLON_BRIGHTNESS
                self.g.set_pen(
                    self.g.create_pen(int(fg[0] * cb), int(fg[1] * cb), int(fg[2] * cb))
                )
                self.g.rectangle(x - s, y + 2 * s, s, s)
                self.g.rectangle(x - s, y + 4 * s, s, s)
        else:
            self._draw_big(left, s, 0, hour_pen, self._hour_font)
            self._draw_big(
                right,
                self.w - (2 * BIG_DIGIT_PITCH) * s,
                self.h - BIG_GLYPH_H * s,
                minute_pen,
                self._minute_font,
            )
