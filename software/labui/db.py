"""
Storage for HALO LAB.

One SQLite file holds every gauge that was ever measured, every measurement
campaign, and every raw series and report. Nothing here computes anything: the
numbers come from the probe, this only keeps them and hands them back.

  gauges    a physical instrument: maker, model, dial size, range, sweep
  sessions  one campaign on one gauge, with its optics and its step size
  series    one finished measurement, raw firmware object plus metadata
  reports   one contrast and SNR evaluation

Only the standard library is used, sqlite3 ships with Python.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS gauges (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  manufacturer  TEXT NOT NULL DEFAULT '',
  model         TEXT NOT NULL DEFAULT '',
  dial_mm       REAL NOT NULL DEFAULT 20.0,
  range_min     REAL NOT NULL DEFAULT 0.0,
  range_max     REAL NOT NULL DEFAULT 40.0,
  unit          TEXT NOT NULL DEFAULT 'MPa',
  sweep_deg     REAL NOT NULL DEFAULT 180.0,
  needle_colour TEXT NOT NULL DEFAULT '#FCB803',
  dial_colour   TEXT NOT NULL DEFAULT '#F1EFE8',
  notes         TEXT NOT NULL DEFAULT '',
  created       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  gauge_id   INTEGER REFERENCES gauges(id) ON DELETE SET NULL,
  title      TEXT NOT NULL DEFAULT '',
  sensor     TEXT NOT NULL DEFAULT '',
  aperture   TEXT NOT NULL DEFAULT 'none',
  scale      TEXT NOT NULL DEFAULT '1:1',
  point_min  REAL,
  point_max  REAL,
  point_step REAL NOT NULL DEFAULT 1.0,
  unit       TEXT NOT NULL DEFAULT '',
  notes      TEXT NOT NULL DEFAULT '',
  created    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS series (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
  label      TEXT NOT NULL DEFAULT '',
  target     TEXT NOT NULL DEFAULT '',
  light      TEXT NOT NULL DEFAULT '',
  gain       TEXT NOT NULL DEFAULT '',
  aperture   TEXT NOT NULL DEFAULT '',
  samples    INTEGER NOT NULL DEFAULT 0,
  saturated  INTEGER NOT NULL DEFAULT 0,
  stem       TEXT NOT NULL DEFAULT '',
  payload    TEXT NOT NULL,
  created    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
  light      TEXT NOT NULL DEFAULT '',
  best       TEXT NOT NULL DEFAULT '',
  best_snr   REAL NOT NULL DEFAULT 0,
  go         INTEGER NOT NULL DEFAULT 0,
  stem       TEXT NOT NULL DEFAULT '',
  payload    TEXT NOT NULL,
  created    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_series_session  ON series(session_id);
CREATE INDEX IF NOT EXISTS ix_reports_session ON reports(session_id);
"""

GAUGE_FIELDS = ["manufacturer", "model", "dial_mm", "range_min", "range_max", "unit",
                "sweep_deg", "needle_colour", "dial_colour", "notes"]
SESSION_FIELDS = ["gauge_id", "title", "sensor", "aperture", "scale",
                  "point_min", "point_max", "point_step", "unit", "notes"]


def _now():
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        with self.lock:
            self.db.executescript(SCHEMA)
            # databases made before the campaign unit existed get the column now
            cols = [r[1] for r in self.db.execute("PRAGMA table_info(sessions)")]
            if "unit" not in cols:
                self.db.execute("ALTER TABLE sessions ADD COLUMN unit TEXT NOT NULL DEFAULT ''")
            self.db.commit()
        if not self.gauges():
            self.add_gauge({"manufacturer": "Huben", "model": "GK1", "dial_mm": 20.0,
                            "range_min": 0, "range_max": 40, "unit": "MPa",
                            "sweep_deg": 180.0,
                            "notes": "reference gauge of the halo-gauge-experiment"})

    # ---------------------------------------------------------------- helpers
    def _rows(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def _one(self, sql, args=()):
        rows = self._rows(sql, args)
        return rows[0] if rows else None

    def _write(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.lastrowid, cur.rowcount

    @staticmethod
    def _pick(data, fields):
        return {k: data[k] for k in fields if k in data}

    # ---------------------------------------------------------------- gauges
    def gauges(self):
        return self._rows("SELECT * FROM gauges ORDER BY manufacturer, model")

    def gauge(self, gid):
        return self._one("SELECT * FROM gauges WHERE id=?", (gid,))

    def add_gauge(self, data):
        d = self._pick(data, GAUGE_FIELDS)
        cols = list(d) + ["created"]
        vals = list(d.values()) + [_now()]
        gid, _ = self._write("INSERT INTO gauges (%s) VALUES (%s)" %
                             (",".join(cols), ",".join("?" * len(cols))), vals)
        return self.gauge(gid)

    def update_gauge(self, gid, data):
        d = self._pick(data, GAUGE_FIELDS)
        if not d:
            return self.gauge(gid)
        self._write("UPDATE gauges SET %s WHERE id=?" % ",".join(k + "=?" for k in d),
                    list(d.values()) + [gid])
        return self.gauge(gid)

    def delete_gauge(self, gid):
        _, n = self._write("DELETE FROM gauges WHERE id=?", (gid,))
        return n > 0

    # -------------------------------------------------------------- sessions
    def sessions(self):
        return self._rows("""
            SELECT s.*, s.unit AS s_unit, g.manufacturer, g.model, g.unit AS g_unit, g.range_min AS g_min,
                   g.range_max AS g_max, g.dial_mm, g.sweep_deg,
                   (SELECT COUNT(*) FROM series WHERE session_id=s.id) AS n_series
            FROM sessions s LEFT JOIN gauges g ON g.id = s.gauge_id
            ORDER BY s.id DESC""")

    def session(self, sid):
        rows = [s for s in self.sessions() if s["id"] == sid]
        return rows[0] if rows else None

    def add_session(self, data):
        d = self._pick(data, SESSION_FIELDS)
        cols = list(d) + ["created"]
        vals = list(d.values()) + [_now()]
        sid, _ = self._write("INSERT INTO sessions (%s) VALUES (%s)" %
                             (",".join(cols), ",".join("?" * len(cols))), vals)
        return self.session(sid)

    def update_session(self, sid, data):
        d = self._pick(data, SESSION_FIELDS)
        if d:
            self._write("UPDATE sessions SET %s WHERE id=?" % ",".join(k + "=?" for k in d),
                        list(d.values()) + [sid])
        return self.session(sid)

    def delete_session(self, sid):
        _, n = self._write("DELETE FROM sessions WHERE id=?", (sid,))
        return n > 0

    # ------------------------------------------------------- measurement plan
    def points(self, sid):
        """The list of needle positions this session is supposed to walk through.

        Derived from the session range and step, falling back to the range of
        the gauge itself. Each point carries the label used in file names and
        whether it has been measured already.
        """
        s = self.session(sid)
        if not s:
            return []
        lo = s["point_min"] if s["point_min"] is not None else s.get("g_min")
        hi = s["point_max"] if s["point_max"] is not None else s.get("g_max")
        step = s["point_step"] or 1.0
        if lo is None or hi is None or step <= 0 or hi < lo:
            return []
        # a campaign can run in degrees of rotor travel instead of pressure,
        # which is what the turning head does
        unit = (s.get("s_unit") or "").strip() or (s.get("g_unit") or "")
        decimals = 0 if abs(step - round(step)) < 1e-9 else (1 if abs(step * 10 - round(step * 10)) < 1e-9 else 2)
        measured = {r["label"] for r in
                    self._rows("SELECT DISTINCT label FROM series WHERE session_id=?", (sid,))}
        out, v, i = [], lo, 0
        while v <= hi + 1e-9 and i < 400:
            label = ("%%.%df %%s" % decimals) % (v, unit) if unit else ("%%.%df" % decimals) % v
            out.append({"value": round(v, 6), "label": label.strip(),
                        "done": label.strip() in measured})
            v += step
            i += 1
        return out

    # ---------------------------------------------------------------- results
    def add_series(self, sid, obj, stem):
        self._write("""INSERT INTO series
            (session_id,label,target,light,gain,aperture,samples,saturated,stem,payload,created)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, obj.get("label") or obj.get("target", ""), obj.get("target", ""),
                     obj.get("light", ""), obj.get("gain", ""), obj.get("aperture", ""),
                     obj.get("samples", 0), 1 if obj.get("saturated") else 0,
                     stem, json.dumps(obj), _now()))

    def add_report(self, sid, obj, stem):
        self._write("""INSERT INTO reports
            (session_id,light,best,best_snr,go,stem,payload,created)
            VALUES (?,?,?,?,?,?,?,?)""",
                    (sid, obj.get("light", ""), obj.get("best", ""),
                     obj.get("best_snr", 0), 1 if obj.get("go") else 0,
                     stem, json.dumps(obj), _now()))

    def series_of(self, sid):
        return self._rows("""SELECT id,label,target,light,gain,aperture,samples,saturated,stem,created
                             FROM series WHERE session_id=? ORDER BY id""", (sid,))

    def curve(self, sid):
        """Every measured point of a campaign, reduced to what a curve needs:
        the numeric part of the label and the signal of each channel."""
        out = []
        for r in self._rows("SELECT label,target,payload FROM series WHERE session_id=? ORDER BY id",
                            (sid,)):
            try:
                p = json.loads(r["payload"])
            except Exception:
                continue
            num = None
            for tok in (r["label"] or "").replace(",", ".").split():
                try:
                    num = float(tok); break
                except ValueError:
                    continue
            on, off = p.get("on", {}), p.get("off", {})
            row = {"label": r["label"], "x": num, "target": r["target"]}
            for ch in ("C", "R", "G", "B", "PT-A", "PT-B"):
                a = on.get(ch) or [0, 0]
                b = off.get(ch) or [0, 0]
                row[ch] = {"on": a[0], "sd": a[1] if len(a) > 1 else 0,
                           "signal": a[0] - b[0]}
            out.append(row)
        out.sort(key=lambda r: (r["x"] is None, r["x"]))
        return out

    def reports_of(self, sid):
        return self._rows("""SELECT id,light,best,best_snr,go,stem,created
                             FROM reports WHERE session_id=? ORDER BY id""", (sid,))

    def delete_series(self, rid):
        _, n = self._write("DELETE FROM series WHERE id=?", (rid,))
        return n > 0

    def full_series(self, rid):
        row = self._one("SELECT * FROM series WHERE id=?", (rid,))
        if row:
            row["payload"] = json.loads(row["payload"])
        return row

    # ----------------------------------------------------------------- export
    def export(self, sid):
        s = self.session(sid)
        if not s:
            return None
        return {"session": s, "gauge": self.gauge(s["gauge_id"]) if s["gauge_id"] else None,
                "points": self.points(sid),
                "series": [self.full_series(r["id"]) for r in self.series_of(sid)],
                "reports": [dict(r, payload=json.loads(
                    self._one("SELECT payload FROM reports WHERE id=?", (r["id"],))["payload"]))
                    for r in self.reports_of(sid)]}
