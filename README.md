# Unicorn Pomodoro

A [Pomodoro](https://en.wikipedia.org/wiki/Pomodoro_Technique) timer for the
[Pimoroni Stellar Unicorn](https://shop.pimoroni.com/products/space-unicorns)
(16x16 LED matrix, Raspberry Pi Pico W), written in MicroPython. A spiritual
sibling of [garmodoro](https://github.com/klimeryk/garmodoro) for Garmin
watches.

The code is board-agnostic: change one constant in `config.py` to build for
the Galactic Unicorn (53x11) or Cosmic Unicorn (32x32) instead.

## How it works

- **Ready** (green border): the pixels next to the **A** button pulse.
  Press **A** to start a 25-minute session.
- **Session** (tomato border): `MM:SS` countdown, a quiet tick every second,
  progress dots show your place in the cycle of 4.
- **Break** (yellow border): 5 minutes after each session, 25 minutes after
  the 4th — then everything starts over.
- The current time is shown at the bottom of every screen (needs WiFi, see
  below).
- **B** asks `Reset?` — press **B** again to reset to the first session,
  any other button (or 5 s) cancels.
- **D** switches to a clock-only mode and resets the Pomodoro; **A** goes
  back. Big hours sit top-left, dimmer minutes bottom-right, colored on a
  black background. At the top of every hour the background flashes through
  random colors, settles on a new one, then fades back to black leaving the
  digits in the new color (set `CLOCK_HOURLY_FLASH = False` in `config.py`
  for a plain white-on-black clock).
- **LUX +/-** adjusts brightness, **VOL +/-** adjusts the sound volume.

## Setup

1. **Flash the Pimoroni firmware.** Grab the latest release from
   [pimoroni/unicorn releases](https://github.com/pimoroni/unicorn/releases)
   and pick the build matching your board **and** your Pico: for a Stellar
   Unicorn with the original **Pico W**, that's the `stellar` + `pico_w`
   variant — *not* `pico2_w` (that one is for the newer Pico 2 W). Hold
   BOOTSEL while plugging in USB, then copy the `.uf2` onto the `RPI-RP2`
   drive.

2. **WiFi credentials** (optional, needed only for the clock):

   ```sh
   cp secrets.py.example secrets.py   # then edit it
   ```

   Set your timezone in `config.py` (`UTC_OFFSET_HOURS`; EU daylight saving
   is applied automatically while `AUTO_DST_EU = True`).

3. **Copy the app to the board** (with [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html),
   `pip install mpremote`; Thonny works too):

   ```sh
   mpremote cp main.py config.py board.py pomodoro.py ui.py effects.py sound.py net_time.py secrets.py 3x5.bitmapfont MatrixChunky8x6.bitmapfont MatrixLight8x6.bitmapfont :
   mpremote reset
   ```

   Being `main.py`, it starts automatically on power-up.

## Configuration

Everything lives in `config.py`: durations, colors, sounds (set
`TICK_ENABLED`/`BEEP_ENABLED` to `False` to silence), brightness, timezone.
Set `TEST_MODE = True` to shrink all phases to seconds and watch a full
cycle end-to-end.

## Other Unicorn boards

Set `BOARD = "galactic"` or `BOARD = "cosmic"` in `config.py` and flash the
matching firmware. All layout is derived from the board's dimensions plus
the small per-board table (`_LAYOUT`) in `config.py` — border rings, text
scale and stacked vs side-by-side arrangement.

## Development

The state machine (`pomodoro.py`) is hardware-free and tested on the host:

```sh
python3 tests/test_pomodoro.py
```

Linting and formatting use [ruff](https://docs.astral.sh/ruff/)
(`brew install ruff`), configured in `pyproject.toml`:

```sh
ruff check .    # lint (add --fix to auto-fix)
ruff format .   # format
```

The main display font is [Tom Thumb](https://opengameart.org/content/tom-thumb-tiny-ascii-font-3x5)
by Brian Swetland and Robey Pointer (CC0/CC-BY 3.0), checked in as the
`tom-thumb-new.png` sprite sheet. Clock mode uses trip5's
[Matrix-Fonts](https://github.com/trip5/Matrix-Fonts) (CC-BY): the bold
`MatrixChunky8x6` for the hours and the thin `MatrixLight8x6` for the minutes.
The `.bitmapfont` files are generated with
[pgfutil](https://github.com/Gadgetoid/pgfutil):

```sh
pip install pgfutil pillow
python3 tools/build_font.py           # 3x5.bitmapfont
python3 tools/build_matrix_fonts.py   # MatrixChunky8x6 + MatrixLight8x6 (auto-fetches the BDFs)
python3 tests/test_font.py            # sanity-check the results
```
