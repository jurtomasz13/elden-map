"""Przeliczanie pozycji (lokalne -> świat -> piksele mapy), nazwy regionów, krainy łask i bossów."""
import json
import os
import shutil
import unittest

from helpers import BACKEND, copy_saves, source_save_dir

from erbackend.gamedata import GameData
from erbackend.savefile import SaveFile
from erbackend.worldmap import WorldMap

ASSETS = os.path.join(BACKEND, "..", "assets", "data")
EXTRAS = os.path.join(BACKEND, "data", "world_extras.json")


def load(fn):
    with open(os.path.join(ASSETS, fn), encoding="utf-8") as f:
        return json.load(f)


@unittest.skipUnless(os.path.exists(EXTRAS), "brak backend/data/world_extras.json")
class WorldMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wm = WorldMap.load()

    def test_map_without_own_row_placed_by_row_leading_into_it(self):
        # Kaplica Oczekiwania (m10_01) ma tylko wiersz z zamku Burzowego Całunu do siebie: (-514, 28, 200) w m10_00 to jej (0, 0, 0)
        chapel = self.wm.to_map("m10_01_00_00", 10.0, 0.0, -5.0)
        castle = self.wm.to_map("m10_00_00_00", -504.0, 28.0, 195.0)
        self.assertIsNotNone(chapel)
        self.assertEqual(chapel, castle)

    def test_distance_same_map_and_across_tiles(self):
        self.assertAlmostEqual(self.wm.distance("m10_00_00_00", (0, 0, 0), "m10_00_00_00", (3, 4, 0)), 5.0)
        self.assertAlmostEqual(self.wm.distance("m60_42_36_00", (125, 0, 0), "m60_43_36_00", (-125, 0, 0)), 6.0)
        self.assertIsNone(self.wm.distance("m10_00_00_00", (0, 0, 0), "m11_00_00_00", (0, 0, 0)))

    @unittest.skipUnless(os.path.exists(os.path.join(ASSETS, "graces.json")), "brak assets/data")
    def test_matches_frontend_pixels(self):
        """Te same piksele co px/py w assets/data (liczone przez tools/extract)."""
        n = 0
        for g in load("graces.json"):
            if g.get("px") is None:
                continue
            r = self.wm.to_map(g["map_id"], *g["pos"])
            self.assertEqual(r["map"], g["map"])
            self.assertAlmostEqual(r["px"], g["px"], delta=1)
            self.assertAlmostEqual(r["py"], g["py"], delta=1)
            n += 1
        for t in load("item_locations.json")[:600]:       # też lochy (WorldMapLegacyConvParam, approx)
            if t.get("px") is None or not t.get("pos"):
                continue
            r = self.wm.to_map(t["map_id"], *t["pos"])
            self.assertEqual((r["map"], r["approx"]), (t["map"], t["approx"]))
            self.assertAlmostEqual(r["px"], t["px"], delta=1)
            n += 1
        self.assertGreater(n, 200)

    def test_inside_shape_rotated_rect_and_cylinder(self):
        from erbackend.worldmap import inside_shape
        rect = {"shape": "rect", "x": 0, "y": 0, "z": 0, "rot_y": 90.0, "dims": [10.0, 40.0]}   # 10 × 40, obrót 90°
        self.assertTrue(inside_shape(rect, (18, 0, 0)))       # po obrocie długa oś leży wzdłuż X
        self.assertFalse(inside_shape(rect, (0, 0, 18)))
        self.assertFalse(inside_shape(rect, (0, 60, 0)))      # za wysoko nad płaskim regionem
        cyl = {"shape": "cylinder", "x": 0, "y": 0, "z": 0, "rot_y": 0, "dims": [20.0, 10.0]}
        self.assertTrue(inside_shape(cyl, (10, 5, 10)))
        self.assertFalse(inside_shape(cyl, (10, 15, 10)))
        self.assertEqual(self.wm.to_frame("m60_43_36_00", (-125, 0, 0), "m60_42_36_00"), (131, 0, 0))

    def test_region_names(self):
        self.assertEqual(self.wm.region_name(6101000)["name"], "Burzowe Wzgórze")
        self.assertEqual(self.wm.region_name(6100000)["region"], "Pogrobno")
        self.assertEqual(self.wm.region_name(4500000)["name"], "Koloseum Królewskie")
        self.assertEqual(self.wm.region_name(4501000)["region"], "Pogrobno")
        self.assertEqual(self.wm.region_name(1209000)["subregion"], "Nokron, Wieczne Miasto")
        unnamed = {v["map_id"] for v in self.wm.play_regions.values() if v.get("named") is False}
        self.assertLessEqual(len(unnamed), 1, unnamed)                      # tylko m42_01 (brak nazwy w grze)
        self.assertIsNone(self.wm.region_name(1)["name"])

    @unittest.skipIf(source_save_dir() is None, "brak save'ów")
    def test_saves_regions_named(self):
        tmp = copy_saves()
        try:
            for fn in ("ER0000.sl2", "ER0000.co2"):
                p = os.path.join(tmp, fn)
                if not os.path.exists(p):
                    continue
                sf = SaveFile.read(p)
                ids = {r for i in sf.active_slots for r in sf.slot(i).regions}
                unnamed = [r for r in ids if not self.wm.region_name(r)["name"]]
                self.assertLessEqual(len(unnamed), max(5, len(ids) // 50), unnamed)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(os.path.exists(os.path.join(ASSETS, "bosses_all.json")), "brak assets/data")
class RegionsDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = GameData.load()

    def test_grace_regions(self):
        gs = self.gd.entries("graces")
        self.assertTrue(all(g["region"] for g in gs if g.get("map_id")))
        self.assertEqual(sum(1 for g in gs if g["dlc"]), 105)        # zgodne z tabelą CE
        by = {g["flag"]: g for g in gs}
        self.assertEqual(by[76101]["region"], "Pogrobno")             # Pierwszy krok
        self.assertEqual(by[76800]["region"], "Cmentarna równina")

    def test_boss_regions_and_arenas(self):
        bs = {b["defeat_flag"]: b for b in self.gd.entries("bosses")}
        self.assertEqual(bs[10000800]["region"], "Zamek Burzowego Całunu")   # Godrick
        self.assertEqual(bs[1052380800]["region"], "Caelid")                 # Radahn
        self.assertEqual(bs[10000800]["region"], bs[10000800]["region_pl"])
        with_pos = [b for b in bs.values() if (b.get("arena") or {}).get("radius")]
        self.assertGreater(len(with_pos), 0.9 * len(bs))
        self.assertTrue(all(b.get("subregion") for b in bs.values()))               # każdy boss ma podregion
        self.assertFalse([b["name"] for b in bs.values() if b["name"].startswith("Boss ")])
        regions = [b for b in bs.values() if (b.get("arena") or {}).get("match") == "region"]
        self.assertGreater(len(regions), 0.7 * len(bs))                         # granice areny z pliku mapy
        from erbackend.worldmap import inside_shape
        g = bs[10000800]["arena"]                                               # Godrick: w swoim regionie
        self.assertTrue(inside_shape(g["region"], (g["x"], g["y"], g["z"]), 2.0))

    def test_attempts_inside_arena_region(self):
        import shutil as _sh
        import tempfile
        from erbackend.history import History
        from erbackend.diffing import Snap
        from erbackend.flags import FlagMap
        boss = next(b for b in self.gd.entries("bosses") if b["defeat_flag"] == 10000800)
        a = boss["arena"]
        d = tempfile.mkdtemp(prefix="er-arena-test-")
        h = History(os.path.join(d, "h.sqlite"))
        try:
            fm = FlagMap.load()
            base = Snap(file="co2", slot=0, name="t", level=1, playtime_s=0, runes_memory=0, deaths=0,
                        map_id="m10_00_00_00", position={"map_id": "m10_00_00_00", "x": 0, "y": 0, "z": 0},
                        regions=[], bloodstain=None, md5="a", ts=1.79e9, flags=bytes(0x1BF99F))
            h.observe(base, fm, {})
            import dataclasses
            near = {"map_id": a["map_id"], "x": a["x"] + 3, "y": a["y"], "z": a["z"] + 3, "global": None, "runes": 1}
            far = {"map_id": a["map_id"], "x": a["x"] + 300, "y": a["y"], "z": a["z"], "global": None, "runes": 1}
            h.observe(dataclasses.replace(base, md5="b", ts=1.79e9 + 60, deaths=1, bloodstain=near), fm, {})
            h.observe(dataclasses.replace(base, md5="c", ts=1.79e9 + 120, deaths=2, bloodstain=far), fm, {})
            cid = h.character_id("co2", 0, "t")
            self.assertEqual(h.boss_attempts(cid, [boss], {}, WorldMap.load())[boss["id"]], 1)
        finally:
            h.close()
            _sh.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
