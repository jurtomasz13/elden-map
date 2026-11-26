"""Historia (SQLite): kronika, śmierci, próby na bossa, sesje, trwałość po restarcie; discovered i ostrzeżenia."""
import dataclasses
import datetime as dt
import os
import sqlite3
import shutil
import tempfile
import unittest

from helpers import assert_not_game_dir, copy_saves, source_save_dir

from erbackend.diffing import item_key, snap_from
from erbackend.flags import FlagMap
from erbackend.gamedata import GameData
from erbackend.history import History, adopt_old_db
from erbackend.savefile import SaveFile


def with_flags(snap, fm, values: dict[int, bool], **changes):
    """Kopia migawki z ustawionymi flagami i innymi polami (np. ts, level, deaths, bloodstain)."""
    flags = bytearray(snap.flags)
    for fid, val in values.items():
        b, bit = fm.location(fid)
        flags[b] = flags[b] | (1 << bit) if val else flags[b] & ~(1 << bit) & 0xFF
    md5 = changes.pop("md5", None) or f"{snap.md5}-{len(values)}-{changes.get('ts', snap.ts)}"
    return dataclasses.replace(snap, flags=bytes(flags), md5=md5, **changes)


@unittest.skipIf(source_save_dir() is None, "brak save'ów (ustaw ER_SAVE_DIR)")
class HistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = copy_saves()
        cls.fm = FlagMap.load()
        cls.gd = GameData.load()
        cls.index = cls.gd.flag_index()
        path = next(os.path.join(cls.tmp, f) for f in ("ER0000.co2", "ER0000.sl2")
                    if os.path.exists(os.path.join(cls.tmp, f)))
        sf = SaveFile.read(path)
        # postać bez pokonanych bossów DLC (najlepiej najsłabsza)
        slot = min(sf.active_slots, key=lambda i: sf.character(i).level)
        cls.base = snap_from(sf, slot)
        cls.boss = next(b for b in cls.gd.entries("bosses")
                        if b.get("arena") and not cls.fm.get(cls.base.flags, b["defeat_flag"]))
        cls.grace = next(g for g in cls.gd.entries("graces") if not cls.fm.get(cls.base.flags, g["flag"]))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.dbdir = tempfile.mkdtemp(prefix="er-history-test-")
        assert_not_game_dir(self.dbdir)
        self.h = History(os.path.join(self.dbdir, "history.sqlite"))

    def tearDown(self):
        self.h.close()
        shutil.rmtree(self.dbdir, ignore_errors=True)

    def ch(self):
        return {"file": self.base.file, "slot": self.base.slot, "name": self.base.name}

    def cid(self):
        return self.h.character_id(self.base.file, self.base.slot, self.base.name)

    def test_baseline_then_events(self):
        r = self.h.observe(self.base, self.fm, self.index)
        self.assertTrue(r["baseline"])
        self.assertEqual(r["events"], [])
        self.assertTrue(r["diff"]["new_character"])
        # ten sam zapis jeszcze raz -> nic
        self.assertFalse(self.h.observe(self.base, self.fm, self.index)["changed"])
        t = self.base.ts
        s2 = with_flags(self.base, self.fm, {self.boss["defeat_flag"]: True, self.grace["flag"]: True},
                        ts=t + 60, level=self.base.level + 2, map_id="m41_02_00_00",
                        position={**self.base.position, "map_id": "m41_02_00_00"})
        r = self.h.observe(s2, self.fm, self.index)
        kinds = {e["kind"] for e in r["events"]}             # flaga bossa bywa też krokiem questa
        self.assertLessEqual({"boss_defeated", "grace_discovered", "level_up", "map_changed"}, kinds)
        self.assertLessEqual(kinds, {"boss_defeated", "grace_discovered", "level_up", "map_changed", "quest_step"})

        lvl = next(e for e in r["events"] if e["kind"] == "level_up")
        self.assertEqual(lvl["data"], {"from": self.base.level, "to": self.base.level + 2})
        chron = self.h.chronicle(self.cid(), self.ch(), limit=10)
        self.assertEqual(len(chron), len(r["events"]))
        self.assertGreater(chron[0]["id"], chron[-1]["id"])            # najnowsze najpierw
        self.assertEqual(self.h.chronicle(self.cid(), self.ch(), kinds=["boss_defeated"])[0]["ref_id"],
                         self.boss["id"])

    def test_open_world_tile_change_is_not_map_change(self):
        self.h.observe(dataclasses.replace(self.base, map_id="m60_42_36_00"), self.fm, self.index)
        s2 = with_flags(self.base, self.fm, {}, ts=self.base.ts + 60, map_id="m60_43_36_00")
        r = self.h.observe(s2, self.fm, self.index)
        self.assertEqual([e for e in r["events"] if e["kind"] == "map_changed"], [])

    def test_deaths_and_attempts(self):
        a = self.boss["arena"]
        arena = a["map_id"]
        ax, ay, az = (a.get("x") or 0.0), (a.get("y") or 0.0), (a.get("z") or 0.0)
        t = self.base.ts
        base = dataclasses.replace(self.base, deaths=10, bloodstain=None)
        self.h.observe(base, self.fm, self.index)

        def bs(m, dx, x0=ax, y0=ay, z0=az):
            return {"map_id": m, "x": x0 + dx, "y": y0, "z": z0, "global": None, "runes": 100}

        s1 = with_flags(base, self.fm, {}, ts=t + 60, deaths=11, bloodstain=bs(arena, 5.0))
        s2 = with_flags(base, self.fm, {}, ts=t + 120, deaths=12, bloodstain=bs(arena, 9.0))
        s3 = with_flags(base, self.fm, {}, ts=t + 180, deaths=13, bloodstain=bs("m60_42_36_00", 1.0))
        s4 = with_flags(base, self.fm, {}, ts=t + 240, deaths=13, bloodstain=bs("m60_42_36_00", 1.0))  # bez zmian
        steps = [s1, s2, s3, s4]
        if a.get("radius"):                         # ta sama mapa, ale poza promieniem areny — nie liczy się
            steps.append(with_flags(base, self.fm, {}, ts=t + 250, deaths=14,
                                    bloodstain=bs(arena, a["radius"] + 500.0)))
        for s in steps:
            self.h.observe(s, self.fm, self.index)
        d = self.h.deaths(self.cid(), self.ch())
        self.assertEqual([x["deaths_total"] for x in d][-3:], [13, 12, 11])
        bosses = self.gd.entries("bosses")
        att = self.h.boss_attempts(self.cid(), bosses, {})
        self.assertEqual(att[self.boss["id"]], 2)
        self.assertIsNone(next(v for k, v in att.items() if not next(b for b in bosses if b["id"] == k).get("arena")))
        # boss pada, potem kolejna śmierć na arenie się nie liczy
        s5 = with_flags(base, self.fm, {self.boss["defeat_flag"]: True}, ts=t + 300, deaths=14,
                        bloodstain=bs("m60_42_36_00", 1.0))
        s6 = with_flags(s5, self.fm, {}, ts=t + 360, deaths=15, bloodstain=bs(arena, 3.0))
        self.h.observe(s5, self.fm, self.index)
        self.h.observe(s6, self.fm, self.index)
        att = self.h.boss_attempts(self.cid(), bosses, {self.boss["id"]: True})
        self.assertEqual(att[self.boss["id"]], 2)

    def test_attempts_across_open_world_tiles(self):
        """Arena na kaflu m60_42_36, śmierć tuż za granicą kafla (m60_43_36) — liczona przez współrzędne świata."""
        from erbackend.worldmap import WorldMap
        wm = WorldMap.load()
        boss = {"id": "b", "arena": {"map_id": "m60_42_36_00", "x": 125.0, "y": 0.0, "z": 0.0, "radius": 60.0}}
        base = dataclasses.replace(self.base, deaths=0, bloodstain=None)
        self.h.observe(base, self.fm, self.index)
        near = {"map_id": "m60_43_36_00", "x": -125.0, "y": 0.0, "z": 0.0, "global": None, "runes": None}   # 6 m dalej
        far = {"map_id": "m60_44_36_00", "x": 0.0, "y": 0.0, "z": 0.0, "global": None, "runes": None}
        self.h.observe(with_flags(base, self.fm, {}, ts=base.ts + 60, deaths=1, bloodstain=near), self.fm, self.index)
        self.h.observe(with_flags(base, self.fm, {}, ts=base.ts + 120, deaths=2, bloodstain=far), self.fm, self.index)
        self.assertEqual(self.h.boss_attempts(self.cid(), [boss], {}, wm)["b"], 1)
        self.assertEqual(self.h.boss_attempts(self.cid(), [boss], {}, None)["b"], 0)   # bez mapy świata: tylko ta sama mapa

    def test_death_without_new_bloodstain(self):
        base = dataclasses.replace(self.base, deaths=5, bloodstain=None)
        self.h.observe(base, self.fm, self.index)
        self.h.observe(with_flags(base, self.fm, {}, ts=base.ts + 30, deaths=7), self.fm, self.index)
        d = self.h.deaths(self.cid(), self.ch())
        self.assertEqual((d[0]["delta"], d[0]["position"]), (2, None))

    def test_session(self):
        t = self.base.ts
        base = dataclasses.replace(self.base, deaths=0, level=10, playtime_s=1000, runes_memory=0)
        self.h.observe(base, self.fm, self.index)                               # poprzednia sesja
        a = with_flags(base, self.fm, {self.grace["flag"]: True}, ts=t + 3600, playtime_s=1100, deaths=1,
                       runes_memory=500)
        b = with_flags(a, self.fm, {self.boss["defeat_flag"]: True}, ts=t + 3660, playtime_s=1160, level=11,
                       deaths=3, runes_memory=900)
        self.h.observe(a, self.fm, self.index)
        self.h.observe(b, self.fm, self.index)
        s = self.h.session(self.cid(), self.ch(), now=t + 3700)
        self.assertTrue(s["active"])
        self.assertEqual(s["saves"], 2)
        self.assertEqual(s["wall_duration_s"], 60)
        self.assertEqual(s["playtime_s"], 160)
        self.assertEqual(s["deaths"], 3)
        self.assertEqual(s["levels"], {"from": 10, "to": 11, "gained": 1})
        self.assertEqual(s["runes_gained"], 900)
        self.assertEqual([x["id"] for x in s["bosses"]], [self.boss["id"]])
        self.assertEqual([x["id"] for x in s["graces"]], [self.grace["id"]])
        self.assertFalse(self.h.session(self.cid(), self.ch(), now=t + 3660 + 601)["active"])

    def test_items_obtained(self):
        # nowy przedmiot bez flagi (kupiony, z przeciwnika, wytworzony) -> „zdobyty”; ze skarbu ma już „item_collected”
        treasure = next(i for i in self.gd.entries("items")
                        if i.get("contents") and not self.fm.get(self.base.flags, i["flag"]))
        from_treasure = item_key(treasure["contents"][0]["cat"], treasure["contents"][0]["id"])
        base = dataclasses.replace(self.base, items=["goods:100"])
        self.h.observe(base, self.fm, self.index)
        s2 = with_flags(base, self.fm, {treasure["flag"]: True}, ts=self.base.ts + 60,
                        items=["goods:100", "talisman:1000", from_treasure])
        r = self.h.observe(s2, self.fm, self.index)
        self.assertEqual([e["ref_id"] for e in r["events"] if e["kind"] == "item_obtained"], ["talisman:1000"])
        self.assertIn(treasure["id"], [e["ref_id"] for e in r["events"] if e["kind"] == "item_collected"])

    def test_items_unknown_before_give_no_events(self):
        # migawka sprzed spisu przedmiotów (starsza baza): cały ekwipunek nie może trafić do kroniki jako „zdobyty”
        self.h.observe(dataclasses.replace(self.base, items=None), self.fm, self.index)
        s2 = with_flags(self.base, self.fm, {}, ts=self.base.ts + 60, items=["goods:100", "talisman:1000"])
        self.assertEqual([e for e in self.h.observe(s2, self.fm, self.index)["events"] if e["kind"] == "item_obtained"], [])

    def test_days(self):
        # dzień kroniki trwa od 4:00 do 4:00: zapis o 3:00 należy jeszcze do poprzedniego dnia
        at = lambda d, h: dt.datetime(2026, 11, d, h, 0).timestamp()          # noqa: E731
        base = dataclasses.replace(self.base, ts=at(20, 12), level=50, deaths=5, playtime_s=1000, runes_memory=100)
        self.h.observe(base, self.fm, self.index)
        evening = with_flags(base, self.fm, {self.grace["flag"]: True}, ts=at(20, 23), level=51, deaths=7,
                             playtime_s=2000, runes_memory=300)
        night = with_flags(evening, self.fm, {}, ts=at(21, 3), level=52, deaths=8, playtime_s=3000, runes_memory=400)
        morning = with_flags(night, self.fm, {}, ts=at(21, 10), level=53, playtime_s=4000, runes_memory=50)
        for s in (evening, night, morning):
            self.h.observe(s, self.fm, self.index)
        r = self.h.days(self.cid(), self.ch(), 7)
        self.assertEqual([d["date"] for d in r["days"]], ["2026-11-21", "2026-11-20"])
        today, yesterday = r["days"]
        self.assertEqual((yesterday["playtime_s"], yesterday["deaths"], yesterday["levels"]["to"]), (2000, 3, 52))
        self.assertEqual([g["id"] for g in yesterday["graces"]], [self.grace["id"]])
        self.assertEqual((today["playtime_s"], today["deaths"], today["levels"]), (1000, 0, {"from": 52, "to": 53, "gained": 1}))
        self.assertEqual(today["runes_gained"], -350)
        older = self.h.days(self.cid(), self.ch(), 7, before=dt.date(2026, 11, 21))
        self.assertEqual([d["date"] for d in older["days"]], ["2026-11-20"])
        self.assertTrue(self.h.days(self.cid(), self.ch(), 1)["more"])

    def test_adopt_old_db(self):
        # baza z folderu programu (do 0.1.6) przechodzi do folderu użytkownika; stary plik zostaje
        old, new = os.path.join(self.dbdir, "old.sqlite"), os.path.join(self.dbdir, "user", "history.sqlite")
        con = sqlite3.connect(old)
        con.execute("CREATE TABLE t(x)")
        con.execute("INSERT INTO t VALUES (7)")
        con.commit()
        con.close()
        self.assertTrue(adopt_old_db(new, old))
        con = sqlite3.connect(new)
        self.assertEqual(con.execute("SELECT x FROM t").fetchone()[0], 7)
        con.close()
        self.assertTrue(os.path.exists(old))
        self.assertFalse(adopt_old_db(new, old))                              # nowa baza już jest: bez zmian

    def test_persistence_across_restart(self):
        self.h.observe(self.base, self.fm, self.index)
        self.h.close()
        self.h = History(os.path.join(self.dbdir, "history.sqlite"))
        self.assertFalse(self.h.observe(self.base, self.fm, self.index)["changed"])
        s2 = with_flags(self.base, self.fm, {self.grace["flag"]: True}, ts=self.base.ts + 10)
        r = self.h.observe(s2, self.fm, self.index)
        self.assertEqual([e["ref_id"] for e in r["events"]], [self.grace["id"]])

    def test_new_character_in_same_slot(self):
        self.h.observe(self.base, self.fm, self.index)
        other = dataclasses.replace(self.base, name=self.base.name + "_2", md5="x")
        r = self.h.observe(other, self.fm, self.index)
        self.assertTrue(r["baseline"])


class DiscoveryAndWarningsTest(unittest.TestCase):
    def setUp(self):
        self.gd = GameData({
            "bosses": {"_meta": {}, "entries": [
                {"id": "b1", "name": "Boss 1", "region": "Area A", "defeat_flag": 100, "alt_flags": [101]},
                {"id": "b2", "name": "Boss 2", "region": "Area B", "defeat_flag": 200, "alt_flags": [],
                 "arena": {"map_id": "m41_02_00_00"}},
                {"id": "b3", "name": "Boss 3", "region": "Area C", "defeat_flag": 300, "alt_flags": [],
                 "discover": {"flags": [301]}}]},
            "graces": {"_meta": {}, "entries": [
                {"id": "g1", "name": "G1", "region": "R", "area": "Area A", "flag": 10},
                {"id": "g2", "name": "G2", "region": "R", "area": "Area A", "flag": 11},
                {"id": "g3", "name": "G3", "region": "R", "area": "Area B", "flag": 12}]},
            "items": {"_meta": {}, "entries": [{"id": "i1", "name": "I1", "flag": 50}]},
            "quests": {"_meta": {}, "entries": [
                {"id": "q1", "name": "Quest", "npc": "NPC",
                 "steps": [{"id": "s1", "text": "pogadaj", "flags": [60]}, {"id": "s2", "text": "koniec", "flags": [61]}],
                 "locks": [{"boss_id": "b1", "step": "s2", "warning": "Najpierw skończ quest"},
                           {"boss_id": "b2", "warning": "Zabicie bossa przerywa quest"}]}]},
        })

    def ev(self, on, maps=()):
        return self.gd.evaluate(lambda f: f in on, visited_maps=set(maps))

    def test_discovered(self):
        r = self.ev({10})
        b = {x["id"]: x for x in r["bosses"]}
        g = {x["id"]: x for x in r["graces"]}
        self.assertEqual((b["b1"]["discovered"], b["b1"]["discovered_by"]), (True, "area_grace"))
        self.assertFalse(b["b2"]["discovered"])
        self.assertEqual(g["g2"]["discovered_by"], "area_grace")
        self.assertFalse(g["g3"]["discovered"])
        self.assertFalse(r["items"][0]["discovered"])
        self.assertEqual(self.ev(set(), maps=["m41_02_00_00"])["bosses"][1]["discovered_by"], "map_visited")
        self.assertEqual(self.ev({101})["bosses"][0]["discovered_by"], "alt_flag")
        self.assertEqual(self.ev({301})["bosses"][2]["discovered_by"], "flag")
        self.assertEqual(self.ev({200})["bosses"][1]["discovered_by"], "defeated")
        self.assertTrue(self.ev({50})["items"][0]["discovered"])

    def test_warnings(self):
        w = self.ev(set())["warnings"]
        self.assertEqual(sorted(x["boss_id"] for x in w), ["b1", "b2"])
        self.assertEqual(sorted(x["boss_id"] for x in self.ev({61})["warnings"]), ["b2"])   # krok s2 zrobiony
        self.assertEqual(self.ev({200})["warnings"][0]["boss_id"], "b1")                    # b2 już martwy
        self.assertEqual(self.ev({60, 61})["warnings"], [])                                 # quest skończony


if __name__ == "__main__":
    unittest.main()
