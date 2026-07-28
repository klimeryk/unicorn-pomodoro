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
import net_time
from pomodoro import READY, WORK, WORK_DONE, Pomodoro
from sound import Sound
from ui import UI

MODE_POMODORO = "pomodoro"
MODE_CLOCK = "clock"


class Button:
    def __init__(self, su, switch):
        self._su = su
        self._switch = switch
        self._down = False

    def pressed(self):
        down = self._su.is_pressed(self._switch)
        fired = down and not self._down
        self._down = down
        return fired


su = board.Unicorn()
graphics = PicoGraphics(display=board.DISPLAY)
with open("3x5.bitmapfont", "rb") as f:
    font = f.read()
with open("MatrixChunky8x6.bitmapfont", "rb") as f:
    clock_hour_font = f.read()
with open("MatrixLight8x6.bitmapfont", "rb") as f:
    clock_minute_font = f.read()
su.set_brightness(config.DEFAULT_BRIGHTNESS)

ui = UI(
    graphics,
    board.WIDTH,
    board.HEIGHT,
    board.BUTTON_A_ZONE,
    font,
    clock_hour_font,
    clock_minute_font,
)
sound = Sound(su, board.Channel)
fx_burst = effects.Burst(
    graphics, board.WIDTH, board.HEIGHT, config.TOMATO_RED, config.STEM_GREEN
)
fx_ready = effects.Rings(graphics, board.WIDTH, board.HEIGHT, config.COLOR_READY)
hour_flash = effects.HourFlash() if config.CLOCK_HOURLY_FLASH else None
pomo = Pomodoro(
    config.WORK_S, config.SHORT_BREAK_S, config.LONG_BREAK_S, config.SESSIONS_PER_CYCLE
)

ui.render_boot()
su.update(graphics)
net_time.sync()
last_ntp_sync = time.ticks_ms()
sync_retry_delay = config.WIFI_RETRY_START_S
next_sync_retry = time.ticks_add(last_ntp_sync, sync_retry_delay * 1000)

btn_a = Button(su, board.Unicorn.SWITCH_A)
btn_b = Button(su, board.Unicorn.SWITCH_B)
btn_c = Button(su, board.Unicorn.SWITCH_C)
btn_d = Button(su, board.Unicorn.SWITCH_D)

mode = MODE_POMODORO
reset_prompt_until = None
effect = None
last_ticked_second = None

gc.collect()
last_gc = time.ticks_ms()

while True:
    now = time.ticks_ms()
    if time.ticks_diff(now, last_gc) >= 1000:
        gc.collect()
        last_gc = now
    a, b, c, d = btn_a.pressed(), btn_b.pressed(), btn_c.pressed(), btn_d.pressed()

    if reset_prompt_until is not None:
        if b:
            pomo.reset()
            effect = None
            reset_prompt_until = None
        elif a or c or d or time.ticks_diff(reset_prompt_until, now) <= 0:
            reset_prompt_until = None
    elif mode == MODE_CLOCK:
        if a:
            mode = MODE_POMODORO
    else:
        if a and pomo.state == READY:
            pomo.start(now)
        if b:
            reset_prompt_until = time.ticks_add(
                now, config.RESET_CONFIRM_TIMEOUT_S * 1000
            )
        if d:
            pomo.reset()
            effect = None
            mode = MODE_CLOCK

    if su.is_pressed(board.Unicorn.SWITCH_BRIGHTNESS_UP):
        su.adjust_brightness(0.01)
    if su.is_pressed(board.Unicorn.SWITCH_BRIGHTNESS_DOWN):
        su.adjust_brightness(-0.01)
    if su.is_pressed(board.Unicorn.SWITCH_VOLUME_UP):
        su.adjust_volume(0.01)
    if su.is_pressed(board.Unicorn.SWITCH_VOLUME_DOWN):
        su.adjust_volume(-0.01)

    event = pomo.poll(now)
    if event is not None:
        melody = (
            config.WORK_DONE_MELODY if event == WORK_DONE else config.BREAK_DONE_MELODY
        )
        sound.play(melody, now)
        effect = fx_burst if event == WORK_DONE else fx_ready
        effect.start(now)
        if event == WORK_DONE:
            pomo.postpone(int(fx_burst.DURATION_S * 1000))

    secs = pomo.remaining_seconds(now)
    if pomo.state == WORK and secs != last_ticked_second:
        last_ticked_second = secs
        sound.tick(now)
    sound.update(now)

    if (
        net_time.synced
        and (mode == MODE_CLOCK or pomo.state == READY)
        and time.ticks_diff(now, last_ntp_sync) > config.NTP_RESYNC_HOURS * 3600 * 1000
    ):
        net_time.resync()
        last_ntp_sync = now
    elif not net_time.synced and time.ticks_diff(now, next_sync_retry) >= 0:
        net_time.sync()
        last_ntp_sync = now
        sync_retry_delay = min(sync_retry_delay * 2, config.WIFI_RETRY_MAX_S)
        next_sync_retry = time.ticks_add(now, sync_retry_delay * 1000)

    if effect is not None and effect.done(now):
        effect = None

    hms = net_time.local_hms()
    if hour_flash is not None:
        clock_fg, clock_bg = hour_flash.update(now, hms)
    else:
        clock_fg = clock_bg = None

    if reset_prompt_until is not None:
        ui.render_reset_confirm(now)
    elif effect is not None:
        effect.draw(now)
    elif mode == MODE_CLOCK:
        ui.render_clock(hms, clock_fg, clock_bg)
    else:
        ui.render_pomodoro(
            now,
            pomo.state,
            secs,
            pomo.remaining_fraction(now),
            pomo.completed,
            hms,
        )
    su.update(graphics)
    if effect is None:
        time.sleep_ms(1000 // config.FPS)
