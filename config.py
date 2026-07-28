# All tunables for the Unicorn Pomodoro app live here.

# Which board to build for: "stellar" (16x16), "galactic" (53x11) or "cosmic" (32x32).
BOARD = "stellar"

# --- Pomodoro timings ---------------------------------------------------
WORK_MINUTES = 25
SHORT_BREAK_MINUTES = 5
LONG_BREAK_MINUTES = 25
SESSIONS_PER_CYCLE = 4

# Shrink every phase to seconds so a full cycle can be watched end-to-end.
TEST_MODE = False

if TEST_MODE:
    WORK_S = 15
    SHORT_BREAK_S = 5
    LONG_BREAK_S = 10
else:
    WORK_S = WORK_MINUTES * 60
    SHORT_BREAK_S = SHORT_BREAK_MINUTES * 60
    LONG_BREAK_S = LONG_BREAK_MINUTES * 60

RESET_CONFIRM_TIMEOUT_S = 5

COLOR_READY = (0, 255, 0)
COLOR_WORK = (255, 99, 71)
COLOR_BREAK = (255, 210, 0)
COLOR_LONG_BREAK = (255, 170, 0)
COLOR_CLOCK = (170, 170, 170)
COLOR_CLOCK_BIG = (255, 255, 255)
COLOR_RESET = (255, 40, 40)
COLOR_DOT_DONE = (255, 99, 71)
COLOR_DOT_PENDING = (40, 40, 40)
CLOCK_COLON_BRIGHTNESS = 0.45

# The tomato that bursts when a work session ends.
TOMATO_RED = (255, 60, 40)
STEM_GREEN = (30, 150, 40)

TICK_ENABLED = False  # quiet tick every second during a work session
BEEP_ENABLED = True  # beeps when a session/break ends
DEFAULT_VOLUME = 0.5  # 0.0-1.0, also adjustable with the volume buttons

TICK_FREQ = 2093  # Hz
TICK_MS = 25
TICK_VOLUME = 0.08  # relative to channel max, keep it subtle
BEEP_VOLUME = 0.4
WORK_DONE_MELODY = ((1175, 120), (988, 120), (784, 250))  # descending: wind down
BREAK_DONE_MELODY = ((784, 120), (988, 120), (1175, 250))  # ascending: back at it

UTC_OFFSET_HOURS = 0  # CET; DST on top of this if AUTO_DST_EU
AUTO_DST_EU = False  # EU rule: last Sunday of March -> last Sunday of October
WIFI_TIMEOUT_S = 10
NTP_RESYNC_HOURS = 6
CLOCK_24H = True

# Clock mode: colored digits on black, recolored each hour by a full-screen
# flash that settles on the new color and then inverts back into the digits;
# False = plain white-on-black.
CLOCK_HOURLY_FLASH = True
CLOCK_BG_VALUE = 0.6  # HSV value of the flash background colors
CLOCK_DIGIT_VALUE = 1.0  # HSV value of the settled digit color
CLOCK_MINUTE_BRIGHTNESS = 0.7  # minutes vs hours; hours read as the bold line
CLOCK_FLASH_S = 1.2  # random-color flash at the top of the hour
CLOCK_SETTLE_S = 2.0  # smooth fade into the new hour's color
CLOCK_INVERT_S = 1.0  # background fades out while the digits take the color

DEFAULT_BRIGHTNESS = 0.5
FPS = 100
SCROLL_MS = 150  # ms per pixel when scrolling text that does not fit
PULSE_PERIOD_MS = 1200  # breathing rate of the "press A" hint
PULSE_MIN_BRIGHTNESS = 0.25
PULSE_MAX_BRIGHTNESS = 1.0

_LAYOUT = {
    "stellar": {"rings": 1, "scale": 1, "horizontal": False},
    "galactic": {"rings": 1, "scale": 1, "horizontal": True},
    "cosmic": {"rings": 3, "scale": 2, "horizontal": False},
}
LAYOUT = _LAYOUT[BOARD]

RING_FADE = (1.0, 0.55, 0.25)
