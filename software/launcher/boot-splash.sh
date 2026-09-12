#!/usr/bin/env bash
# Replaces the Raspberry boot screens with the CYB3RGUN one.
#
#   the firmware rainbow            -> off
#   the kernel messages and cursor  -> hidden
#   the plymouth raspberries        -> our splash
#
# Every original is kept as a .backup next to it, so this is reversible.
set -u
IMG="$(cd "$(dirname "$0")" && pwd)/cyb3rgun_splash.png"
say(){ printf "\n== %s ==\n" "$1"; }

[ -f "$IMG" ] || { echo "missing $IMG"; exit 1; }

BOOT=/boot/firmware
[ -d "$BOOT" ] || BOOT=/boot

say "firmware rainbow"
if ! grep -q "^disable_splash=1" "$BOOT/config.txt"; then
  sudo cp "$BOOT/config.txt" "$BOOT/config.txt.backup.$(date +%Y%m%d%H%M)"
  echo "disable_splash=1" | sudo tee -a "$BOOT/config.txt" > /dev/null
  echo "  added disable_splash=1"
else
  echo "  already off"
fi

say "kernel messages"
CMD="$BOOT/cmdline.txt"
sudo cp "$CMD" "$CMD.backup.$(date +%Y%m%d%H%M)"
LINE=$(tr -d '\n' < "$CMD")
for opt in quiet splash logo.nologo vt.global_cursor_default=0 loglevel=0 consoleblank=0; do
  case " $LINE " in *" $opt "*) ;; *) LINE="$LINE $opt";; esac
done
echo "$LINE" | sudo tee "$CMD" > /dev/null
echo "  cmdline is now:"
echo "    $LINE"

say "plymouth splash"
if [ -d /usr/share/plymouth/themes/pix ]; then
  sudo cp /usr/share/plymouth/themes/pix/splash.png \
          /usr/share/plymouth/themes/pix/splash.png.backup 2>/dev/null || true
  sudo cp "$IMG" /usr/share/plymouth/themes/pix/splash.png
  echo "  replaced the pix theme splash"
  sudo plymouth-set-default-theme pix 2>/dev/null || true
  sudo update-initramfs -u 2>/dev/null || echo "  initramfs update skipped, image is still in place"
else
  echo "  plymouth theme not found, skipping. the rainbow and the messages are still gone."
fi

say "done"
echo "reboot to see it:  sudo reboot"
