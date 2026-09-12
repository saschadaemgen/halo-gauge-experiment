#!/usr/bin/env bash
# Turns the uConsole into the CYB3RGUN research terminal: both servers start on
# boot, the browser comes up full screen on the launcher, no desktop in sight.
set -e
REPO="$HOME/halo-gauge-experiment"
HERE="$REPO/software/launcher"

echo "== packages =="
sudo apt update
sudo apt install -y python3-serial chromium unclutter scrot

echo "== services =="
mkdir -p ~/.config/systemd/user
cp "$HERE/systemd/halo-lab.service"          ~/.config/systemd/user/
cp "$HERE/systemd/cyb3rgun-launcher.service" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now halo-lab cyb3rgun-launcher
sudo loginctl enable-linger "$USER"

echo "== kiosk =="
mkdir -p ~/.config/labwc
cat > ~/.config/labwc/autostart <<'AUTO'
# CYB3RGUN research terminal
unclutter --timeout 2 &
sleep 3
chromium --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
         --check-for-update-interval=31536000 \
         --app=http://127.0.0.1:8750 &
AUTO

echo
echo "done. reboot and the terminal comes up on its own:"
echo "  sudo reboot"
