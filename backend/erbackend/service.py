"""Serwis: cache save'ów, wybór aktywnego pliku/slotu, stan, historia (kronika/śmierci/sesje), watcher folderu."""
from __future__ import annotations

import datetime as dt
import logging
import os
import queue
import threading
import time

from .diffing import snap_from
from .flags import FlagMap
from .gamedata import GameData, boss_defeated
from .history import History
from .worldmap import WorldMap
from .savefile import FILE_KINDS, SaveError, SaveFile

log = logging.getLogger("erbackend")

DEFAULT_SAVE_ROOT = os.path.join(os.environ.get("APPDATA", ""), "EldenRing")


def _steam_libraries() -> list[str]:
    home = os.path.expanduser("~")
    steam = [os.path.join(home, ".steam", "steam"), os.path.join(home, ".local", "share", "Steam"),
             os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
             os.path.join(home, "snap", "steam", "common", ".local", "share", "Steam")]
    libs = list(steam)
    for s_ in steam:
        vdf = os.path.join(s_, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            import re
            libs += re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding="utf-8", errors="replace").read())
    return libs


def save_roots() -> list[str]:
    """Wszystkie katalogi „EldenRing” z save'ami: Windows %APPDATA%, a na Linuxie każdy prefiks Wine/Protona —
    także Seamless Coop dodany do Steama jako gra spoza Steama (własny compatdata/<numer>), Lutris, Heroic, Bottles."""
    import glob
    roots = [DEFAULT_SAVE_ROOT] if os.environ.get("APPDATA") else []
    home = os.path.expanduser("~")
    tail = os.path.join("drive_c", "users", "*", "AppData", "Roaming", "EldenRing")
    patterns = [os.path.join(lib, "steamapps", "compatdata", "*", "pfx", tail) for lib in _steam_libraries()]
    patterns += [os.path.join(home, ".wine", tail), os.path.join(home, "Games", "*", tail),
                 os.path.join(home, "Games", "Heroic", "Prefixes", "*", "*", tail),
                 os.path.join(home, ".local", "share", "bottles", "bottles", "*", tail),
                 os.path.join(home, ".var", "app", "com.usebottles.bottles", "data", "bottles", "bottles", "*", tail)]
    seen = set()
    for pat in patterns:
        for d in sorted(glob.glob(pat)):
            key = os.path.normcase(os.path.realpath(d))
            if key not in seen:
                seen.add(key)
                roots.append(d)
    return roots


def find_save_dirs(root: str | None = None) -> dict[str, str]:
    """Dla każdego rodzaju pliku (sl2 = gra, co2 = Seamless Coop) folder <EldenRing>/<SteamID64> z najświeższym plikiem.
    Pliki mogą leżeć w różnych prefiksach (np. Seamless Coop uruchamiany przez Proton jako osobna gra)."""
    if os.environ.get("ER_SAVE_DIR"):
        return {k: os.environ["ER_SAVE_DIR"] for k in FILE_KINDS}
    best: dict[str, tuple[int, str]] = {}
    for r in ([root] if root else save_roots()):
        try:
            names = os.listdir(r)
        except OSError:
            continue
        for name in names:
            d = os.path.join(r, name)
            if not (name.isdigit() and os.path.isdir(d)):
                continue
            for kind, fn in FILE_KINDS.items():
                try:
                    mt = os.stat(os.path.join(d, fn)).st_mtime_ns
                except OSError:
                    continue
                if mt > best.get(kind, (-1, ""))[0]:
                    best[kind] = (mt, d)
    return {k: d for k, (_mt, d) in best.items()}


def find_save_dir(root: str | None = None) -> str | None:
    """Folder z najświeższym plikiem save'a (dowolnego rodzaju)."""
    if os.environ.get("ER_SAVE_DIR"):
        return os.environ["ER_SAVE_DIR"]
    dirs = find_save_dirs(root)
    if not dirs:
        return None
    return max(dirs.values(), key=lambda d: max((os.stat(os.path.join(d, fn)).st_mtime_ns
                                                 for fn in FILE_KINDS.values() if os.path.exists(os.path.join(d, fn))), default=-1))


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


class Service:
    def __init__(self, save_dir: str, flagmap: FlagMap | None = None, gamedata: GameData | None = None,
                 history: History | None = None, poll_interval: float = 0.5, debounce: float = 0.4,
                 worldmap: WorldMap | None = None, save_dirs: dict[str, str] | None = None):
        self.save_dir = os.path.normpath(save_dir)
        # osobny folder dla każdego rodzaju pliku (np. .co2 Seamless Coop w innym prefiksie Protona niż .sl2)
        self.save_dirs = {k: os.path.normpath((save_dirs or {}).get(k) or save_dir) for k in FILE_KINDS}
        self.flagmap = flagmap or FlagMap.load()
        self.gamedata = gamedata or GameData.load()
        # domyślnie baza w pamięci (testy/skrypty); serwer podaje plik backend/var/history.sqlite
        self.history = history or History(":memory:")
        self.flag_index = self.gamedata.flag_index()
        # przeliczanie pozycji na mapę strony + nazwy regionów (backend/data/world_extras.json; bez pliku — puste)
        self.worldmap = worldmap or WorldMap.load()
        self.poll_interval = poll_interval
        self.debounce = debounce
        self.lock = threading.RLock()
        self.saves: dict[str, SaveFile] = {}           # "sl2"/"co2" -> SaveFile
        self.mtimes: dict[str, int] = {}
        self.errors: dict[str, str] = {}
        self.active: dict | None = None                # {"file", "slot", "reason", "since"}
        self.subscribers: set[queue.Queue] = set()
        self.listeners: list = []                      # fn(kind, slot, SaveFile) po zmianie slotu (np. portrety)
        self.event_id = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._initial_load()

    # --- wczytywanie -------------------------------------------------------------------------
    def path_for(self, kind: str) -> str:
        return os.path.join(self.save_dirs[kind], FILE_KINDS[kind])

    def _initial_load(self):
        for kind in FILE_KINDS:
            path = self.path_for(kind)
            if not os.path.exists(path):
                continue
            try:
                sf = SaveFile.read(path)
                self.saves[kind] = sf
                self.mtimes[kind] = sf.mtime_ns
            except (SaveError, OSError) as e:
                self.errors[kind] = str(e)
                log.warning("nie udało się wczytać %s: %s", path, e)
                continue
            # synchronizacja historii: zmiany zrobione, gdy serwer nie działał, trafią do kroniki
            for slot in sf.active_slots:
                try:
                    r = self.history.observe(snap_from(sf, slot), self.flagmap, self.flag_index)
                except SaveError as e:
                    log.warning("%s slot %d: %s", kind, slot, e)
                    continue
                if r["changed"] and not r["baseline"]:
                    log.info("%s slot %d: zmiany od ostatniego uruchomienia: %d zdarzeń kroniki",
                             kind, slot, len(r["events"]))
        if self.saves:
            # aktywny plik = ostatnio zmieniony; slot = ostatnio wczytany wg profilu
            kind = max(self.saves, key=lambda k: self.saves[k].mtime_ns)
            sf = self.saves[kind]
            if sf.last_slot is not None:
                self.active = {"file": kind, "slot": sf.last_slot, "reason": "profile_last_slot", "since": now_iso()}

    # --- stan --------------------------------------------------------------------------------
    def get_save(self, kind: str | None) -> SaveFile:
        with self.lock:
            if kind is None:
                if self.active:
                    kind = self.active["file"]
                elif self.saves:
                    kind = next(iter(self.saves))
            if kind not in self.saves:
                raise LookupError(f"brak pliku save '{kind}' (dostępne: {', '.join(self.saves) or 'brak'})")
            return self.saves[kind]

    def resolve(self, kind: str | None, slot: int | None) -> tuple[str, SaveFile, int]:
        with self.lock:
            if kind is None and slot is None and self.active:
                kind, slot = self.active["file"], self.active["slot"]
            sf = self.get_save(kind)
            kind = sf.kind
            if slot is None:
                if self.active and self.active["file"] == kind:
                    slot = self.active["slot"]
                else:
                    slot = sf.last_slot
            if slot is None or slot not in sf.active_slots:
                raise LookupError(f"slot {slot} w pliku {kind} jest pusty (zajęte: {sf.active_slots})")
            return kind, sf, slot

    def _character_key(self, kind, slot) -> tuple[SaveFile, dict, int | None]:
        kind, sf, slot = self.resolve(kind, slot)
        name = sf.character(slot).name
        cid = self.history.character_id(kind, slot, name)
        return sf, {"file": kind, "slot": slot, "name": name}, cid

    def characters(self) -> dict:
        with self.lock:
            files = []
            for kind in FILE_KINDS:
                sf = self.saves.get(kind)
                if sf is None:
                    if kind in self.errors:
                        files.append({"file": kind, "path": self.path_for(kind), "error": self.errors[kind]})
                    continue
                files.append({
                    "file": kind, "path": sf.path, "written_at": sf.written_at, "last_slot": sf.last_slot,
                    "characters": [char_dict(c) for c in sf.characters()],
                })
            return {"save_dir": self.save_dir, "save_dirs": self.save_dirs, "active": self.active, "files": files}

    def state(self, kind: str | None = None, slot: int | None = None, sections: list[str] | None = None,
              item_kinds: list[str] | None = None) -> dict:
        with self.lock:
            kind, sf, slot = self.resolve(kind, slot)
            active = self.active
        c = sf.character(slot)
        s = sf.slot(slot)
        get = lambda f: self.flagmap.get(s.flags, f)  # noqa: E731
        cid = self.history.character_id(kind, slot, c.name)
        maps = {s.position["map_id"], s.map_id} | (self.history.visited_maps(cid) if cid else set())
        if s.bloodstain:
            maps.add(s.bloodstain["map_id"])
        attempts = {}
        if cid:
            defeated = {b["id"]: boss_defeated(b, get) for b in self.gamedata.entries("bosses")}
            attempts = self.history.boss_attempts(cid, self.gamedata.entries("bosses"), defeated, self.worldmap)
        ev = self.gamedata.evaluate(get, visited_maps=maps, attempts=attempts)
        out = {
            "character": {
                "slot": slot, "name": c.name, "level": c.level, "playtime_s": c.playtime_s,
                "runes_memory": c.runes_memory, "deaths": s.deaths,
                "last_grace": last_grace_dict(s.last_grace, self.gamedata),
                **c.profile,
            },
            "position": self.with_map(s.position),
            "map_id": s.map_id,
            "bloodstain": self.with_map(s.bloodstain),
            "regions_unlocked": s.regions,
            "regions": [self.worldmap.region_name(r) for r in s.regions],
            "equipment": s.equipment,
            "stats": s.stats,
            "inventory": s.inventory,
            **ev,
            "save": {"file": sf.kind, "path": sf.path, "written_at": sf.written_at, "slot_md5": s.md5,
                     "is_active": bool(active and active["file"] == sf.kind and active["slot"] == slot)},
        }
        if item_kinds:                      # np. tylko popioły/osełki (acquired_flag) — skarbów z map jest ~3400
            out["items"] = [i for i in out["items"] if i.get("kind") in item_kinds]
        if sections:
            out = {k: v for k, v in out.items() if k in sections or k in ("character", "save")}
        return out

    def with_map(self, pos: dict | None) -> dict | None:
        """Dodaje `map: {map, px, py, approx}` — piksele mapy strony (jak px/py w assets/data)."""
        if not pos:
            return pos
        return {**pos, "map": self.worldmap.to_map(pos["map_id"], pos["x"], pos["y"], pos["z"])}

    def flags(self, ids: list[int], kind: str | None = None, slot: int | None = None) -> dict:
        with self.lock:
            kind, sf, slot = self.resolve(kind, slot)
        flags = sf.slot(slot).flags
        return {"file": kind, "slot": slot, "flags": {str(i): self.flagmap.get(flags, i) for i in ids}}

    # --- historia ----------------------------------------------------------------------------
    def chronicle(self, kind=None, slot=None, limit=100, before_id=None, kinds=None) -> dict:
        _, ch, cid = self._character_key(kind, slot)
        events = self.history.chronicle(cid, ch, limit, before_id, kinds) if cid else []
        return {"character": ch, "events": events,
                "next_before_id": events[-1]["id"] if len(events) == limit else None}

    def deaths(self, kind=None, slot=None, limit=None) -> dict:
        sf, ch, cid = self._character_key(kind, slot)
        rows = self.history.deaths(cid, ch, limit) if cid else []
        for d in rows:
            if d["position"]:
                d["position"] = self.with_map(d["position"])
        return {"character": ch, "deaths_total": sf.slot(ch["slot"]).deaths,
                "bloodstain": self.with_map(sf.slot(ch["slot"]).bloodstain),
                "recorded": sum(1 for d in rows if not d["baseline"]), "deaths": rows}

    def days(self, kind, slot, limit, before) -> dict:
        _, ch, cid = self._character_key(kind, slot)
        return {"character": ch, **(self.history.days(cid, ch, limit, before) if cid else {"days": [], "more": False})}

    def session(self, kind=None, slot=None) -> dict:
        _, ch, cid = self._character_key(kind, slot)
        return {"character": ch, "session": self.history.session(cid, ch) if cid else None,
                "gap_s": 600}

    # --- SSE ---------------------------------------------------------------------------------
    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        with self.lock:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self.lock:
            self.subscribers.discard(q)

    def publish(self, event: str, data: dict):
        with self.lock:
            self.event_id += 1
            msg = (self.event_id, event, data)
            subs = list(self.subscribers)
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:            # klient nie odbiera — wyrzucamy go
                self.unsubscribe(q)

    # --- watcher -----------------------------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, name="save-watcher", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        log.info("obserwuję %s (co %.1f s)", ", ".join(sorted(set(self.save_dirs.values()))), self.poll_interval)
        while not self._stop.wait(self.poll_interval):
            try:
                self.poll_once()
            except Exception:                         # watcher nie może umrzeć
                log.exception("błąd watchera")

    def _stat(self, kind: str) -> int | None:
        try:
            return os.stat(self.path_for(kind)).st_mtime_ns
        except OSError:
            return None

    def poll_once(self) -> list[dict]:
        """Jedno sprawdzenie folderu. Zwraca listę opublikowanych zdarzeń 'save'."""
        published = []
        for kind in FILE_KINDS:
            mt = self._stat(kind)
            if mt is None or mt == self.mtimes.get(kind):
                continue
            # debounce: czekamy aż mtime przestanie się zmieniać (gra robi kilka zapisów pod rząd)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if self._stop.wait(self.debounce):
                    return published
                mt2 = self._stat(kind)
                if mt2 == mt:
                    break
                mt = mt2
            try:
                sf = SaveFile.read(self.path_for(kind))
            except (SaveError, OSError) as e:
                log.warning("zmiana %s, ale odczyt się nie udał: %s", kind, e)
                self.errors[kind] = str(e)
                self.mtimes[kind] = mt                 # nie próbujemy w kółko; następny zapis gry nadpisze
                self.publish("error", {"file": kind, "error": str(e), "time": now_iso()})
                continue
            self.errors.pop(kind, None)
            published += self._apply(kind, sf)
        return published

    def _apply(self, kind: str, sf: SaveFile) -> list[dict]:
        with self.lock:
            old = self.saves.get(kind)
            self.saves[kind] = sf
            self.mtimes[kind] = sf.mtime_ns
            changed = [i for i in sf.active_slots
                       if old is None or i not in old.active_slots or old.slot_md5(i) != sf.slot_md5(i)]
            # aktywny = slot zmieniony w tym zapisie (przy kilku — ten z ostatnim wczytaniem w profilu)
            if changed:
                slot = sf.last_slot if sf.last_slot in changed else changed[0]
                self.active = {"file": kind, "slot": slot, "reason": "last_written", "since": now_iso()}
        events = []
        for i in changed:
            try:
                r = self.history.observe(snap_from(sf, i), self.flagmap, self.flag_index)
            except SaveError as e:
                log.warning("%s slot %d: %s", kind, i, e)
                continue
            if not r["changed"]:
                continue
            ev = r["diff"]
            ev["active"] = self.active
            events.append(ev)
            self.publish("save", ev)
            if r["events"] or r["deaths"]:
                self.publish("chronicle", {"character": {"file": kind, "slot": i, "name": ev["character"]["name"]},
                                           "events": r["events"], "deaths": r["deaths"]})
        for i in changed:
            for fn in self.listeners:
                try:
                    fn(kind, i, sf)
                except Exception:
                    log.exception("słuchacz zmian slotu")
        if not changed:
            self.publish("save", {"file": kind, "slot": None, "written_at": sf.written_at,
                                  "note": "plik zapisany, żaden slot się nie zmienił", "active": self.active})
        log.info("zapis %s, zmienione sloty: %s", kind, changed)
        return events


def last_grace_dict(raw: int, gd: GameData) -> dict:
    g = gd.grace_by_last_grace().get(raw)
    return {"entity_id": raw, "grace_id": g["id"] if g else None, "name": g["name"] if g else None,
            "map_id": g.get("map_id") if g else None}


def char_dict(c) -> dict:
    return {"slot": c.slot, "name": c.name, "level": c.level, "playtime_s": c.playtime_s,
            "runes_memory": c.runes_memory, "map_id": c.map_id}
