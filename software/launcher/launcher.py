#!/usr/bin/env python3
"""
CYB3RGUN launcher.

The screen the device shows when it is switched on. It lists the applications,
says which of them are running, starts them, and can reboot or shut the machine
down. Nothing else is visible: the browser runs in kiosk mode on top of this.

The list itself lives in apps.json next to this file, so new tools are added
without touching any code.

    python3 launcher.py                 # serves http://127.0.0.1:8750
    python3 launcher.py --host 0.0.0.0  # reachable from the network

Standard library only.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
APPS = os.path.join(HERE, "apps.json")

DEFAULT_APPS = {
    "title": "CYB3RGUN",
    "subtitle": "digital shooting cinema",
    "apps": [
        {
            "key": "1", "name": "HALO LAB", "line": "optical gauge probe",
            "detail": "contrast, needle sweep, campaigns",
            "url": "http://127.0.0.1:8760", "check": "127.0.0.1:8760",
            "service": "halo-lab"
        },
        {
            "key": "2", "name": "DATA", "line": "measurement archive",
            "detail": "raw series, reports, exports",
            "open": "docs/log/data"
        },
        {
            "key": "3", "name": "TERMINAL", "line": "shell",
            "detail": "for everything the menu does not cover",
            "run": ["x-terminal-emulator"]
        }
    ]
}


def load_apps():
    if not os.path.isfile(APPS):
        with open(APPS, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_APPS, f, indent=2)
        return DEFAULT_APPS
    try:
        with open(APPS, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print("[apps] %s is broken: %s" % (APPS, exc), flush=True)
        return DEFAULT_APPS


def reachable(target, timeout=0.35):
    """True if something answers on host:port."""
    try:
        host, _, port = target.partition(":")
        with socket.create_connection((host or "127.0.0.1", int(port)), timeout):
            return True
    except Exception:
        return False


def service_state(name):
    try:
        out = subprocess.run(["systemctl", "is-active", name], capture_output=True,
                             text=True, timeout=3).stdout.strip()
        return out or "unknown"
    except Exception:
        return "unknown"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def handle_one_request(self):
        try:
            BaseHTTPRequestHandler.handle_one_request(self)
        except (ConnectionError, TimeoutError, OSError):
            self.close_connection = True

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, default=str), "application/json")

    def _file(self, name, ctype):
        path = os.path.join(STATIC, name)
        if not os.path.isfile(path):
            return self._send(404, "not found")
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._file("index.html", "text/html; charset=utf-8")
        elif self.path == "/static/cyb3rgun_logo.svg":
            self._file("cyb3rgun_logo.svg", "image/svg+xml")
        elif self.path == "/api/apps":
            cfg = load_apps()
            for a in cfg.get("apps", []):
                if a.get("check"):
                    a["up"] = reachable(a["check"])
                if a.get("service"):
                    a["state"] = service_state(a["service"])
            cfg["host"] = socket.gethostname()
            cfg["ip"] = self._own_ip()
            cfg["time"] = datetime.now().strftime("%H:%M")
            self._json(cfg)
        else:
            self._send(404, "not found")

    @staticmethod
    def _own_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 53))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "offline"

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads((self.rfile.read(length) or b"{}").decode("utf-8") or "{}")
        except ValueError:
            body = {}
        if self.path == "/api/launch":
            return self._launch(body.get("key"))
        if self.path == "/api/service":
            name, action = body.get("name"), body.get("action")
            if action not in ("start", "stop", "restart") or not name:
                return self._json({"error": "bad request"}, 400)
            try:
                subprocess.run(["systemctl", "--user", action, name], timeout=8)
                return self._json({"ok": True, "state": service_state(name)})
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if self.path == "/api/power":
            what = body.get("what")
            cmd = {"reboot": ["sudo", "systemctl", "reboot"],
                   "off": ["sudo", "systemctl", "poweroff"]}.get(what)
            if not cmd:
                return self._json({"error": "bad request"}, 400)
            self._json({"ok": True})
            threading.Timer(0.6, lambda: subprocess.Popen(cmd)).start()
            return
        self._send(404, "not found")

    def _launch(self, key):
        cfg = load_apps()
        app = next((a for a in cfg.get("apps", []) if a.get("key") == key), None)
        if not app:
            return self._json({"error": "unknown app"}, 404)
        if app.get("run"):
            try:
                subprocess.Popen(app["run"], cwd=os.path.expanduser(app.get("cwd", "~")),
                                 start_new_session=True)
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        return self._json({"ok": True, "url": app.get("url"), "open": app.get("open")})


def main():
    ap = argparse.ArgumentParser(description="CYB3RGUN launcher")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8750)
    args = ap.parse_args()
    load_apps()
    print("CYB3RGUN launcher")
    print("  apps : %s" % APPS)
    print("  open : http://%s:%d" % ("127.0.0.1" if args.host in ("0.0.0.0", "") else args.host,
                                     args.port))
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
