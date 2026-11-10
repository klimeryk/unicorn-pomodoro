# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A MicroPython Pomodoro timer for the Pimoroni Stellar Unicorn: a 16x16 LED matrix driven by an **original Raspberry Pi Pico W (RP2040) — not a Pico 2 W** (Pimoroni ships separate firmware builds; always the `pico_w` variant). The code is portable to the Galactic (53x11) and Cosmic (32x32) Unicorns by changing `BOARD` in `config.py`. Behavior is modeled on the user's Garmin app, [garmodoro](https://github.com/klimeryk/garmodoro).

## Commands

```sh
# Host tests — stdlib unittest, no dependencies; run from the repo root
python3 -m unittest              # everything
python3 -m unittest tests.test_ui # one module (also test_pomodoro, test_effects, test_sound, test_net_time, test_font)
ruff check .                     # lint — must stay clean; config in pyproject.toml
ruff format .                    # format
python3 tools/build_font.py      # regenerate 3x5.bitmapfont (needs: pip install pgfutil pillow)
mpremote cp main.py config.py board.py compat.py pomodoro.py ui.py effects.py sound.py net_time.py secrets.py 3x5.bitmapfont MatrixChunky8x6.bitmapfont MatrixLight8x6.bitmapfont : && mpremote reset
```

The Matrix 8x6 clock fonts (`MatrixChunky8x6.bitmapfont`, `MatrixLight8x6.bitmapfont`) are checked in; the repo currently ships **no** generator for them (only `tools/build_font.py`, for the 3x5 font).

Set `TEST_MODE = True` in `config.py` to shrink all phases to seconds for on-device testing of a full cycle.

## Architecture

The core split is host-runnable vs device-only:

- **Host-runnable**: `pomodoro.py` (pure state machine — timestamps are injected `now` arguments), `ui.py` and `effects.py` (need only a graphics object), `sound.py` (needs only a unicorn/channel stand-in), and `net_time.py`'s sync state machine and EU DST rule (the hardware calls `_open_wifi`/`_ntp_settime` are patched out in tests). `compat.py` supplies CPython stand-ins for `ticks_add`/`ticks_diff` — wrapping at 2**30 exactly like MicroPython's `ticks_ms`, so tests can cover wraparound — and `micropython.native`. Test and iterate on these without hardware.
- **Device-only**: `main.py`, `board.py` and `net_time._Wifi`/`_ntp_settime` need MicroPython/firmware modules. Verify with `python3 -m py_compile` on the host; they can only run on the board.

Responsibilities:

- `board.py` is the **only** place hardware modules (`stellar`/`galactic`/`cosmic`, `picographics`) are imported, keyed on `config.BOARD`. Everything else consumes its uniform surface: `Unicorn`, `Channel`, `DISPLAY`, `WIDTH`, `HEIGHT`, `BUTTON_A_HINT_PIXELS`.
- `config.py` holds every tunable (durations, colors, sound, timezone) plus the per-board `LAYOUTS` table (`LAYOUT` is the selected board's entry). `ui.py` derives all coordinates from `WIDTH`/`HEIGHT` + `LAYOUT` — no magic numbers anywhere else.
- `pomodoro.py` knows nothing about buttons or rendering; it reports transitions as return values from `poll()` (`WORK_DONE`/`BREAK_DONE`) that `main.py` turns into beeps and a ~2s full-screen animation from `effects.py` (red tomato bursts when work ends, green rings converge when the break ends). Effects and the UI call `create_pen` directly with continuous float-scaled values (no quantization, no cache — pens are packed small ints, so this doesn't allocate); that is what keeps them smooth.
- `main.py`'s `App` owns the view modes (pomodoro/clock), the "Reset?" confirm overlay, debounced button edge detection (`Button`), and the per-frame order: buttons → timer/sound → time sync (only when `_idle()`) → render. Frames are paced against a `FRAME_MS` deadline, so render time doesn't lower the FPS and per-frame steps (brightness/volume) run at a constant rate.
- Time: the RTC holds UTC after NTP sync; `NetworkTime.local_hms()` applies the UTC offset + EU DST and returns `None` when unsynced — every caller must handle `None` (clock hidden / `--:--`). `NetworkTime.poll(now)` is a per-frame state machine: `wlan.connect()` is asynchronous on rp2, so connecting never blocks; only the NTP request blocks (≤ `_NTP_TIMEOUT_S`, one attempt per poll). It retries an unsynced clock with exponential backoff (`WIFI_RETRY_START_S` → `WIFI_RETRY_MAX_S`), counted from the end of the failed attempt, and resyncs every `NTP_RESYNC_HOURS` once synced.

## Hardware constraints

- The 3x5 bitmap font can't fit `MM:SS` in 16px through plain `graphics.text()`. `UI._draw_time()` draws digits at a fixed 4px pitch (`UI._draw_digits()`) with a manually drawn 1px colon column (`UI._draw_colon()`; 15px total for 4 digits). Reuse it for anything time-like.
- Clock mode uses two generated Matrix 8x6 fonts (5x7 digits): `MatrixChunky8x6.bitmapfont` (bold) for the hours and `MatrixLight8x6.bitmapfont` (thin) for the dimmed minutes — the weight plus `CLOCK_MINUTE_BRIGHTNESS` gives the hour/minute hierarchy. `UI._draw_big_digits()` draws each digit at a fixed 6px pitch (5px glyph + 1px gap) so digits don't jitter and swaps fonts via `UI._set_font()`. These binaries derive from trip5's [Matrix-Fonts](https://github.com/trip5/Matrix-Fonts) BDFs (CC-BY) and are checked in as-is — never edit them. (Both CLAUDE.md and README once referenced a `tools/build_matrix_fonts.py` generator; it is not in the repo.)
- `3x5.bitmapfont` is generated — never edit the binary. The source is the `assets/tom-thumb-new.png` sprite sheet ([Tom Thumb](https://opengameart.org/content/tom-thumb-tiny-ascii-font-3x5), CC0/CC-BY 3.0), converted by `tools/build_font.py` via pgfutil. Font height is 6 (3x5 glyphs + descender row for `gjpqy`); `SMALL_GLYPH_H` in `ui.py` stays 5 because layout centers on the cap height. `tests/test_font.py` asserts every glyph the UI draws exists, taking the labels from `ui.py`'s `*_LABEL` constants (zero-width lowercase once rendered "Ready" as a static "R").
- Keep the render loop allocation-light (RP2040 has 264 KB RAM) and stick to MicroPython ≥1.19 syntax; ruff's `target-version = "py38"` keeps autofixes safe.
- rp2 floats are single precision (24-bit mantissa): reduce tick counts with integer `%` before float math (see `UI._pulse`), or animations judder after a few days of uptime.
- The Pimoroni synth renders audio from a DMA IRQ: a note sounds until Python calls `trigger_release()`. Never block the main loop while `Sound.busy()` — a blocked loop holds the current note (this is what once made the break chime "stick").
- Compare stored ticks only with `ticks_diff`, and keep stored timestamps short-lived: `ticks_ms` wraps every ~12.4 days and differences are only valid within ±2**29 ms.
- UI changes can be previewed without hardware: pass a graphics stand-in (`tests/fakes.FakeGraphics` implements the full surface and rejects off-screen draws and invalid pens) into `UI`. `tests/test_ui.py` renders every screen on all three board sizes by patching `config.LAYOUT`.

## Deliberate behavior decisions — do not "fix"

- Pressing D (clock mode) fully resets the Pomodoro; switching to the clock means you're done with the session.
- Work → break auto-advances; break → Ready waits for an A press.
- The timer keeps running underneath the "Reset?" prompt until the reset is confirmed.
- `Pomodoro.poll()` chains each phase deadline from the previous deadline (not from the poll time) so phases don't drift. On `WORK_DONE`, `main.py` then pads the break deadline by the burst effect's duration (`Pomodoro.postpone()`) so the animation doesn't eat into the break — the pad is a fixed constant, so no drift accumulates.
- Missing `secrets.py` or failed WiFi degrades gracefully; the Pomodoro must always work offline.
- Time sync only advances while idle — clock mode or Ready, no effect playing and `Sound.busy()` false — because an NTP attempt can still block the loop for up to `_NTP_TIMEOUT_S`. A failed resync after the first success keeps the current time and waits the full `NTP_RESYNC_HOURS`.

## Code style

- **Do not add comments that explain what the code does.** Comments are only for non-obvious constraints, units, or hardware quirks — match the existing sparse style.
- Ruff-formatted; run `ruff check .` and `ruff format .` before finishing any change.
