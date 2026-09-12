# HALO LAB

Measurement front end for the halo-gauge-experiment probe. It reads the Heltec
board over USB, shows the running measurement full screen, and records every
finished series and report into `docs/log/data/`.

Built for the Clockwork uConsole at 1280 x 720, runs the same on any PC.

## Install

Only pyserial is needed. Everything else is the Python standard library.

    sudo apt install python3-serial          # Raspberry Pi OS
    pip3 install pyserial                    # anywhere else

For the screenshot button, `scrot` must be present. Without it the button
reports what is missing and nothing else breaks.

    sudo apt install scrot

## Run

    python3 software/labui/halo_lab.py --list          # which ports exist
    python3 software/labui/halo_lab.py                 # uses /dev/ttyUSB0 or COM6
    python3 software/labui/halo_lab.py --port COM6
    python3 software/labui/halo_lab.py --simulate      # no hardware, fake data

Then open http://127.0.0.1:8760

To reach it from another machine, for example the board on a PC and the screen
on the uConsole:

    python3 software/labui/halo_lab.py --host 0.0.0.0

Kiosk mode on the uConsole:

    chromium-browser --kiosk --app=http://127.0.0.1:8760

## Using it

The board is switched into JSON mode automatically on connect. Every button in
the footer is also a key on the keyboard, the letter is printed on the button.

| key | does |
|---|---|
| w | measure the white card |
| y | measure the yellow card |
| r | report contrast and SNR |
| i | switch light source, blue or white |
| g | cycle the colour sensor gain |
| c | clear stored results |
| s | screenshot into `docs/log/images/` |

Fill in the aperture field before measuring. It goes into the file names and
into the header of every record, which is the only way to tell two otherwise
identical series apart later.

## What gets written

Per finished series and per report, into `docs/log/data/`:

- `YYYY-MM-DD_HHMM_<target>_<light>_<gain>_<aperture>.txt`, the human readable
  record with a header naming firmware, light, gain, aperture and note
- the same stem with `.json`, holding the raw firmware object plus that metadata

Every serial line, parseable or not, is appended to
`docs/log/data/session_YYYY-MM-DD.log` with a timestamp. If anything else goes
wrong, that file still has the measurement in it.

## Colours

The palette is the experiment, not decoration. Blue is the light source and
anything the operator triggers, yellow is the needle and its measured values,
white is the dial. A go verdict is blue. A failed threshold is grey, because a
low reading is a result and not a fault. The only red is a lost serial link.
