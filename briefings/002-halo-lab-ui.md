# Briefing 002: HALO LAB, measurement software for the uConsole

Author: Mausi (master chat)
Executor: Claude Code (CC)
Repository: https://github.com/saschadaemgen/halo-gauge-experiment
Development machine: Windows PC, C:\Projects\CYB3RGUN\HUBEN\halo-gauge-experiment
Target machine: Clockwork uConsole, CM4, Clockwork Raspberry Pi OS image, 1280 x 720
Hardware under test: Heltec WiFi LoRa 32 V2 on USB, firmware probe-0.2

## Goal

A local measurement application that reads the probe firmware over USB, shows the running measurement on the uConsole screen, and writes every finished series to disk as a raw log and a JSON record. It replaces the serial monitor for all further experiments, and every screen of it will end up as a photograph in a public forum post.

## Working rules

- Stop at the first failure and report the exact output. Do not improvise around a missing dependency, report it.
- Ask before adding any dependency that is not in the list below.
- Code, comments, docstrings and UI text in English. No em dashes anywhere.
- Do not touch anything under `firmware/`, `hardware/`, `docs/research/` or `docs/method/`.
- Do not invent measurement logic. All numbers come from the firmware. The UI computes nothing except formatting.
- Conventional Commits, commit messages at the end.

## Protocol, firmware probe-0.2

Serial, 115200 baud, 8N1. The firmware starts in human readable mode. Sending `j` switches it to JSON mode and it answers with a `hello` object. In JSON mode every line is exactly one JSON object with a `type` field. Single character commands, no line ending required:

| key | effect |
|---|---|
| `j` | toggle JSON mode, emits `hello` when switching on |
| `p` | emit `hello` again (status poll) |
| `w` | run a series on the white card |
| `y` | run a series on the yellow card |
| `r` | emit the report for every light source that has both targets |
| `i` | switch light source, blue or white, emits `ack` |
| `g` | cycle TCS34725 gain 1x / 4x / 16x / 60x, emits `ack` |
| `l` | toggle live stream, emits `ack` |
| `c` | clear stored results, emits `ack` |

Object types:

```
{"type":"hello","fw":"probe-0.2","tcs":0,"oled":1,"light":"blue","gain":"16x","samples":50}
{"type":"ack","cmd":"g","light":"blue","gain":"60x","live":1}
{"type":"live","t":123456,"c":0,"r":0,"g":0,"b":0,"pta":2286.3,"ptb":142.0,"sat":0,"light":"blue","gain":"60x"}
{"type":"run","target":"white","light":"blue","gain":"60x","samples":50}
{"type":"sample","target":"white","led":1,"n":0,"c":0,"r":0,"g":0,"b":0,"pta":2286.0,"ptb":142.0}
{"type":"series","target":"white","light":"blue","gain":"60x","samples":50,"saturated":0,
 "on":{"C":[1067.70,38.53],"R":[...],"G":[...],"B":[...],"PT-A":[...],"PT-B":[...]},
 "off":{...},"signal":{"C":1067.70,...},"noise":{"C":38.53,...}}
{"type":"report","light":"blue","saturated":0,
 "channels":[{"ch":"C","unit":"cnt","white":1067.70,"yellow":224.10,"contrast":0.7901,"noise":38.76,"snr":21.80,"go":1}, ...],
 "best":"B","best_snr":22.00,"go":1}
{"type":"error","msg":"unknown command x"}
```

In `on`/`off` each channel is `[mean, sd]`. Channel order is always C, R, G, B, PT-A, PT-B. `contrast` is a fraction, display it as a percentage. A run emits one `run`, then 100 `sample` objects (50 with `led:1`, 50 with `led:0`), then one `series`. A run takes about 20 seconds.

Unparseable lines are not an error: the firmware may print a boot banner or a stray human line. Ignore any line that is not valid JSON, but keep it in the raw log.

## Architecture

Python 3 on the uConsole. A local HTTP server on 127.0.0.1:8760 serves one page and a websocket. The browser runs in kiosk mode and shows it full screen. Reason for this split: the same code runs on a normal PC, and the screen is easy to make look good.

Dependencies, all from apt or pip on the Pi: `pyserial`, `websockets`, `aiohttp`. Nothing else. No build step, no npm, no bundler. The page is one HTML file with inline CSS and JavaScript plus the logo SVG, served from `software/labui/static/`.

```
software/labui/
  README.md            how to install and run, on the Pi and on a PC
  halo_lab.py          server: serial reader, JSON parser, websocket, file writer
  static/index.html    the whole UI
  static/cyb3rgun_logo.svg
```

Serial port: default `/dev/ttyUSB0`, override with `--port`. On Windows `COM6`. Add `--list` to print available ports and exit. If the port is missing or busy, the UI must still load and show a clear disconnected state with the port name and a retry button. Reconnect automatically every 2 seconds while disconnected.

## Files written per series

Directory `docs/log/data/`, created if missing. Two files per finished series, same stem:

`YYYY-MM-DD_HHMM_<target>_<light>_<gain>_<aperture>.txt` and `.json`

`<aperture>` comes from an input field in the UI, free text, default `none`, sanitised to lowercase with non alphanumerics replaced by `-`. The `.txt` is a human readable record in the same layout the firmware prints in text mode, with a header block naming date, firmware version, sensor, light, gain, aperture, sample count and the operator note. The `.json` holds the raw `series` object plus that same metadata under a `meta` key.

A report is written as `YYYY-MM-DD_HHMM_report_<light>_<aperture>.txt` and `.json` when it arrives.

Every raw serial line, JSON or not, is appended to `docs/log/data/session_YYYY-MM-DD.log` with a millisecond timestamp. That file is the fallback if anything else goes wrong.

## Screen

Fixed 1280 x 720, no page scrolling, nothing may be cut off. Design it once for that size, do not build a responsive grid.

Layout, left to right:

```
+--------------------------------------------------------------+
| [logo]  HALO LAB          blue - 60x - 1.0 mm     probe-0.2   |  56 px header
+---------------------+----------------------+-----------------+
|  LIVE               |  SERIES              |  RESULT         |
|  six channel bars,  |  the running series   |  report table,  |
|  value in mV / cnt  |  as a strip chart,    |  one row per    |
|  saturation flag    |  LED on and off runs  |  channel, GO or |
|                     |  drawn apart          |  no per row     |
|                     |                      |  verdict block  |
+---------------------+----------------------+-----------------+
|  w white   y yellow   r report   i light   g gain   c clear   |  72 px footer
+--------------------------------------------------------------+
```

Behaviour:

- The header always shows the current light source, gain and aperture, because every photograph of this screen has to be self explanatory.
- During a run the whole screen shows it: a progress bar with the sample count, the LED state as a labelled indicator, and the strip chart filling left to right. The other panels stay visible but dim.
- When a `series` arrives, its numbers replace the series panel: mean and sd for LED on and off, signal and noise per channel, saturation warning if the firmware sets it.
- When a `report` arrives, the result panel fills. The verdict block states the best channel, its SNR and whether the threshold of 10 is met, in words, not just a colour.
- The footer buttons send the keys. They are also bound to the keyboard, because the uConsole has one. Show the key letter on each button.
- An aperture field and a one line operator note field sit in the footer. Both go into the file metadata. Changing them does not send anything to the firmware.
- A camera button saves a PNG screenshot of the page into `docs/log/images/` with the same name stem as the last series. Use `html2canvas` only if it can be vendored as a single local file, otherwise leave the button out and say so in the report.

## Visual direction

The palette is not decoration, it is the experiment: the light source is blue, the needle is yellow, the dial is white. Use exactly those three as the meaningful colours and let the rest be dark and quiet.

```
--bg      #0A0C0E   near black, the inside of the light chamber
--panel   #12161A   panel fill
--line    #1E252B   hairlines and panel borders
--ink     #C9D3DA   body text
--dim     #6B7A85   labels and secondary text
--beam    #009FE3   CYB3RGUN blue, the light source, primary accent
--needle  #FCB803   needle yellow, measured from the gauge artwork
--dial    #F1EFE8   dial white
```

Rules for using them: the blue belongs to the light and to anything the operator triggers. The yellow belongs to the yellow card and its measured values. The white belongs to the white card. A GO verdict is blue, not green. A failed threshold is dim grey, not red, because a low contrast reading is a result and not a fault. The only red in the application is a lost serial connection.

Type: one monospace family for everything, because this is an instrument and the numbers must align. Use the stack `"DejaVu Sans Mono", "Liberation Mono", monospace`, which is present on the Clockwork image. No web fonts, the machine may be offline. Measured values are the largest type on the screen. Labels are small and quiet, in sentence case, not all caps.

The logo sits top left at 28 px, unmodified, in its own blue. Do not tint it, do not put it behind anything, do not repeat it.

Motion: exactly two moving things, the live bars and the strip chart, both driven by data. No transitions on buttons, no fades, no glow. The instrument look comes from precision and alignment, not from effects. Do not add scan lines, grid overlays, flicker, glitch text or terminal typing effects.

Numbers: fixed decimal places per channel, right aligned, with the unit in a separate dim column so the digits line up. Never let a value change its width while updating.

## Acceptance

1. `python3 halo_lab.py --list` prints the available serial ports.
2. With the Heltec connected, `python3 halo_lab.py` starts, the page loads at http://127.0.0.1:8760, the header shows firmware version and light source within two seconds.
3. Unplugging the Heltec shows the disconnected state, plugging it back in recovers without restarting the program.
4. Pressing `w` runs a series, the progress and the strip chart follow it live, and afterwards the numbers match what the firmware printed.
5. After `w`, `y` and `r`, four data files and one session log exist under `docs/log/data/` and the values in them match the screen.
6. The page fits 1280 x 720 with no scrollbar and no clipped text.

## Commits

```
feat(labui): add serial reader and websocket server for probe-0.2
feat(labui): add HALO LAB measurement screen
docs(labui): add install and run instructions
```

## Build hint

No firmware change in this briefing, so no flashing. On the uConsole: `git pull`, then `python3 software/labui/halo_lab.py`. If dependencies are missing, report the exact `pip install` line rather than running it blind.

## Report back

1. Python version on the PC and, if you touched it, on the uConsole
2. The dependency list actually installed
3. Whether the screenshot button was implemented, and if not, why
4. A description of what the screen shows in the disconnected state
5. The three commit hashes and the push result

No suggestions for next steps.
