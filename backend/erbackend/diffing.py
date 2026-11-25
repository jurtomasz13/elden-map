"""Migawka slotu (Snap) i diff dwóch migawek — wspólne dla SSE 'save' i kroniki w bazie."""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import asdict, dataclass, field

from .flags import FlagMap
from .gamedata import GameData
from .savefile import SaveFile

MAX_FLAGS_IN_EVENT = 500


@dataclass
class Snap:
    """Stan postaci z jednego zapisu save'a (wszystko, czego potrzeba do diffu i historii)."""
    file: str
    slot: int
    name: str
    level: int
    playtime_s: int
    runes_memory: int
    deaths: int
    map_id: str
    position: dict
    regions: list[int]
    bloodstain: dict | None
    md5: str
    ts: float                       # mtime pliku (epoch, s)
    flags: bytes = field(repr=False, default=b"")

    def info(self) -> dict:
        d = asdict(self)
        d.pop("flags")
        return d

    @classmethod
    def from_info(cls, info: dict, flags: bytes) -> "Snap":
        return cls(**info, flags=flags)


def snap_from(sf: SaveFile, slot: int) -> Snap:
    c = sf.character(slot)
    s = sf.slot(slot)
    return Snap(file=sf.kind, slot=slot, name=c.name, level=c.level, playtime_s=c.playtime_s,
                runes_memory=c.runes_memory, deaths=s.deaths, map_id=s.position["map_id"],
                position=s.position, regions=s.regions, bloodstain=s.bloodstain, md5=s.md5,
                ts=sf.mtime_ns / 1e9, flags=s.flags)


def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return dt.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="milliseconds")


def area_of(map_id: str | None) -> str | None:
    """Obszar do zdarzenia 'zmiana mapy': świat otwarty m60/m61 jako całość, reszta 'mAA_BB'."""
    if not map_id:
        return None
    parts = map_id.split("_")
    if parts[0] in ("m60", "m61"):
        return parts[0]
    return "_".join(parts[:2])


def bloodstain_moved(a: dict | None, b: dict | None) -> bool:
    if b is None:
        return False
    if a is None:
        return True
    if a["map_id"] != b["map_id"]:
        return True
    return math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"])) > 0.05


def char_brief(s: Snap) -> dict:
    return {"slot": s.slot, "name": s.name, "level": s.level, "playtime_s": s.playtime_s,
            "runes_memory": s.runes_memory, "deaths": s.deaths}


def build_diff(old: Snap | None, new: Snap, fm: FlagMap, index: dict) -> dict:
    """Zdarzenie SSE 'save' dla jednego slotu (kształt w docs/07)."""
    ev = {"file": new.file, "slot": new.slot, "written_at": iso(new.ts),
          "character": char_brief(new), "position": new.position, "bloodstain": new.bloodstain,
          "new_character": False,
          "changed_flags": [], "changed_flags_total": 0, "truncated": False,
          "completed": {"bosses": [], "graces": [], "items": [], "quest_steps": []},
          "reverted": {"bosses": [], "graces": [], "items": [], "quest_steps": []},
          "deaths_delta": 0, "level_delta": 0, "regions_added": [],
          "map_changed": None}
    if old is None or old.name != new.name:
        ev["new_character"] = True
        return ev
    diffs = fm.diff(old.flags, new.flags)
    ev["changed_flags_total"] = len(diffs)
    ev["truncated"] = len(diffs) > MAX_FLAGS_IN_EVENT
    ev["changed_flags"] = [{"id": fid, "value": val} for fid, val, _, _ in diffs[:MAX_FLAGS_IN_EVENT]]
    ev["deaths_delta"] = new.deaths - old.deaths
    ev["level_delta"] = new.level - old.level
    old_regions = set(old.regions)
    ev["regions_added"] = [r for r in new.regions if r not in old_regions]
    if area_of(old.map_id) != area_of(new.map_id):
        ev["map_changed"] = {"from": old.map_id, "to": new.map_id}
    seen = set()
    get_new = lambda f: fm.get(new.flags, f)  # noqa: E731
    get_old = lambda f: fm.get(old.flags, f)  # noqa: E731
    for fid, val, _, _ in diffs:
        for kind, entry, step in index.get(fid, ()):
            if kind == "quests":
                key = (kind, entry["id"], step.get("id"), step["text"])
                if key in seen:
                    continue
                seen.add(key)
                now, before = GameData.step_done(step, get_new), GameData.step_done(step, get_old)
                if now != before:
                    (ev["completed"] if now else ev["reverted"])["quest_steps"].append(
                        {"quest_id": entry["id"], "quest": entry["name"], "step_id": step.get("id"),
                         "text": step["text"]})
                continue
            key = (kind, entry["id"])
            if key in seen:
                continue
            seen.add(key)
            (ev["completed"] if val else ev["reverted"])[kind].append(
                {"id": entry["id"], "name": entry["name"], "flag": fid})
    return ev
