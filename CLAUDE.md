# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A MicroPython Pomodoro timer for the Pimoroni Stellar Unicorn: a 16x16 LED matrix driven by an **original Raspberry Pi Pico W (RP2040) — not a Pico 2 W** (Pimoroni ships separate firmware builds; always the `pico_w` variant). The code is portable to the Galactic (53x11) and Cosmic (32x32) Unicorns by changing `BOARD` in `config.py`. Behavior is modeled on the user's Garmin app, [garmodoro](https://github.com/klimeryk/garmodoro).

## Commands

```sh
# Host tests — plain asserts, no pytest; run each directly (no runner discovers them)
python3 tests/test_pomodoro.py   # state machine
python3 tests/test_ui_pens.py    # UI pen cache stays bounded
python3 tests/test_effects.py    # transition animations render in range
python3 tests/test_font.py       # every glyph the UI draws exists
ruff check .                     # lint — must stay clean; config in pyproject.toml
ruff format .                    # format
python3 tools/build_font.py      # regenerate 3x5.bitmapfont (needs: pip install pgfutil pillow)
mpremote cp main.py config.py board.py pomodoro.py ui.py effects.py sound.py net_time.py secrets.py 3x5.bitmapfont MatrixChunky8x6.bitmapfont MatrixLight8x6.bitmapfont : && mpremote reset
```

The Matrix 8x6 clock fonts (`MatrixChunky8x6.bitmapfont`, `MatrixLight8x6.bitmapfont`) are checked in; the repo currently ships **no** generator for them (only `tools/build_font.py`, for the 3x5 font).

Set `TEST_MODE = True` in `config.py` to shrink all phases to seconds for on-device testing of a full cycle.

## Architecture

The core split is host-runnable vs device-only:

- **Host-runnable**: `pomodoro.py` (pure state machine — timestamps are injected `now` arguments, with CPython fallbacks for `ticks_add`/`ticks_diff`), `ui.py` and `effects.py` (need only a graphics object; `effects.py` shims `micropython.native` on CPython). Test and iterate on these without hardware.
- **Device-only**: `main.py`, `board.py`, `sound.py`, `net_time.py` import MicroPython/firmware modules. Verify with `python3 -m py_compile` on the host; they can only run on the board.

Responsibilities:

- `board.py` is the **only** place hardware modules (`stellar`/`galactic`/`cosmic`, `picographics`) are imported, keyed on `config.BOARD`. Everything else consumes its uniform surface: `Unicorn`, `Channel`, `DISPLAY`, `WIDTH`, `HEIGHT`, `BUTTON_A_ZONE`.
- `config.py` holds every tunable (durations, colors, sound, timezone) plus the per-board `LAYOUT` table. `ui.py` derives all coordinates from `WIDTH`/`HEIGHT` + `LAYOUT` — no magic numbers anywhere else.
- `pomodoro.py` knows nothing about buttons or rendering; it reports transitions as return values from `poll()` (`WORK_DONE`/`BREAK_DONE`) that `main.py` turns into beeps and a ~2s full-screen animation from `effects.py` (red tomato bursts when work ends, green rings converge when the break ends). Effects call `create_pen` per pixel with continuous float values (no quantization, no cache — pens are packed ints) and the main loop runs unthrottled while one plays; that combination is what keeps them smooth.
- `main.py` owns the view modes (pomodoro/clock), the "Reset?" confirm overlay, and button edge detection (`Button` class).
- Time: the RTC holds UTC after NTP sync; `net_time.local_hms()` applies the UTC offset + EU DST and returns `None` when unsynced — every caller must handle `None` (clock hidden / `--:--`).

## Hardware constraints

- The 3x5 bitmap font can't fit `MM:SS` in 16px through plain `graphics.text()`. `UI._draw_time()` draws digits at a fixed 4px pitch with a manually drawn 1px colon column (15px total for 4 digits). Reuse it for anything time-like.
- Clock mode uses two generated Matrix 8x6 fonts (5x7 digits): `MatrixChunky8x6.bitmapfont` (bold) for the hours and `MatrixLight8x6.bitmapfont` (thin) for the dimmed minutes — the weight plus `CLOCK_MINUTE_BRIGHTNESS` gives the hour/minute hierarchy. `UI._draw_big()` draws each digit at a fixed 6px pitch (5px glyph + 1px gap) so digits don't jitter and swaps fonts via `UI._set_font()`. These binaries derive from trip5's [Matrix-Fonts](https://github.com/trip5/Matrix-Fonts) BDFs (CC-BY) and are checked in as-is — never edit them. (Both CLAUDE.md and README once referenced a `tools/build_matrix_fonts.py` generator; it is not in the repo.)
- `3x5.bitmapfont` is generated — never edit the binary. The source is the `tom-thumb-new.png` sprite sheet ([Tom Thumb](https://opengameart.org/content/tom-thumb-tiny-ascii-font-3x5), CC0/CC-BY 3.0), converted by `tools/build_font.py` via pgfutil. Font height is 6 (3x5 glyphs + descender row for `gjpqy`); `GLYPH_H` in `ui.py` stays 5 because layout centers on the cap height. `tests/test_font.py` asserts every glyph the UI draws exists (zero-width lowercase once rendered "Ready" as a static "R").
- Keep the render loop allocation-light (RP2040 has 264 KB RAM) and stick to MicroPython ≥1.19 syntax; ruff's `target-version = "py38"` keeps autofixes safe.
- UI changes can be previewed without hardware: pass a mock graphics object (implementing `create_pen`, `set_pen`, `set_font`, `clear`, `pixel`, `rectangle`, `text`, `measure_text`) into `UI` and rasterize draw calls to an ASCII grid.

## Deliberate behavior decisions — do not "fix"

- Pressing D (clock mode) fully resets the Pomodoro; switching to the clock means you're done with the session.
- Work → break auto-advances; break → Ready waits for an A press.
- The timer keeps running underneath the "Reset?" prompt until the reset is confirmed.
- `Pomodoro.poll()` chains each phase deadline from the previous deadline (not from the poll time) so phases don't drift. On `WORK_DONE`, `main.py` then pads the break deadline by the burst effect's duration (`pomo.postpone`) so the animation doesn't eat into the break — the pad is a fixed constant, so no drift accumulates.
- Missing `secrets.py` or failed WiFi degrades gracefully; the Pomodoro must always work offline.

## Code style

- **Do not add comments that explain what the code does.** Comments are only for non-obvious constraints, units, or hardware quirks — match the existing sparse style.
- Ruff-formatted; run `ruff check .` and `ruff format .` before finishing any change.
