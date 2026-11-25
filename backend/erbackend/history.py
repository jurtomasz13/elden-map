"""Historia zapisów w SQLite (backend/var/history.sqlite): kronika, miejsca śmierci, sesje.

Postać = (plik sl2/co2, slot, imię). Dla każdej postaci trzymamy ostatnią migawkę (flagi skompresowane
zlib), więc po restarcie serwera diff liczy się względem stanu z bazy — zmiany zrobione, gdy serwer
nie działał, też trafią do kroniki (z czasem zapisu pliku).
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
import time
import zlib

from .diffing import Snap, area_of, bloodstain_moved, build_diff, iso
from .worldmap import inside_shape

DEFAULT_DB = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "var",
                                           "history.sqlite"))
SESSION_GAP_S = 600
ARENA_MARGIN = 3.0       # m — plama krwi tuż przy granicy areny (mgła, ściana) też się liczy

SCHEMA = """
CREATE TABLE IF NOT EXISTS characters(
    id INTEGER PRIMARY KEY, file TEXT NOT NULL, slot INTEGER NOT NULL, name TEXT NOT NULL,
    first_seen REAL NOT NULL, UNIQUE(file, slot, name));
CREATE TABLE IF NOT EXISTS last_state(
    character_id INTEGER PRIMARY KEY REFERENCES characters(id), md5 TEXT NOT NULL, ts REAL NOT NULL,
    info TEXT NOT NULL, flags BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(
    id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL REFERENCES characters(id), ts REAL NOT NULL,
    observed REAL NOT NULL, md5 TEXT, level INTEGER, deaths INTEGER, playtime_s INTEGER,
    runes_memory INTEGER, map_id TEXT, x REAL, y REAL, z REAL, baseline INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS snapshots_char_ts ON snapshots(character_id, ts);
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL REFERENCES characters(id), ts REAL NOT NULL,
    kind TEXT NOT NULL, ref_id TEXT, name TEXT, data TEXT);
CREATE INDEX IF NOT EXISTS events_char ON events(character_id, id);
CREATE TABLE IF NOT EXISTS deaths(
    id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL REFERENCES characters(id), ts REAL NOT NULL,
    deaths_total INTEGER, delta INTEGER, map_id TEXT, x REAL, y REAL, z REAL, runes INTEGER,
    baseline INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS deaths_char ON deaths(character_id, ts);
"""

EVENT_KINDS = {"bosses": "boss_defeated", "graces": "grace_discovered", "items": "item_collected"}


class History:
    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            if path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)

    def close(self):
        with self.lock:
            self.db.close()

    # --- postacie ----------------------------------------------------------------------------
    def character_id(self, file: str, slot: int, name: str, create: bool = False) -> int | None:
        with self.lock:
            row = self.db.execute("SELECT id FROM characters WHERE file=? AND slot=? AND name=?",
                                  (file, slot, name)).fetchone()
            if row:
                return row["id"]
            if not create:
                return None
            return self.db.execute("INSERT INTO characters(file, slot, name, first_seen) VALUES(?,?,?,?)",
                                   (file, slot, name, time.time())).lastrowid

    def last_snap(self, cid: int) -> Snap | None:
        row = self.db.execute("SELECT info, flags FROM last_state WHERE character_id=?", (cid,)).fetchone()
        if not row:
            return None
        return Snap.from_info(json.loads(row["info"]), zlib.decompress(row["flags"]))

    # --- zapis obserwacji ---------------------------------------------------------------------
    def observe(self, new: Snap, fm, index: dict) -> dict:
        """Rejestruje migawkę. Zwraca {"diff", "events", "deaths", "baseline", "changed"}."""
        with self.lock:
            cid = self.character_id(new.file, new.slot, new.name, create=True)
            old = self.last_snap(cid)
            if old is not None and old.md5 == new.md5:
                return {"diff": None, "events": [], "deaths": [], "baseline": False, "changed": False}
            diff = build_diff(old, new, fm, index)
            observed = time.time()
            ch = {"file": new.file, "slot": new.slot, "name": new.name}
            events, deaths = [], []
            cur = self.db.cursor()
            cur.execute("BEGIN")
            try:
                cur.execute("INSERT INTO snapshots(character_id, ts, observed, md5, level, deaths, playtime_s,"
                            " runes_memory, map_id, x, y, z, baseline) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (cid, new.ts, observed, new.md5, new.level, new.deaths, new.playtime_s,
                             new.runes_memory, new.map_id, new.position["x"], new.position["y"],
                             new.position["z"], int(old is None)))
                if old is None:
                    if new.bloodstain:   # ostatnia plama krwi sprzed obserwacji — czas nieznany
                        deaths.append(self._add_death(cur, cid, ch, new.ts, new.deaths, 0, new.bloodstain, True))
                else:
                    for group, kind in EVENT_KINDS.items():
                        for e in diff["completed"][group]:
                            events.append(self._add_event(cur, cid, ch, new.ts, kind, e["id"], e["name"],
                                                          {"flag": e["flag"]}))
                    for st in diff["completed"]["quest_steps"]:
                        events.append(self._add_event(cur, cid, ch, new.ts, "quest_step", st["quest_id"],
                                                      st["quest"], {"step_id": st["step_id"], "text": st["text"]}))
                    if new.level > old.level:
                        events.append(self._add_event(cur, cid, ch, new.ts, "level_up", None, f"Poziom {new.level}",
                                                      {"from": old.level, "to": new.level}))
                    if diff["map_changed"]:
                        events.append(self._add_event(cur, cid, ch, new.ts, "map_changed", new.map_id, new.map_id,
                                                      {"from": old.map_id, "to": new.map_id,
                                                       "from_area": area_of(old.map_id),
                                                       "to_area": area_of(new.map_id)}))
                    delta = new.deaths - old.deaths
                    moved = bloodstain_moved(old.bloodstain, new.bloodstain)
                    if delta > 0 or moved:
                        deaths.append(self._add_death(cur, cid, ch, new.ts, new.deaths, max(delta, 1),
                                                      new.bloodstain if moved else None, False))
                cur.execute("INSERT OR REPLACE INTO last_state(character_id, md5, ts, info, flags) VALUES(?,?,?,?,?)",
                            (cid, new.md5, new.ts, json.dumps(new.info()), zlib.compress(new.flags, 1)))
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
            return {"diff": diff, "events": events, "deaths": deaths, "baseline": old is None, "changed": True}

    def _add_event(self, cur, cid, ch, ts, kind, ref_id, name, data) -> dict:
        eid = cur.execute("INSERT INTO events(character_id, ts, kind, ref_id, name, data) VALUES(?,?,?,?,?,?)",
                          (cid, ts, kind, ref_id, name, json.dumps(data, ensure_ascii=False))).lastrowid
        return {"id": eid, "ts": iso(ts), "kind": kind, "ref_id": ref_id, "name": name, "data": data,
                "character": ch}

    def _add_death(self, cur, cid, ch, ts, total, delta, bs, baseline) -> dict:
        bs = bs or {}
        did = cur.execute("INSERT INTO deaths(character_id, ts, deaths_total, delta, map_id, x, y, z, runes, baseline)"
                          " VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (cid, ts, total, delta, bs.get("map_id"), bs.get("x"), bs.get("y"), bs.get("z"),
                           bs.get("runes"), int(baseline))).lastrowid
        return self._death_dict({"id": did, "ts": ts, "deaths_total": total, "delta": delta,
                                 "map_id": bs.get("map_id"), "x": bs.get("x"), "y": bs.get("y"), "z": bs.get("z"),
                                 "runes": bs.get("runes"), "baseline": int(baseline)}, ch)

    # --- odczyt ------------------------------------------------------------------------------
    @staticmethod
    def _event_dict(r, ch) -> dict:
        return {"id": r["id"], "ts": iso(r["ts"]), "kind": r["kind"], "ref_id": r["ref_id"],
                "name": r["name"], "data": json.loads(r["data"]) if r["data"] else None, "character": ch}

    @staticmethod
    def _death_dict(r, ch) -> dict:
        r = dict(r)
        pos = None
        if r["map_id"]:
            pos = {"map_id": r["map_id"], "x": r["x"], "y": r["y"], "z": r["z"]}
        return {"id": r["id"], "ts": iso(r["ts"]), "deaths_total": r["deaths_total"], "delta": r["delta"],
                "position": pos, "runes": r["runes"], "baseline": bool(r["baseline"]), "character": ch}

    def chronicle(self, cid: int, ch: dict, limit: int = 100, before_id: int | None = None,
                  kinds: list[str] | None = None) -> list[dict]:
        q = "SELECT * FROM events WHERE character_id=?"
        args: list = [cid]
        if before_id:
            q += " AND id<?"
            args.append(before_id)
        if kinds:
            q += f" AND kind IN ({','.join('?' * len(kinds))})"
            args += kinds
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.lock:
            return [self._event_dict(r, ch) for r in self.db.execute(q, args)]

    def deaths(self, cid: int, ch: dict, limit: int | None = None) -> list[dict]:
        q = "SELECT * FROM deaths WHERE character_id=? ORDER BY ts DESC, id DESC"
        args: list = [cid]
        if limit:
            q += " LIMIT ?"
            args.append(limit)
        with self.lock:
            return [self._death_dict(r, ch) for r in self.db.execute(q, args)]

    def visited_maps(self, cid: int) -> set[str]:
        with self.lock:
            maps = {r[0] for r in self.db.execute("SELECT DISTINCT map_id FROM snapshots WHERE character_id=?", (cid,))}
            maps |= {r[0] for r in self.db.execute("SELECT DISTINCT map_id FROM deaths WHERE character_id=?", (cid,))}
        maps.discard(None)
        return maps

    def defeat_times(self, cid: int) -> dict[str, float]:
        with self.lock:
            return {r["ref_id"]: r["ts"] for r in self.db.execute(
                "SELECT ref_id, MAX(ts) AS ts FROM events WHERE character_id=? AND kind='boss_defeated' GROUP BY ref_id",
                (cid,))}

    def boss_attempts(self, cid: int, bosses: list[dict], defeated: dict[str, bool],
                      worldmap=None) -> dict[str, int | None]:
        """Próby = zarejestrowane śmierci z plamą krwi na arenie bossa, zanim padł.

        Arena z danych: `arena = {map_id, x, y, z, radius}` (gdy x/radius = null — liczy się cała mapa).
        Odległość liczona lokalnie na tej samej mapie, a w otwartym świecie (m60/m61) przez współrzędne świata,
        więc śmierć na sąsiednim kaflu też się liczy (`worldmap.distance`).
        None, gdy boss nie ma areny albo padł, zanim zaczęliśmy obserwować postać (czas pokonania nieznany).
        """
        out: dict[str, int | None] = {}
        with self.lock:
            rows = [dict(r) for r in self.db.execute(
                "SELECT ts, map_id, x, y, z FROM deaths WHERE character_id=? AND baseline=0 AND map_id IS NOT NULL",
                (cid,))]
        killed_at = self.defeat_times(cid)
        for b in bosses:
            arena = b.get("arena")
            if not arena or not arena.get("map_id"):
                out[b["id"]] = None
                continue
            limit = None
            if defeated.get(b["id"]):
                limit = killed_at.get(b["id"])
                if limit is None:
                    out[b["id"]] = None
                    continue
            n = 0
            for r in rows:
                if limit is not None and r["ts"] > limit:
                    continue
                if arena.get("region"):             # granice areny z pliku mapy (obszar przyzywania ducha)
                    pa = (r["x"], r["y"], r["z"])
                    if worldmap is not None:
                        pa = worldmap.to_frame(r["map_id"], pa, arena["map_id"])
                    elif r["map_id"] != arena["map_id"]:
                        pa = None
                    if pa is None or not inside_shape(arena["region"], pa, ARENA_MARGIN):
                        continue
                elif arena.get("x") is not None and arena.get("radius"):
                    pa, pb = (r["x"], r["y"], r["z"]), (arena["x"], arena["y"], arena["z"])
                    if worldmap is not None:
                        d = worldmap.distance(r["map_id"], pa, arena["map_id"], pb)
                    else:
                        d = math.dist(pa, pb) if r["map_id"] == arena["map_id"] else None
                    if d is None or d > arena["radius"]:
                        continue
                elif r["map_id"] != arena["map_id"]:
                    continue
                n += 1
            out[b["id"]] = n
        return out

    def session(self, cid: int, ch: dict, now: float | None = None, gap: float = SESSION_GAP_S) -> dict | None:
        """Bieżąca lub ostatnia sesja: ciąg zapisów bez przerwy dłuższej niż `gap` sekund."""
        now = time.time() if now is None else now
        with self.lock:
            snaps = [dict(r) for r in self.db.execute(
                "SELECT * FROM snapshots WHERE character_id=? ORDER BY ts, id", (cid,))]
            if not snaps:
                return None
            i = len(snaps) - 1
            while i > 0 and snaps[i]["ts"] - snaps[i - 1]["ts"] <= gap:
                i -= 1
            group = snaps[i:]
            base = snaps[i - 1] if i > 0 else group[0]
            start, end = group[0]["ts"], group[-1]["ts"]
            evs = [self._event_dict(r, ch) for r in self.db.execute(
                "SELECT * FROM events WHERE character_id=? AND ts>=? AND ts<=? ORDER BY id", (cid, start, end))]
            dts = [self._death_dict(r, ch) for r in self.db.execute(
                "SELECT * FROM deaths WHERE character_id=? AND baseline=0 AND ts>=? AND ts<=? ORDER BY ts, id",
                (cid, start, end))]

        def pick(kind):
            return [{"id": e["ref_id"], "name": e["name"], "ts": e["ts"]} for e in evs if e["kind"] == kind]

        last = group[-1]
        return {
            "active": now - end <= gap,
            "started_at": iso(start), "ended_at": iso(end),
            "wall_duration_s": round(end - start, 1),
            "playtime_s": last["playtime_s"] - base["playtime_s"],
            "saves": len(group),
            "bosses": pick("boss_defeated"), "graces": pick("grace_discovered"), "items": pick("item_collected"),
            "quest_steps": [{"quest_id": e["ref_id"], "quest": e["name"], **(e["data"] or {}), "ts": e["ts"]}
                            for e in evs if e["kind"] == "quest_step"],
            "maps": [e["data"]["to"] for e in evs if e["kind"] == "map_changed"],
            "deaths": last["deaths"] - base["deaths"],
            "death_points": [d["position"] for d in dts if d["position"]],
            "levels": {"from": base["level"], "to": last["level"], "gained": last["level"] - base["level"]},
            "runes_gained": last["runes_memory"] - base["runes_memory"],
            "based_on_previous_save": i > 0,
        }
