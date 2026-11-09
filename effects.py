import math
import random
from array import array

import config
from compat import micropython, ticks_diff

BLACK = (0, 0, 0)


def _hsv_to_rgb(hue, saturation, value):
    sector_pos = (hue % 1.0) * 6.0
    sector = int(sector_pos)
    f = sector_pos - sector
    p = value * (1.0 - saturation)
    q = value * (1.0 - saturation * f)
    t = value * (1.0 - saturation * (1.0 - f))
    if sector == 0:
        r, g, b = value, t, p
    elif sector == 1:
        r, g, b = q, value, p
    elif sector == 2:
        r, g, b = p, value, t
    elif sector == 3:
        r, g, b = p, q, value
    elif sector == 4:
        r, g, b = t, value, q
    else:
        r, g, b = value, p, q
    return int(r * 255), int(g * 255), int(b * 255)


def _smoothstep(u):
    return u * u * (3.0 - 2.0 * u)


def _ease_out_back(u):
    overshoot = 1.70158
    u -= 1.0
    return 1.0 + (overshoot + 1.0) * u * u * u + overshoot * u * u


def _blend_linear_light(start, end, amount):
    keep = 1.0 - amount
    return (
        int(math.sqrt(start[0] * start[0] * keep + end[0] * end[0] * amount)),
        int(math.sqrt(start[1] * start[1] * keep + end[1] * end[1] * amount)),
        int(math.sqrt(start[2] * start[2] * keep + end[2] * end[2] * amount)),
    )


def _whitened(color, amount):
    return (
        color[0] + (255 - color[0]) * amount,
        color[1] + (255 - color[1]) * amount,
        color[2] + (255 - color[2]) * amount,
    )


class _Effect:
    DURATION_S = 0.0

    def __init__(self, graphics, width, height):
        self.g = graphics
        self.w = width
        self.h = height
        self._black = graphics.create_pen(0, 0, 0)
        self._start = 0

    def _on_start(self):
        pass

    def start(self, now):
        self._start = now
        self._on_start()

    def done(self, now):
        return ticks_diff(now, self._start) >= self.DURATION_S * 1000

    def _elapsed_s(self, now):
        return ticks_diff(now, self._start) / 1000

    def _clear(self):
        self.g.set_pen(self._black)
        self.g.clear()

    @micropython.native
    def _plot(self, x, y, red, green, blue, brightness):
        if x < 0 or x >= self.w or y < 0 or y >= self.h:
            return
        if brightness > 1.0:
            brightness = 1.0
        self.g.set_pen(
            self.g.create_pen(
                int(red * brightness), int(green * brightness), int(blue * brightness)
            )
        )
        self.g.pixel(x, y)


class _Field(_Effect):
    def __init__(self, graphics, width, height, aspect):
        super().__init__(graphics, width, height)
        self.cx = (width - 1) / 2
        self.cy = (height - 1) / 2
        self._aspect = aspect
        self._center_dist = array("f", (0.0 for _ in range(width * height)))
        i = 0
        for y in range(height):
            for x in range(width):
                dy = (y - self.cy) * aspect
                self._center_dist[i] = math.sqrt((x - self.cx) ** 2 + dy * dy)
                i += 1

    @micropython.native
    def _disc(self, radius, color, brightness):
        red, green, blue = color
        center_dist = self._center_dist
        radius_y = radius / self._aspect
        x0 = max(int(self.cx - radius) - 1, 0)
        x1 = min(int(self.cx + radius) + 2, self.w)
        y0 = max(int(self.cy - radius_y) - 1, 0)
        y1 = min(int(self.cy + radius_y) + 2, self.h)
        for y in range(y0, y1):
            row = y * self.w
            for x in range(x0, x1):
                coverage = radius - center_dist[row + x] + 0.5
                if coverage <= 0.0:
                    continue
                if coverage > 1.0:
                    coverage = 1.0
                level = coverage * brightness
                self._plot(x, y, red, green, blue, level * level)

    @micropython.native
    def _ring(self, radius, color, brightness):
        red, green, blue = color
        center_dist = self._center_dist
        i = 0
        for y in range(self.h):
            for x in range(self.w):
                coverage = 1.0 - abs(center_dist[i] - radius)
                i += 1
                if coverage <= 0.0:
                    continue
                level = coverage * brightness
                self._plot(x, y, red, green, blue, level * level)


class Burst(_Field):
    GROW_S = 0.6
    POP_S = 0.8
    DURATION_S = 1.8

    _ASPECT = 1.3
    _RADIUS_FRACTION = 0.34
    _POP_WHITEN = 0.8
    _FLASH_END = 0.08
    _SHOCKWAVE_END = 0.5
    _SHOCKWAVE_SPEED = 1.5
    _PARTICLE_COUNT = 24
    _PARTICLE_SPAWN_RADIUS = 0.7
    _PARTICLE_MIN_SPEED = 5.0
    _PARTICLE_SPEED_RANGE = 7.0
    _PARTICLE_LIFT = 3.0
    _GRAVITY = 10.0

    def __init__(self, graphics, width, height, body_color, stem_color):
        super().__init__(graphics, width, height, self._ASPECT)
        self.radius = min(width, height) * self._RADIUS_FRACTION
        self.body_color = body_color
        self.stem_color = stem_color
        # Flat [x, y, vx, vy] per particle so draw() never allocates.
        self._particles = array("f", (0.0 for _ in range(self._PARTICLE_COUNT * 4)))

    def _on_start(self):
        for i in range(self._PARTICLE_COUNT):
            angle = (i + random.random()) * 2 * math.pi / self._PARTICLE_COUNT
            speed = (
                self._PARTICLE_MIN_SPEED + random.random() * self._PARTICLE_SPEED_RANGE
            )
            p = i * 4
            self._particles[p] = (
                self.cx + math.cos(angle) * self.radius * self._PARTICLE_SPAWN_RADIUS
            )
            self._particles[p + 1] = (
                self.cy
                + math.sin(angle)
                * self.radius
                * self._PARTICLE_SPAWN_RADIUS
                / self._ASPECT
            )
            self._particles[p + 2] = math.cos(angle) * speed
            self._particles[p + 3] = math.sin(angle) * speed - self._PARTICLE_LIFT

    @micropython.native
    def _draw_stem(self, radius, brightness):
        if radius < 2.0:
            return
        red, green, blue = self.stem_color
        level = brightness * brightness
        x = int(self.cx)
        y = int(self.cy - radius / self._aspect + 0.5)
        self._plot(x, y - 1, red, green, blue, level)
        self._plot(x - 1, y, red, green, blue, level * 0.6)
        self._plot(x + 1, y, red, green, blue, level * 0.6)

    @micropython.native
    def _plot_antialiased(self, fx, fy, color, brightness):
        red, green, blue = color
        x = math.floor(fx)
        y = math.floor(fy)
        ax = fx - x
        ay = fy - y
        level = brightness * brightness
        self._plot(x, y, red, green, blue, level * (1 - ax) * (1 - ay))
        self._plot(x + 1, y, red, green, blue, level * ax * (1 - ay))
        self._plot(x, y + 1, red, green, blue, level * (1 - ax) * ay)
        self._plot(x + 1, y + 1, red, green, blue, level * ax * ay)

    @micropython.native
    def draw(self, now):
        elapsed_s = self._elapsed_s(now)
        self._clear()
        if elapsed_s < self.GROW_S:
            radius = self.radius * _ease_out_back(elapsed_s / self.GROW_S)
            self._disc(radius, self.body_color, 1.0)
            self._draw_stem(radius, 1.0)
        elif elapsed_s < self.POP_S:
            progress = (elapsed_s - self.GROW_S) / (self.POP_S - self.GROW_S)
            self._disc(
                self.radius,
                _whitened(self.body_color, progress * self._POP_WHITEN),
                1.0,
            )
            self._draw_stem(self.radius, 1.0 - progress)
        else:
            since_pop_s = elapsed_s - self.POP_S
            progress = since_pop_s / (self.DURATION_S - self.POP_S)
            if progress < self._FLASH_END:
                flash_r = self.radius * (1.0 - progress / self._FLASH_END)
                self._disc(flash_r, (255, 255, 255), 1.0)
            if progress < self._SHOCKWAVE_END:
                self._ring(
                    self.radius + progress * self.w * self._SHOCKWAVE_SPEED,
                    self.body_color,
                    1.0 - progress / self._SHOCKWAVE_END,
                )
            fall = 0.5 * self._GRAVITY * since_pop_s * since_pop_s
            particles = self._particles
            for i in range(self._PARTICLE_COUNT):
                p = i * 4
                self._plot_antialiased(
                    particles[p] + particles[p + 2] * since_pop_s,
                    particles[p + 1] + particles[p + 3] * since_pop_s + fall,
                    self.body_color,
                    1.0 - progress,
                )


class Rings(_Field):
    COUNT = 3
    STAGGER_S = 0.24
    SWEEP_S = 0.65
    PULSE_S = 1.05
    DURATION_S = 1.5

    _FADE_IN_SPEED = 5.0
    _PULSE_WHITEN = 0.7

    def __init__(self, graphics, width, height, color):
        super().__init__(graphics, width, height, 1.0)
        self.color = color
        self._start_radius = math.sqrt(self.cx * self.cx + self.cy * self.cy) + 1.0

    @micropython.native
    def draw(self, now):
        elapsed_s = self._elapsed_s(now)
        self._clear()
        for i in range(self.COUNT):
            progress = (elapsed_s - i * self.STAGGER_S) / self.SWEEP_S
            if progress <= 0.0 or progress >= 1.0:
                continue
            brightness = progress * self._FADE_IN_SPEED
            if brightness > 1.0:
                brightness = 1.0
            radius = self._start_radius * (1.0 - progress * progress)
            self._ring(radius, self.color, brightness)
        if elapsed_s >= self.PULSE_S:
            progress = (elapsed_s - self.PULSE_S) / (self.DURATION_S - self.PULSE_S)
            whiten = (
                self._PULSE_WHITEN * (1.0 - progress * 2.0) if progress < 0.5 else 0.0
            )
            color = _whitened(self.color, whiten)
            self._disc(2.5 + progress * 1.5, color, 1.0 - progress)


class HourFlash:
    _FLASH_COLOR_COUNT = 3
    _MIN_HUE_DISTANCE = 0.15

    def __init__(self):
        self._hue = random.random()
        self._digit_color = _hsv_to_rgb(self._hue, 1.0, config.CLOCK_DIGIT_VALUE)
        self._prev_digit_color = self._digit_color
        self._last_period = None
        self._transition_start = None
        self._flash_colors = None
        self._settled_background = None

    def _pick_distant_hue(self):
        while True:
            hue = random.random()
            distance = abs(hue - self._hue)
            if min(distance, 1.0 - distance) >= self._MIN_HUE_DISTANCE:
                return hue

    def _begin_transition(self, now):
        background_value = config.CLOCK_BG_VALUE
        self._hue = self._pick_distant_hue()
        self._settled_background = _hsv_to_rgb(self._hue, 1.0, background_value)
        self._prev_digit_color = self._digit_color
        self._digit_color = _hsv_to_rgb(self._hue, 1.0, config.CLOCK_DIGIT_VALUE)
        self._flash_colors = [BLACK] + [
            _hsv_to_rgb(random.random(), 1.0, background_value)
            for _ in range(self._FLASH_COLOR_COUNT)
        ]
        self._transition_start = now

    def _track_period(self, now, hms):
        period = hms[1] if config.TEST_MODE else hms[0]
        if self._last_period is not None and period != self._last_period:
            self._begin_transition(now)
        self._last_period = period

    def update(self, now, hms):
        if hms is not None:
            self._track_period(now, hms)
        if self._transition_start is None:
            return self._digit_color, BLACK
        elapsed_s = ticks_diff(now, self._transition_start) / 1000
        if elapsed_s < config.CLOCK_FLASH_S:
            position = elapsed_s / config.CLOCK_FLASH_S * (len(self._flash_colors) - 1)
            i = int(position)
            background = _blend_linear_light(
                self._flash_colors[i],
                self._flash_colors[i + 1],
                _smoothstep(position - i),
            )
            if i:
                digits = BLACK
            else:
                digits = _blend_linear_light(
                    self._prev_digit_color, BLACK, _smoothstep(position)
                )
            return digits, background
        elapsed_s -= config.CLOCK_FLASH_S
        if elapsed_s < config.CLOCK_SETTLE_S:
            progress = _smoothstep(elapsed_s / config.CLOCK_SETTLE_S)
            background = _blend_linear_light(
                self._flash_colors[-1], self._settled_background, progress
            )
            return BLACK, background
        elapsed_s -= config.CLOCK_SETTLE_S
        if elapsed_s < config.CLOCK_INVERT_S:
            progress = _smoothstep(elapsed_s / config.CLOCK_INVERT_S)
            return (
                _blend_linear_light(BLACK, self._digit_color, progress),
                _blend_linear_light(self._settled_background, BLACK, progress),
            )
        self._transition_start = None
        self._flash_colors = None
        return self._digit_color, BLACK
