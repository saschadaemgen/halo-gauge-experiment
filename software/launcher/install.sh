#!/usr/bin/env bash
# Turns the uConsole into the CYB3RGUN research terminal: both servers start on
# boot, the browser comes up full screen on the launcher, no desktop in sight.
#
# Safe to run more than once. It never overwrites an existing autostart file,
# it appends to it, and a broken unrelated package does not stop it.
set -u
REPO="$HOME/halo-gauge-experiment"
HERE="$REPO/software/launcher"
MARK="# --- CYB3RGUN research terminal ---"

say(){ printf "\n== %s ==\n" "$1"; }

say "packages"
# a package that is already broken for other reasons must not stop us
sudo apt-get install -y python3-serial chromium unclutter scrot || \
  echo "apt reported a problem, continuing. checking what matters:"
for p in python3 chromium; do
  command -v "$p" >/dev/null && echo "  ok   $p" || echo "  MISSING $p"
done
python3 -c "import serial" 2>/dev/null && echo "  ok   pyserial" || echo "  MISSING pyserial"

say "services"
mkdir -p ~/.config/systemd/user
cp "$HERE/systemd/halo-lab.service"          ~/.config/systemd/user/
cp "$HERE/systemd/cyb3rgun-launcher.service" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable halo-lab cyb3rgun-launcher
systemctl --user restart halo-lab cyb3rgun-launcher
sudo loginctl enable-linger "$USER" || true
sleep 2
systemctl --user --no-pager is-active halo-lab cyb3rgun-launcher || true

say "kiosk"
AUTO=~/.config/labwc/autostart
mkdir -p ~/.config/labwc
touch "$AUTO"
if grep -qF "$MARK" "$AUTO"; then
  echo "  autostart already carries the terminal block, left alone"
else
  cp "$AUTO" "$AUTO.backup.$(date +%Y%m%d%H%M)" 2>/dev/null || true
  BROWSER=$(command -v chromium || command -v chromium-browser || echo chromium)
  cat >> "$AUTO" <<AUTOEOF

$MARK
unclutter --timeout 2 &
( # the panel and the file manager desktop have no business on a terminal
  pkill -f wf-panel-pi 2>/dev/null
  pkill -f "pcmanfm --desktop" 2>/dev/null
  # start as soon as the launcher answers, not after a fixed wait
  for i in \$(seq 1 60); do
    curl -s -o /dev/null http://127.0.0.1:8750/ && break
    sleep 0.25
  done
  $BROWSER --kiosk --password-store=basic --noerrdialogs --disable-infobars \
    --disable-session-crashed-bubble --check-for-update-interval=31536000 \
    --start-fullscreen --app=http://127.0.0.1:8750 ) &
AUTOEOF
  echo "  appended to $AUTO, old copy kept as a backup"
fi

say "check"
sleep 1
for p in 8750 8760; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" || true)
  echo "  port $p answers $code"
done
echo
echo "if both ports answer 200, reboot and the terminal comes up on its own:"
echo "  sudo reboot"
