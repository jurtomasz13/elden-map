"""Ekwipunek (inventory_held + storage_box): logika na danych syntetycznych i sprawdzenie na kopiach save'ów."""
import shutil
import unittest

import os

from helpers import copy_saves, source_save_dir

from erbackend import inventory
from erbackend.savefile import SaveFile

KINDS = ("weapons", "armor", "talismans", "goods", "ashes", "key_items")


class BuildTest(unittest.TestCase):
    def test_resolution_and_grouping(self):
        gaitems = {0x80800001: 1031125, 0x80800002: 1031125, 0x90800003: 0x10000000 | 670100,
                   0xC0800004: 0x80000000 | 10700, 0x80800005: 110000, 0x90800006: 0x10000000 | 10000}
        weapon_ash = {0x80800001: 0xC0800004}
        held = ([(0x80800001, 1, 1), (0x80800002, 1, 2), (0x90800003, 1, 3), (0xA00003E8, 1, 4),
                 (0xB00003E9, 4, 5), (0xC0800004, 1, 6), (0x80800005, 1, 7), (0x90800006, 1, 8),
                 (0x80999999, 1, 9)],
                [(0xB0002134, 1, 10)])
        storage = ([(0xB00003E9, 6, 11)], [])
        inv = inventory.build(held, storage, gaitems, weapon_ash)
        w = inv["weapons"]
        self.assertEqual(len(w), 2)                       # ta sama broń, raz z popiołem, raz bez
        with_ash = next(x for x in w if x["ash_id"])
        self.assertEqual((with_ash["id"], with_ash["base_id"], with_ash["upgrade"], with_ash["affinity"],
                          with_ash["ash_id"]), (1031125, 1030000, 25, "blood", 10700))
        self.assertEqual([a["id"] for a in inv["armor"]], [670100])          # zaślepka 10000 pominięta
        self.assertEqual(inv["talismans"], [{"id": 1000, "count": 1, "storage": 0}])
        self.assertEqual(inv["goods"], [{"id": 1001, "count": 4, "storage": 6}])
        self.assertEqual(inv["ashes"], [{"id": 10700, "count": 1, "storage": 0}])
        self.assertEqual(inv["key_items"], [{"id": 0x2134, "count": 1, "storage": 0}])
        self.assertEqual(inv["totals"]["unresolved"], 1)                     # handle bez wpisu GaItem

    def test_sizes(self):
        self.assertEqual(inventory.HELD_SIZE, 0x9010)
        self.assertEqual(inventory.STORAGE_SIZE, 0x6010)


@unittest.skipIf(source_save_dir() is None, "brak save'ów (ustaw ER_SAVE_DIR)")
class RealSavesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = copy_saves()
        cls.files = [SaveFile.read(os.path.join(cls.tmp, f)) for f in ("ER0000.sl2", "ER0000.co2")
                     if os.path.exists(os.path.join(cls.tmp, f))]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_all_characters(self):
        for sf in self.files:
            for i in sf.active_slots:
                inv = sf.slot(i).inventory
                for k in KINDS:
                    self.assertIsInstance(inv[k], list)
                t = inv["totals"]
                self.assertEqual(t["unresolved"], 0, sf.character(i).name)
                self.assertLessEqual(t["held_entries"], t["held_capacity"])
                self.assertLessEqual(t["storage_entries"], t["storage_capacity"])
                self.assertNotIn(110000, [w["id"] for w in inv["weapons"]])
                for w in inv["weapons"]:
                    self.assertEqual(w["base_id"] + w["upgrade"], w["id"] - (w["id"] % 10000 // 100) * 100)
                    self.assertLessEqual(w["upgrade"], 25)
                for e in inv["goods"] + inv["armor"] + inv["talismans"]:
                    self.assertGreater(e["count"] + e["storage"], 0)

    def test_equipment_shape_and_consistency(self):
        """Założone rzeczy (poza flaszkami 1000–1099) muszą być w ekwipunku; zaślepki = null."""
        for sf in self.files:
            for i in sf.active_slots:
                q = sf.slot(i).equipment
                inv = sf.slot(i).inventory
                self.assertEqual(len(q["right_weapons"]), 3)
                self.assertEqual(len(q["left_weapons"]), 3)
                self.assertEqual(len(q["talismans"]), 4)
                self.assertEqual(len(q["ammo"]), 4)
                self.assertEqual(len(q["quick_items"]), 10)
                self.assertEqual(len(q["pouch"]), 6)
                self.assertEqual(len(q["spells"]), 14)
                self.assertEqual(len(q["physick"]), 2)
                have = {k: {e["id"] for e in inv[k]} for k in ("weapons", "armor", "talismans", "goods", "key_items")}
                for w in q["right_weapons"] + q["left_weapons"] + q["ammo"]:
                    if w:
                        self.assertIn(w["id"], have["weapons"])
                        self.assertNotEqual(w["id"], 110000)
                for k in ("head", "chest", "arms", "legs"):
                    if q[k]:
                        self.assertIn(q[k]["id"], have["armor"])
                        self.assertNotIn(q[k]["id"], (10000, 10100, 10200, 10300))
                for t in q["talismans"]:
                    if t:
                        self.assertIn(t["id"], have["talismans"])
                for g in q["quick_items"] + q["pouch"] + [q["great_rune"]]:
                    if g and not 1000 <= g["id"] < 1100:
                        self.assertIn(g["id"], have["goods"] | have["key_items"])
                c = sf.character(i)
                self.assertIsNotNone(c.profile["archetype"]["name"])
                self.assertIsNotNone(c.profile["starting_gift"]["name"])

    def test_lowest_level_has_starting_kit(self):
        """Najsłabsza postać: komplet 4 części zbroi startowej (xx0000..xx0300), broń, flaszki."""
        sf = self.files[-1]
        slot = min(sf.active_slots, key=lambda i: sf.character(i).level)
        inv = sf.slot(slot).inventory
        armor = sorted(a["id"] for a in inv["armor"])
        self.assertEqual(len(armor), 4)
        self.assertEqual([a - armor[0] for a in armor], [0, 100, 200, 300])
        self.assertGreaterEqual(len(inv["weapons"]), 1)
        self.assertTrue(inv["goods"])


if __name__ == "__main__":
    unittest.main()
