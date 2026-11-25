"""Warstwa danych (backend/data/*.json) i liczenie statusów z bloku flag."""
from __future__ import annotations

import json
import os
from typing import Callable

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
KINDS = ("bosses", "graces", "items", "quests")

FlagGetter = Callable[[int], "bool | None"]


def boss_defeated(b: dict, get) -> bool:
    """Pokonany: flaga główna albo dodatkowa (np. bossowie dużej mapy zapisują śmierć pod flagą 12…)."""
    return any(bool(get(f)) for f in [b["defeat_flag"], *b.get("extra_defeat_flags", [])])


class GameData:
    def __init__(self, sets: dict[str, dict]):
        self.sets = sets                         # kind -> {"_meta": ..., "entries": [...]}
        self._last_grace_idx: dict[int, dict] | None = None

    @classmethod
    def load(cls, data_dir: str = DATA_DIR) -> "GameData":
        sets = {}
        for kind in KINDS:
            path = os.path.join(data_dir, f"{kind}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    sets[kind] = json.load(f)
            else:
                sets[kind] = {"_meta": {"kind": kind, "schema_version": 1}, "entries": []}
        return cls(sets)

    def entries(self, kind: str) -> list[dict]:
        return self.sets[kind]["entries"]

    def by_id(self, kind: str) -> dict[str, dict]:
        return {e["id"]: e for e in self.entries(kind)}

    # --- statusy ----------------------------------------------------------------------------
    @staticmethod
    def step_done(step: dict, get: FlagGetter) -> bool:
        flags = step.get("flags") or []
        if not flags:
            return False
        vals = [bool(get(f)) for f in flags]
        return any(vals) if step.get("mode") == "any" else all(vals)

    def grace_by_last_grace(self) -> dict[int, dict]:
        """Wartość `last_rested_grace` z save'a (= encja łaski + 1000) -> wpis łaski."""
        if self._last_grace_idx is None:
            self._last_grace_idx = {g["last_grace_id"]: g for g in self.entries("graces") if g.get("last_grace_id")}
        return self._last_grace_idx

    @staticmethod
    def _entry_maps(entry: dict) -> list[str]:
        return list(entry.get("map_ids") or ([entry["map_id"]] if entry.get("map_id") else []))

    @staticmethod
    def _discovery(entry: dict, done: bool, done_reason: str, get: FlagGetter, visited_graces: set[str],
                   visited_areas: set[str], visited_maps: set[str], default_areas: list[str],
                   grace_maps: frozenset = frozenset()) -> tuple[bool, str | None]:
        """Czy gracz 'wie' o tym wpisie (tryb bez spoilerów). Zwraca (discovered, powód)."""
        if done:
            return True, done_reason
        d = entry.get("discover") or {}
        for f in d.get("flags", []):
            if get(f):
                return True, "flag"
        for f in entry.get("alt_flags", []):           # np. boss pokonany w poprzednim cyklu NG
            if get(f):
                return True, "alt_flag"
        if any(g in visited_graces for g in d.get("graces", [])):
            return True, "nearby_grace"
        own_maps = GameData._entry_maps(entry)
        if any(m in grace_maps for m in own_maps):          # odwiedzona łaska na tej samej mapie / kaflu
            return True, "nearby_grace"
        areas = d.get("areas", default_areas)
        if any(a and a in visited_areas for a in areas):
            return True, "area_grace"
        maps = list(d.get("maps", [])) + own_maps
        arena = entry.get("arena") or {}
        if arena.get("map_id"):
            maps.append(arena["map_id"])
        if any(m in visited_maps for m in maps):
            return True, "map_visited"
        return False, None

    def evaluate(self, get: FlagGetter, visited_maps: set[str] | None = None,
                 attempts: dict[str, int | None] | None = None) -> dict:
        """Zwraca listy bosses/graces/items/quests w kształcie API + progress + warnings."""
        visited_maps = visited_maps or set()
        attempts = attempts or {}
        graces_raw = self.entries("graces")
        visited = {g["id"]: bool(get(g["flag"])) for g in graces_raw}
        visited_graces = {gid for gid, v in visited.items() if v}
        visited_areas = set()
        for g in graces_raw:
            if visited[g["id"]]:
                visited_areas.update(x for x in (g.get("area"), g.get("subregion")) if x)
        visited_area_only = {g.get("area") for g in graces_raw if visited[g["id"]]}
        grace_maps = frozenset(g["map_id"] for g in graces_raw if visited[g["id"]] and g.get("map_id"))

        bosses = []
        for b in self.entries("bosses"):
            defeated = boss_defeated(b, get)
            disc, why = self._discovery(b, defeated, "defeated", get, visited_graces, visited_areas, visited_maps,
                                        [b.get("subregion") or b.get("region")], grace_maps)
            bosses.append({"id": b["id"], "name": b["name"], "region": b.get("region"), "subregion": b.get("subregion"),
                           "location": b.get("location"),
                           "defeated": defeated, "dlc": b.get("dlc", False), "required": b.get("required"),
                           "hints": b.get("hints"), "confidence": b.get("confidence"),
                           "discovered": disc, "discovered_by": why, "attempts": attempts.get(b["id"]),
                           "flag": b["defeat_flag"], "name_en": b.get("name_en"), "region_pl": b.get("region_pl"),
                           "map_id": b.get("map_id"), "runes": b.get("runes")})
        graces = []
        for g in graces_raw:
            disc, why = self._discovery(g, visited[g["id"]], "visited", get, visited_graces, visited_area_only,
                                        visited_maps, [g.get("subregion") or g.get("area")], grace_maps)
            graces.append({"id": g["id"], "name": g["name"], "region": g.get("region"), "subregion": g.get("subregion"),
                           "area": g.get("area"),
                           "visited": visited[g["id"]], "dlc": g.get("dlc", False),
                           "discovered": disc, "discovered_by": why,
                           "flag": g["flag"], "name_en": g.get("name_en"), "map_id": g.get("map_id")})
        items = []
        for i in self.entries("items"):
            got = bool(get(i["flag"]))
            # przedmioty: tylko reguły mapowe (podregion całej krainy zdradzałby za dużo skarbów naraz)
            disc, why = self._discovery(i, got, "collected", get, visited_graces, visited_areas, visited_maps,
                                        [], grace_maps)
            items.append({"id": i["id"], "name": i["name"], "category": i.get("category"), "collected": got,
                          "dlc": i.get("dlc", False), "location": i.get("location"),
                          "region": i.get("region"), "subregion": i.get("subregion"),
                          "discovered": disc, "discovered_by": why,
                          "flag": i["flag"], "kind": i.get("kind"), "map_id": i.get("map_id")})

        boss_state = {b["id"]: b for b in bosses}
        quests, warnings = [], []
        for q in self.entries("quests"):
            raw = q.get("steps", [])
            steps = [{"id": s.get("id"), "text": s["text"], "done": self.step_done(s, get), "where": s.get("where")}
                     for s in raw]
            completed = bool(steps) and all(s["done"] for s in steps)
            # "co dalej" = podpowiedź pierwszego niezaliczonego kroku
            next_hint = next(((src.get("next") or src["text"]) for st, src in zip(steps, raw) if not st["done"]), None)
            done_by_id = {s["id"]: s["done"] for s in steps if s["id"]}
            disc, why = self._discovery(q, any(s["done"] for s in steps), "started", get, visited_graces,
                                        visited_areas, visited_maps, [q.get("region")] if q.get("region") else [],
                                        grace_maps)
            nxt_raw = next((src for st, src in zip(steps, raw) if not st["done"]), None)
            quests.append({"id": q["id"], "name": q["name"], "npc": q.get("npc"), "dlc": q.get("dlc", False),
                           "steps": steps, "completed": completed, "next": next_hint,
                           "next_where": nxt_raw.get("where") if nxt_raw else None,
                           "region": q.get("region"), "icon": q.get("icon"), "missable": q.get("missable"),
                           "confidence": q.get("confidence"),
                           "discovered": disc, "discovered_by": why})
            if completed:
                continue
            for lock in q.get("locks", []):
                boss = boss_state.get(lock.get("boss_id"))
                if boss is None or boss["defeated"]:
                    continue
                if lock.get("step") and done_by_id.get(lock["step"]):
                    continue        # krok, który trzeba zrobić przed bossem, już zaliczony
                warnings.append({"quest_id": q["id"], "quest": q["name"], "npc": q.get("npc"),
                                 "boss_id": boss["id"], "boss": boss["name"], "step_id": lock.get("step"),
                                 "warning": lock.get("warning"),
                                 "warning_safe": lock.get("warning_safe")})

        def count(lst, key):
            return {"done": sum(1 for x in lst if x[key]), "total": len(lst)}

        progress = {"bosses": count(bosses, "defeated"), "graces": count(graces, "visited"),
                    "items": count(items, "collected"), "quests": count(quests, "completed")}

        def split(lst, key):
            return {"base": count([x for x in lst if not x["dlc"]], key), "dlc": count([x for x in lst if x["dlc"]], key)}

        cats: dict[str, dict] = {}
        for i in items:
            c = cats.setdefault(i["category"] or "other", {"done": 0, "total": 0})
            c["total"] += 1
            c["done"] += i["collected"]
        progress_detail = {
            "bosses": split(bosses, "defeated"),
            "bosses_required": count([b for b in bosses if b["required"]], "defeated"),
            "graces": split(graces, "visited"),
            "items": split(items, "collected"),
            "map_treasures": count([i for i in items if i["kind"] == "map_lot"], "collected"),
            "items_by_category": dict(sorted(cats.items())),
            "quests": split(quests, "completed"),
        }
        return {"bosses": bosses, "graces": graces, "items": items, "quests": quests, "progress": progress,
                "progress_detail": progress_detail, "warnings": warnings}

    # --- diff -------------------------------------------------------------------------------
    def flag_index(self) -> dict[int, list[tuple[str, dict, dict | None]]]:
        """flag_id -> [(kind, wpis, krok_questa|None)] — do opisywania zmian w diffie."""
        idx: dict[int, list] = {}
        for b in self.entries("bosses"):
            for f in [b["defeat_flag"], *b.get("extra_defeat_flags", [])]:
                idx.setdefault(f, []).append(("bosses", b, None))
        for g in self.entries("graces"):
            idx.setdefault(g["flag"], []).append(("graces", g, None))
        for i in self.entries("items"):
            idx.setdefault(i["flag"], []).append(("items", i, None))
        for q in self.entries("quests"):
            for s in q.get("steps", []):
                for f in s.get("flags") or []:
                    idx.setdefault(f, []).append(("quests", q, s))
        return idx
