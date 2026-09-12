#!/usr/bin/env python3
"""
HALO LAB, measurement front end for the halo-gauge-experiment probe.

Reads the probe firmware (probe-0.2) over USB, streams every object to the
browser, and records each finished series and report to disk.

Dependencies: pyserial. Everything else is the Python standard library.

    python3 halo_lab.py --list
    python3 halo_lab.py --port /dev/ttyUSB0
    python3 halo_lab.py --simulate          # no hardware, fake data

Then open http://127.0.0.1:8760
"""

import argparse
import json
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

CHANNELS = ["C", "R", "G", "B", "PT-A", "PT-B"]
UNITS = {"C": "cnt", "R": "cnt", "G": "cnt", "B": "cnt", "PT-A": "mV", "PT-B": "mV"}


# ---------------------------------------------------------------- hub

class Hub:
    """Fans out messages to every connected browser."""

    def __init__(self):
        self.lock = threading.Lock()
        self.clients = []
        self.last_state = {}

    def subscribe(self):
        q = queue.Queue(maxsize=2000)
        with self.lock:
            self.clients.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def publish(self, obj):
        if obj.get("type") in ("hello", "ack"):
            self.last_state.update({k: obj[k] for k in ("light", "gain", "fw", "tcs") if k in obj})
        line = json.dumps(obj, separators=(",", ":"))
        with self.lock:
            dead = []
            for q in self.clients:
                try:
                    q.put_nowait(line)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self.clients.remove(q)


# ---------------------------------------------------------------- recorder

class Recorder:
    """Writes the raw session log and one txt plus one json file per result."""

    def __init__(self, data_dir, image_dir):
        self.data_dir = data_dir
        self.image_dir = image_dir
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        self.meta = {"aperture": "none", "note": "", "operator": "", "label": ""}
        self.last_stem = None
        self.lock = threading.Lock()

    def _session_path(self):
        return os.path.join(self.data_dir, "session_%s.log" % datetime.now().strftime("%Y-%m-%d"))

    def raw(self, line):
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self.lock:
            with open(self._session_path(), "a", encoding="utf-8") as f:
                f.write("%s  %s\n" % (stamp, line.rstrip("\r\n")))

    def _slug(self, text, default):
        out = "".join(c.lower() if c.isalnum() else "-" for c in (text or "").strip())
        while "--" in out:
            out = out.replace("--", "-")
        out = out.strip("-")
        return out or default

    def _header(self, obj, kind):
        now = datetime.now()
        lines = [
            "# halo-gauge-experiment, %s" % kind,
            "# date      : %s" % now.strftime("%Y-%m-%d %H:%M:%S"),
            "# firmware  : %s" % self.meta.get("fw", "unknown"),
            "# light     : %s" % obj.get("light", "?"),
            "# gain      : %s" % obj.get("gain", "n/a"),
            "# aperture  : %s" % self.meta.get("aperture", "none"),
            "# samples   : %s" % obj.get("samples", "n/a"),
        ]
        if self.meta.get("operator"):
            lines.append("# operator  : %s" % self.meta["operator"])
        if self.meta.get("note"):
            lines.append("# note      : %s" % self.meta["note"])
        return lines

    def series(self, obj):
        if obj.get("target") == "point" and self.meta.get("label"):
            obj["label"] = self.meta["label"]
        stem = "%s_%s_%s_%s_%s" % (
            datetime.now().strftime("%Y-%m-%d_%H%M"),
            self._slug(obj.get("label") or obj.get("target"), "target"),
            self._slug(obj.get("light"), "light"),
            self._slug(obj.get("gain"), "gain"),
            self._slug(self.meta.get("aperture"), "none"),
        )
        self.last_stem = stem
        body = list(self._header(obj, "series"))
        body.append("")
        body.append("      ch     on.mean   on.sd   off.mean  off.sd   signal   noise")
        for ch in CHANNELS:
            on = obj.get("on", {}).get(ch, [0, 0])
            off = obj.get("off", {}).get(ch, [0, 0])
            body.append("      %-5s %9.1f %7.2f %9.1f %7.2f %8.1f %7.2f %s" % (
                ch, on[0], on[1], off[0], off[1],
                obj.get("signal", {}).get(ch, 0.0), obj.get("noise", {}).get(ch, 0.0), UNITS[ch]))
        if obj.get("saturated"):
            body.append("      WARNING: clear channel saturated, lower the gain and repeat")
        self._write(stem, body, obj)
        return stem

    def report(self, obj):
        stem = "%s_report_%s_%s" % (
            datetime.now().strftime("%Y-%m-%d_%H%M"),
            self._slug(obj.get("light"), "light"),
            self._slug(self.meta.get("aperture"), "none"),
        )
        body = list(self._header(obj, "report"))
        body.append("")
        body.append("  ch     white     yellow   contrast    noise     SNR   verdict")
        for row in obj.get("channels", []):
            body.append("  %-5s %9.1f %9.1f %8.1f %%  %7.2f %7.1f   %s" % (
                row["ch"], row["white"], row["yellow"], row["contrast"] * 100.0,
                row["noise"], row["snr"], "GO" if row["go"] else "no"))
        body.append("")
        body.append("  best channel: %s  SNR=%.1f  ->  %s" % (
            obj.get("best", "none"), obj.get("best_snr", 0.0),
            "GO: optical readout is viable" if obj.get("go") else "NO-GO: contrast insufficient"))
        self._write(stem, body, obj)
        return stem

    def _write(self, stem, body, obj):
        with self.lock:
            with open(os.path.join(self.data_dir, stem + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(body) + "\n")
            payload = {"meta": dict(self.meta, recorded=datetime.now().isoformat(timespec="seconds")),
                       "data": obj}
            with open(os.path.join(self.data_dir, stem + ".json"), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

    def screenshot(self):
        """Server side screen grab, used by the camera button."""
        tool = shutil.which("scrot") or shutil.which("grim") or shutil.which("import")
        if not tool:
            return None, "no screenshot tool found, install scrot"
        stem = self.last_stem or datetime.now().strftime("%Y-%m-%d_%H%M_screen")
        path = os.path.join(self.image_dir, stem + ".png")
        try:
            if tool.endswith("import"):
                subprocess.run([tool, "-window", "root", path], check=True, timeout=10)
            elif tool.endswith("grim"):
                subprocess.run([tool, path], check=True, timeout=10)
            else:
                subprocess.run([tool, "-o", path], check=True, timeout=10)
        except Exception as exc:
            return None, str(exc)
        return path, None


# ---------------------------------------------------------------- serial

class SerialLink(threading.Thread):
    """Opens the port, keeps it open, reads lines, writes single key commands."""

    def __init__(self, port, baud, hub, recorder):
        super().__init__(daemon=True)
        self.port_name = port
        self.baud = baud
        self.hub = hub
        self.recorder = recorder
        self.ser = None
        self.connected = False
        self.last_detail = None
        self.last_json = 0.0
        self.last_nudge = 0.0
        self.stop_flag = threading.Event()
        self.write_lock = threading.Lock()

    def send(self, key):
        with self.write_lock:
            if self.ser is None:
                return False
            try:
                self.ser.write(key.encode("ascii"))
                self.ser.flush()
                return True
            except Exception:
                return False

    def _announce(self, connected, detail=""):
        if connected != self.connected or detail != self.last_detail:
            if connected:
                print("[serial] %s open" % self.port_name, flush=True)
            else:
                print("[serial] %s not open: %s" % (self.port_name, detail or "unknown"), flush=True)
        self.connected = connected
        self.last_detail = detail
        self.hub.publish({"type": "link", "connected": connected,
                          "port": self.port_name, "detail": detail})

    def run(self):
        import serial  # imported here so --list works without a port
        while not self.stop_flag.is_set():
            try:
                # DTR and RTS drive IO0 and EN on the Heltec. pyserial asserts both
                # on open, which holds the ESP32 in reset: no display, no data.
                # Open with them low, then pulse EN once for a clean boot.
                self.ser = serial.Serial()
                self.ser.port = self.port_name
                self.ser.baudrate = self.baud
                self.ser.timeout = 1
                self.ser.dtr = False
                self.ser.rts = False
                self.ser.open()
                self.ser.dtr = False    # IO0 high, normal boot, not the bootloader
                self.ser.rts = True     # EN low, board in reset
                time.sleep(0.12)
                self.ser.rts = False    # EN high, board boots
                time.sleep(0.9)         # let the banner run out
                self.ser.reset_input_buffer()
                self._announce(True)
                self.send("j")          # ask the firmware for JSON
                time.sleep(0.25)
                self.send("p")          # and its status
                buf = b""
                self.last_json = time.time()
                last_byte = time.time()
                while not self.stop_flag.is_set():
                    chunk = self.ser.read(256)
                    if chunk:
                        last_byte = time.time()
                        buf += chunk
                        while b"\n" in buf:
                            raw, buf = buf.split(b"\n", 1)
                            self._process_line(raw.decode("utf-8", "replace"))
                    elif time.time() - last_byte > 6.0:
                        # silent board: reset it and ask for JSON again
                        print("[serial] board silent, resetting it", flush=True)
                        self.ser.dtr = False
                        self.ser.rts = True
                        time.sleep(0.12)
                        self.ser.rts = False
                        time.sleep(0.9)
                        self.ser.reset_input_buffer()
                        self.send("j")
                        time.sleep(0.25)
                        self.send("p")
                        last_byte = time.time()
            except Exception as exc:
                self._announce(False, str(exc))
                try:
                    if self.ser:
                        self.ser.close()
                except Exception:
                    pass
                self.ser = None
                time.sleep(2.0)

    def _process_line(self, line):
        line = line.strip()
        if not line:
            return
        self.recorder.raw(line)
        try:
            obj = json.loads(line)
        except ValueError:
            # the board is talking plain text, so it rebooted and lost JSON mode.
            # nudge it back, at most once every three seconds
            now = time.time()
            if now - self.last_json > 2.0 and now - self.last_nudge > 3.0:
                self.last_nudge = now
                print("[serial] board is in text mode, switching it back to JSON", flush=True)
                self.send("j")
            self.hub.publish({"type": "text", "line": line})
            return
        self.last_json = time.time()
        if not isinstance(obj, dict):
            return
        kind = obj.get("type")
        if kind == "hello":
            self.recorder.meta["fw"] = obj.get("fw", "unknown")
        elif kind == "series":
            obj["file"] = self.recorder.series(obj)
        elif kind == "report":
            obj["file"] = self.recorder.report(obj)
        self.hub.publish(obj)


class TcpLink(threading.Thread):
    """Same protocol over the network, so the board needs no cable to the PC."""

    def __init__(self, host, port, hub, recorder):
        super().__init__(daemon=True)
        self.host, self.tcp_port = host, port
        self.port_name = "%s:%d" % (host, port)
        self.hub, self.recorder = hub, recorder
        self.sock = None
        self.connected = False
        self.last_detail = None
        self.last_json = 0.0
        self.last_nudge = 0.0
        self.stop_flag = threading.Event()
        self.write_lock = threading.Lock()

    def send(self, key):
        with self.write_lock:
            if self.sock is None:
                return False
            try:
                self.sock.sendall(key.encode("ascii"))
                return True
            except Exception:
                return False

    def _announce(self, connected, detail=""):
        if connected != self.connected or detail != self.last_detail:
            print("[net] %s %s" % (self.port_name,
                  "open" if connected else "not open: " + (detail or "unknown")), flush=True)
        self.connected, self.last_detail = connected, detail
        self.hub.publish({"type": "link", "connected": connected,
                          "port": self.port_name, "detail": detail})

    _process_line = None   # bound below

    def run(self):
        import socket
        while not self.stop_flag.is_set():
            try:
                self.sock = socket.create_connection((self.host, self.tcp_port), timeout=5)
                self.sock.settimeout(1.0)
                self._announce(True)
                self.last_json = time.time()
                self.send("j")
                time.sleep(0.25)
                self.send("p")
                buf = b""
                last_byte = time.time()
                while not self.stop_flag.is_set():
                    try:
                        chunk = self.sock.recv(1024)
                        if not chunk:
                            raise OSError("closed by board")
                    except socket.timeout:
                        chunk = b""
                    if chunk:
                        last_byte = time.time()
                        buf += chunk
                        while b"\n" in buf:
                            raw, buf = buf.split(b"\n", 1)
                            SerialLink._process_line(self, raw.decode("utf-8", "replace"))
                    elif time.time() - last_byte > 8.0:
                        raise OSError("board silent")
            except Exception as exc:
                self._announce(False, str(exc))
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None
                time.sleep(2.0)


class FakeLink(threading.Thread):
    """Replays a plausible session so the screen can be worked on without hardware."""

    def __init__(self, hub, recorder):
        super().__init__(daemon=True)
        self.hub = hub
        self.recorder = recorder
        self.connected = True
        self.light = "blue"
        self.gain = "60x"
        self.cmds = queue.Queue()
        self.results = {}

    def send(self, key):
        self.cmds.put(key)
        return True

    def _live(self):
        base = {"C": 1067, "R": 12, "G": 276, "B": 828, "PT-A": 2286.0, "PT-B": 142.0}
        vals = {k: v * random.uniform(0.97, 1.03) for k, v in base.items()}
        self.hub.publish({"type": "live", "t": int(time.time() * 1000),
                          "c": vals["C"], "r": vals["R"], "g": vals["G"], "b": vals["B"],
                          "pta": vals["PT-A"], "ptb": vals["PT-B"], "sat": 0,
                          "light": self.light, "gain": self.gain})

    def _run(self, target):
        white = target == "white"
        peak = {"C": 1067.7 if white else 224.1, "R": 12.0 if white else 3.3,
                "G": 275.8 if white else 62.8, "B": 827.9 if white else 168.4,
                "PT-A": 2286.3 if white else 451.0, "PT-B": 142.0}
        self.hub.publish({"type": "run", "target": target, "light": self.light,
                          "gain": self.gain, "samples": 50})
        on, off = {}, {}
        for led in (1, 0):
            acc = {ch: [] for ch in CHANNELS}
            for n in range(50):
                s = {}
                for ch in CHANNELS:
                    base = peak[ch] if led else (142.0 if ch.startswith("PT") else 0.0)
                    s[ch] = max(0.0, base * random.uniform(0.985, 1.015)) if base else 0.0
                    acc[ch].append(s[ch])
                self.hub.publish({"type": "sample", "target": target, "led": led, "n": n,
                                  "c": s["C"], "r": s["R"], "g": s["G"], "b": s["B"],
                                  "pta": s["PT-A"], "ptb": s["PT-B"]})
                time.sleep(0.06)
            for ch in CHANNELS:
                xs = acc[ch]
                m = sum(xs) / len(xs)
                sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
                (on if led else off)[ch] = [round(m, 2), round(sd, 2)]
        obj = {"type": "series", "target": target, "light": self.light, "gain": self.gain,
               "samples": 50, "saturated": 0, "on": on, "off": off,
               "signal": {ch: round(on[ch][0] - off[ch][0], 2) for ch in CHANNELS},
               "noise": {ch: round((on[ch][1] ** 2 + off[ch][1] ** 2) ** 0.5, 2) for ch in CHANNELS}}
        self.results[target] = obj
        obj["file"] = self.recorder.series(obj)
        self.hub.publish(obj)

    def _report(self):
        if "white" not in self.results or "yellow" not in self.results:
            self.hub.publish({"type": "report", "empty": 1})
            return
        w, y = self.results["white"], self.results["yellow"]
        rows, best, best_snr = [], "none", 0.0
        for ch in CHANNELS:
            sw, sy = w["signal"][ch], y["signal"][ch]
            noise = (w["noise"][ch] ** 2 + y["noise"][ch] ** 2) ** 0.5
            snr = abs(sw - sy) / noise if noise > 0 else 0.0
            if snr > best_snr:
                best_snr, best = snr, ch
            rows.append({"ch": ch, "unit": UNITS[ch], "white": sw, "yellow": sy,
                         "contrast": (sw - sy) / sw if sw else 0.0,
                         "noise": round(noise, 2), "snr": round(snr, 2),
                         "go": 1 if snr >= 10 else 0})
        obj = {"type": "report", "light": self.light, "saturated": 0, "channels": rows,
               "best": best, "best_snr": round(best_snr, 2), "go": 1 if best_snr >= 10 else 0}
        obj["file"] = self.recorder.report(obj)
        self.hub.publish(obj)

    def run(self):
        self.recorder.meta["fw"] = "probe-0.2-sim"
        self.hub.publish({"type": "link", "connected": True, "port": "simulated", "detail": ""})
        self.hub.publish({"type": "hello", "fw": "probe-0.2-sim", "tcs": 1, "oled": 1,
                          "light": self.light, "gain": self.gain, "samples": 50})
        gains = ["1x", "4x", "16x", "60x"]
        while True:
            try:
                key = self.cmds.get(timeout=0.4)
            except queue.Empty:
                self._live()
                continue
            if key == "w":
                self._run("white")
            elif key == "y":
                self._run("yellow")
            elif key == "r":
                self._report()
            elif key in ("i", "g", "l", "c", "j", "p"):
                if key == "i":
                    self.light = "white" if self.light == "blue" else "blue"
                if key == "g":
                    self.gain = gains[(gains.index(self.gain) + 1) % 4]
                if key == "c":
                    self.results.clear()
                self.hub.publish({"type": "ack", "cmd": key, "light": self.light,
                                  "gain": self.gain, "live": 1})


# ---------------------------------------------------------------- http

def make_handler(hub, link, recorder):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def handle_one_request(self):
            # a browser dropping a keep alive or event stream connection is
            # normal, not an error worth a traceback in the operator console
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

        def _file(self, name, ctype):
            path = os.path.join(STATIC, name)
            if not os.path.isfile(path):
                self._send(404, "not found")
                return
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._file("index.html", "text/html; charset=utf-8")
            elif self.path == "/static/cyb3rgun_logo.svg":
                self._file("cyb3rgun_logo.svg", "image/svg+xml")
            elif self.path == "/events":
                self._events()
            else:
                self._send(404, "not found")

        def _chunk(self, text):
            # HTTP/1.1 needs an explicit framing. Without chunked encoding the
            # browser buffers the whole event stream and shows nothing.
            body = text.encode("utf-8")
            self.wfile.write(b"%X\r\n" % len(body) + body + b"\r\n")
            self.wfile.flush()

        def _events(self):
            q = hub.subscribe()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            first = {"type": "link", "connected": bool(getattr(link, "connected", False)),
                     "port": getattr(link, "port_name", "simulated"), "detail": ""}
            try:
                self._chunk("retry: 2000\n\n")
                self._chunk("data: %s\n\n" % json.dumps(first))
                if hub.last_state:
                    self._chunk("data: %s\n\n" % json.dumps(dict(hub.last_state, type="hello")))
                link.send("p")
                while True:
                    try:
                        self._chunk("data: %s\n\n" % q.get(timeout=10))
                    except queue.Empty:
                        self._chunk(": keepalive\n\n")
            except Exception:
                pass
            finally:
                hub.unsubscribe(q)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                body = {}
            if self.path == "/cmd":
                key = (body.get("key") or "")[:1]
                ok = link.send(key) if key in "wyrigljcpkmn" else False
                self._send(200, json.dumps({"ok": bool(ok)}), "application/json")
            elif self.path == "/meta":
                for field in ("aperture", "note", "operator", "label"):
                    if field in body:
                        recorder.meta[field] = str(body[field])[:120]
                self._send(200, json.dumps({"ok": True, "meta": recorder.meta}), "application/json")
            elif self.path == "/shot":
                path, err = recorder.screenshot()
                self._send(200, json.dumps({"ok": path is not None,
                                            "path": os.path.basename(path) if path else None,
                                            "error": err}), "application/json")
            else:
                self._send(404, "not found")

    return Handler


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return
        ThreadingHTTPServer.handle_error(self, request, client_address)


# ---------------------------------------------------------------- main

def list_ports():
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        print("pyserial is not installed. Try: pip3 install pyserial")
        return 1
    found = list(lp.comports())
    if not found:
        print("no serial ports found")
        return 1
    for p in found:
        print("%-20s %s" % (p.device, p.description))
    return 0


def default_port():
    if sys.platform.startswith("win"):
        return "COM6"
    for cand in ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0"):
        if os.path.exists(cand):
            return cand
    return "/dev/ttyUSB0"


def main():
    ap = argparse.ArgumentParser(description="HALO LAB measurement front end")
    ap.add_argument("--port", default=None, help="serial port of the Heltec board")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from another machine")
    ap.add_argument("--http-port", type=int, default=8760)
    ap.add_argument("--data-dir", default=os.path.join(REPO, "docs", "log", "data"))
    ap.add_argument("--image-dir", default=os.path.join(REPO, "docs", "log", "images"))
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    ap.add_argument("--tcp", default=None, metavar="HOST[:PORT]",
                    help="talk to the board over WiFi instead of USB, e.g. 192.168.1.50")
    ap.add_argument("--simulate", action="store_true", help="run without hardware")
    args = ap.parse_args()

    if args.list:
        sys.exit(list_ports())

    hub = Hub()
    recorder = Recorder(args.data_dir, args.image_dir)

    if args.simulate:
        link = FakeLink(hub, recorder)
    elif args.tcp:
        host, _, port = args.tcp.partition(":")
        link = TcpLink(host, int(port or 3333), hub, recorder)
    else:
        try:
            import serial  # noqa: F401
        except ImportError:
            print("pyserial is not installed. Try: pip3 install pyserial")
            print("or run with --simulate to see the screen without hardware")
            sys.exit(1)
        link = SerialLink(args.port or default_port(), args.baud, hub, recorder)
    link.start()

    server = QuietServer((args.host, args.http_port), make_handler(hub, link, recorder))
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    print("HALO LAB")
    print("  board  : %s" % ("simulated" if args.simulate else link.port_name))
    print("  data   : %s" % args.data_dir)
    print("  open   : http://%s:%d" % (shown, args.http_port))
    print("  stop   : Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
