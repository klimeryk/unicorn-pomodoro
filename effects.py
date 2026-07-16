import math
import random
from array import array

import config
from pomodoro import ticks_diff

try:
    import micropython
except ImportError:

    class micropython:
        @staticmethod
        def native(f):
            return f


_PARTICLES = 24
_GRAVITY = 10.0
_ASPECT = 1.3


def _hsv(h, s, v):
    h = (h % 1.0) * 6.0
    i = int(h)
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, v, q
    else:
        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)


def _smooth(u):
    return u * u * (3.0 - 2.0 * u)


def _blend(c1, c2, u):
    w = 1.0 - u
    return (
        int(math.sqrt(c1[0] * c1[0] * w + c2[0] * c2[0] * u)),
        int(math.sqrt(c1[1] * c1[1] * w + c2[1] * c2[1] * u)),
        int(math.sqrt(c1[2] * c1[2] * w + c2[2] * c2[2] * u)),
    )


def _ease_out_back(t):
    c1 = 1.70158
    t -= 1.0
    return 1.0 + (c1 + 1.0) * t * t * t + c1 * t * t


class _Effect:
    DURATION_S = 0.0

    def __init__(self, graphics, width, height):
        self.g = graphics
        self.w = width
        self.h = height
        self._black = graphics.create_pen(0, 0, 0)
        self._start = 0

    def _seed(self):
        pass

    def start(self, now):
        self._start = now
        self._seed()

    def done(self, now):
        return ticks_diff(now, self._start) >= self.DURATION_S * 1000

    def _elapsed_s(self, now):
        return ticks_diff(now, self._start) / 1000

    def _clear(self):
        self.g.set_pen(self._black)
        self.g.clear()

    @micropython.native
    def _px(self, x, y, cr, cg, cb, v):
        if v > 1.0:
            v = 1.0
        self.g.set_pen(self.g.create_pen(int(cr * v), int(cg * v), int(cb * v)))
        self.g.pixel(x, y)


class _Field(_Effect):
    def __init__(self, graphics, width, height, aspect):
        super().__init__(graphics, width, height)
        self.cx = (width - 1) / 2
        self.cy = (height - 1) / 2
        self._aspect = aspect
        self._dist = array("f", (0.0 for _ in range(width * height)))
        i = 0
        for y in range(height):
            for x in range(width):
                dy = (y - self.cy) * aspect
                self._dist[i] = math.sqrt((x - self.cx) ** 2 + dy * dy)
                i += 1

    @micropython.native
    def _disc(self, r, color, brightness):
        cr, cg, cb = color
        dist = self._dist
        ry = r / self._aspect
        x0 = max(int(self.cx - r) - 1, 0)
        x1 = min(int(self.cx + r) + 2, self.w)
        y0 = max(int(self.cy - ry) - 1, 0)
        y1 = min(int(self.cy + ry) + 2, self.h)
        for y in range(y0, y1):
            base = y * self.w
            for x in range(x0, x1):
                cov = r - dist[base + x] + 0.5
                if cov <= 0.0:
                    continue
                if cov > 1.0:
                    cov = 1.0
                v = cov * brightness
                self._px(x, y, cr, cg, cb, v * v)

    @micropython.native
    def _ring(self, r, color, brightness):
        cr, cg, cb = color
        dist = self._dist
        i = 0
        for y in range(self.h):
            for x in range(self.w):
                cov = 1.0 - abs(dist[i] - r)
                i += 1
                if cov <= 0.0:
                    continue
                v = cov * brightness
                self._px(x, y, cr, cg, cb, v * v)


class _Tomato(_Field):
    def __init__(self, graphics, width, height, body_color, stem_color):
        super().__init__(graphics, width, height, _ASPECT)
        self.r = min(width, height) * 0.34
        self.body = body_color
        self.stem = stem_color
        self._p = array("f", (0.0 for _ in range(_PARTICLES * 4)))

    @micropython.native
    def _draw_stem(self, r, brightness):
        if r < 2.0:
            return
        cr, cg, cb = self.stem
        v = brightness * brightness
        x = int(self.cx)
        y = int(self.cy - r / self._aspect + 0.5)
        if y > 0:
            self._px(x, y - 1, cr, cg, cb, v)
        if y >= 0:
            self._px(x - 1, y, cr, cg, cb, v * 0.6)
            self._px(x + 1, y, cr, cg, cb, v * 0.6)

    @micropython.native
    def _splat(self, fx, fy, color, brightness):
        cr, cg, cb = color
        x = math.floor(fx)
        y = math.floor(fy)
        ax = fx - x
        ay = fy - y
        b = brightness * brightness
        w = self.w
        h = self.h
        if 0 <= x < w and 0 <= y < h:
            self._px(x, y, cr, cg, cb, b * (1 - ax) * (1 - ay))
        if 0 <= x + 1 < w and 0 <= y < h:
            self._px(x + 1, y, cr, cg, cb, b * ax * (1 - ay))
        if 0 <= x < w and 0 <= y + 1 < h:
            self._px(x, y + 1, cr, cg, cb, b * (1 - ax) * ay)
        if 0 <= x + 1 < w and 0 <= y + 1 < h:
            self._px(x + 1, y + 1, cr, cg, cb, b * ax * ay)


class Burst(_Tomato):
    GROW_S = 0.6
    POP_S = 0.8
    DURATION_S = 1.8

    def _seed(self):
        for i in range(_PARTICLES):
            a = (i + random.random()) * 2 * math.pi / _PARTICLES
            speed = 5.0 + random.random() * 7.0
            j = i * 4
            self._p[j] = self.cx + math.cos(a) * self.r * 0.7
            self._p[j + 1] = self.cy + math.sin(a) * self.r * 0.7 / _ASPECT
            self._p[j + 2] = math.cos(a) * speed
            self._p[j + 3] = math.sin(a) * speed - 3.0

    @micropython.native
    def draw(self, now):
        t = self._elapsed_s(now)
        self._clear()
        if t < self.GROW_S:
            r = self.r * _ease_out_back(t / self.GROW_S)
            self._disc(r, self.body, 1.0)
            self._draw_stem(r, 1.0)
        elif t < self.POP_S:
            u = (t - self.GROW_S) / (self.POP_S - self.GROW_S)
            cr, cg, cb = self.body
            color = (
                cr + (255 - cr) * u * 0.8,
                cg + (255 - cg) * u * 0.8,
                cb + (255 - cb) * u * 0.8,
            )
            self._disc(self.r, color, 1.0)
            self._draw_stem(self.r, 1.0 - u)
        else:
            u = (t - self.POP_S) / (self.DURATION_S - self.POP_S)
            if u < 0.08:
                self._disc(self.r * (1.0 - u / 0.08), (255, 255, 255), 1.0)
            if u < 0.5:
                self._ring(self.r + u * self.w * 1.5, self.body, 1.0 - u * 2.0)
            dt = t - self.POP_S
            fall = 0.5 * _GRAVITY * dt * dt
            b = 1.0 - u
            for i in range(_PARTICLES):
                j = i * 4
                self._splat(
                    self._p[j] + self._p[j + 2] * dt,
                    self._p[j + 1] + self._p[j + 3] * dt + fall,
                    self.body,
                    b,
                )


class Rings(_Field):
    COUNT = 3
    STAGGER_S = 0.24
    SWEEP_S = 0.65
    PULSE_S = 1.05
    DURATION_S = 1.5

    def __init__(self, graphics, width, height, color):
        super().__init__(graphics, width, height, 1.0)
        self.color = color
        self._r0 = math.sqrt(self.cx * self.cx + self.cy * self.cy) + 1.0

    @micropython.native
    def draw(self, now):
        t = self._elapsed_s(now)
        self._clear()
        for i in range(self.COUNT):
            u = (t - i * self.STAGGER_S) / self.SWEEP_S
            if u <= 0.0 or u >= 1.0:
                continue
            b = u * 5.0
            if b > 1.0:
                b = 1.0
            self._ring(self._r0 * (1.0 - u * u), self.color, b)
        if t >= self.PULSE_S:
            u = (t - self.PULSE_S) / (self.DURATION_S - self.PULSE_S)
            cr, cg, cb = self.color
            wh = 0.7 * (1.0 - u * 2.0) if u < 0.5 else 0.0
            color = (
                cr + (255 - cr) * wh,
                cg + (255 - cg) * wh,
                cb + (255 - cb) * wh,
            )
            self._disc(2.5 + u * 1.5, color, 1.0 - u)


class HourFlash:
    _FLASH_COLORS = 3
    _MIN_HUE_DIST = 0.15
    _BLACK = (0, 0, 0)

    def __init__(self):
        self._hue = random.random()
        self._fg = _hsv(self._hue, 1.0, config.CLOCK_DIGIT_VALUE)
        self._prev_fg = self._fg
        self._last_key = None
        self._start = None
        self._seq = None
        self._target = None

    def _trigger(self, now):
        v = config.CLOCK_BG_VALUE
        while True:
            hue = random.random()
            d = abs(hue - self._hue)
            if min(d, 1.0 - d) >= self._MIN_HUE_DIST:
                break
        self._hue = hue
        self._target = _hsv(hue, 1.0, v)
        self._prev_fg = self._fg
        self._fg = _hsv(hue, 1.0, config.CLOCK_DIGIT_VALUE)
        self._seq = [self._BLACK] + [
            _hsv(random.random(), 1.0, v) for _ in range(self._FLASH_COLORS)
        ]
        self._start = now

    def update(self, now, hms):
        if hms is not None:
            key = hms[1] if config.TEST_MODE else hms[0]
            if self._last_key is None:
                self._last_key = key
            elif key != self._last_key:
                self._last_key = key
                self._trigger(now)
        if self._start is None:
            return self._fg, None
        t = ticks_diff(now, self._start) / 1000
        flash_s = config.CLOCK_FLASH_S
        if t < flash_s:
            pos = t / flash_s * (len(self._seq) - 1)
            i = int(pos)
            bg = _blend(self._seq[i], self._seq[i + 1], _smooth(pos - i))
            fg = self._BLACK if i else _blend(self._prev_fg, self._BLACK, _smooth(pos))
            return fg, bg
        t -= flash_s
        if t < config.CLOCK_SETTLE_S:
            u = _smooth(t / config.CLOCK_SETTLE_S)
            return self._BLACK, _blend(self._seq[-1], self._target, u)
        t -= config.CLOCK_SETTLE_S
        if t < config.CLOCK_INVERT_S:
            u = _smooth(t / config.CLOCK_INVERT_S)
            return (
                _blend(self._BLACK, self._fg, u),
                _blend(self._target, self._BLACK, u),
            )
        self._start = None
        self._seq = None
        return self._fg, None
