# CYB3RGUN research terminal

Turns a Clockwork uConsole into an instrument: it boots into a menu of the
project's applications, no desktop, no Linux in sight.

## What it does

- `launcher.py` serves the start screen on port 8750 and knows which
  applications exist, whether they are running, and how to start them
- `apps.json` is that list. Adding a tool is an entry in a file, not code
- two systemd user services keep the launcher and HALO LAB alive across reboots
- the browser starts full screen on the launcher as soon as it answers
- `boot-splash.sh` replaces the Raspberry boot screens with the project's own

## Install

```
cd ~/halo-gauge-experiment
bash software/launcher/install.sh
bash software/launcher/boot-splash.sh
sudo reboot
```

Both scripts keep a backup of anything they change and can be run again
safely. `install.sh` appends to the labwc autostart rather than replacing it.

## The application list

```json
{
  "key": "1",
  "name": "HALO LAB",
  "line": "optical gauge probe",
  "detail": "contrast, needle sweep, campaigns",
  "url": "http://127.0.0.1:8760",
  "check": "127.0.0.1:8760",
  "service": "halo-lab"
}
```

`url` sends the browser somewhere, `run` starts a program, `check` is a
host:port that decides whether the tile shows as running, and `soon: true`
greys a tile out for something not built yet.

## Keys

Digits 1 to 9 start an application, `r` refreshes, `p` opens power, plus and
minus change the text size. The uConsole game buttons A, B, X and Y start the
first four tiles. The text size is remembered.

## Notes

Chromium is started with `--password-store=basic`, otherwise it asks for a
keyring password on every start, which on a kiosk is asking nobody.

If the power buttons do nothing, `systemctl poweroff` needs a polkit rule or a
sudoers line for this user.
