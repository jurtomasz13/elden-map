import unittest

import helpers  # noqa: F401  (ustawia sys.path)

from erbackend.flags import FlagMap
from erbackend.gamedata import KINDS, GameData

CONF = {"verified", "high", "medium", "low"}
REQUIRED = {
    "bosses": {"id", "name", "region", "location", "defeat_flag", "alt_flags", "arena", "dlc", "required", "hints",
               "sources", "confidence"},
    "graces": {"id", "name", "region", "area", "flag", "dlc", "sources", "confidence"},
    "items": {"id", "name", "category", "flag", "dlc", "location", "sources", "confidence"},
    "quests": {"id", "name", "npc", "steps", "sources", "confidence"},
}


class DataFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = GameData.load()
        cls.fm = FlagMap.load()

    def test_schema(self):
        for kind in KINDS:
            data = self.gd.sets[kind]
            meta = data["_meta"]
            self.assertEqual(meta["kind"], kind)
            self.assertEqual(meta["schema_version"], 1)
            ids = set()
            for e in data["entries"]:
                missing = REQUIRED[kind] - e.keys()
                self.assertFalse(missing, f"{kind}/{e.get('id')}: brak pól {missing}")
                self.assertNotIn(e["id"], ids, f"duplikat id {e['id']}")
                ids.add(e["id"])
                self.assertIn(e["confidence"], CONF)
                for src in e["sources"]:
                    self.assertIn(src, meta["sources"], f"{e['id']}: nieopisane źródło {src}")
                flags = [e["defeat_flag"], *e["alt_flags"]] if kind == "bosses" else \
                    [f for s in e.get("steps", []) for f in s.get("flags", [])] if kind == "quests" else [e["flag"]]
                for f in flags:
                    self.assertTrue(self.fm.known(f), f"{e['id']}: flaga {f} spoza tabeli bst")

    def test_counts(self):
        self.assertGreaterEqual(len(self.gd.entries("bosses")), 30)
        self.assertGreaterEqual(len(self.gd.entries("graces")), 100)
        self.assertGreaterEqual(len(self.gd.entries("items")), 100)

    def test_evaluate_with_fake_flags(self):
        b = self.gd.entries("bosses")[0]
        g = self.gd.entries("graces")[0]
        on = {b["defeat_flag"], g["flag"]}
        res = self.gd.evaluate(lambda f: f in on)
        self.assertEqual(res["progress"]["bosses"]["done"], 1)
        self.assertEqual(res["progress"]["graces"]["done"], 1)
        self.assertEqual(res["progress"]["items"]["done"], 0)
        self.assertTrue(next(x for x in res["bosses"] if x["id"] == b["id"])["defeated"])

    def test_world_data_consistency(self):
        dlc_maps = ("m20", "m21", "m22", "m25", "m28", "m40", "m41", "m42", "m43", "m61")
        for kind in ("bosses", "graces", "items"):
            for e in self.gd.entries(kind):
                if e.get("map_id"):
                    self.assertEqual(e["dlc"], e["map_id"].startswith(dlc_maps), f"{kind}/{e['id']}")
        boss_ids = {b["id"] for b in self.gd.entries("bosses")}
        for q in self.gd.entries("quests"):
            for lk in q.get("locks", []):
                self.assertIn(lk["boss_id"], boss_ids, q["id"])
        # last_rested_grace z save'a = encja + 1000
        idx = self.gd.grace_by_last_grace()
        if idx:
            g = next(iter(idx.values()))
            self.assertEqual(idx[g["entity"] + 1000]["id"], g["id"])

    def test_progress_detail(self):
        res = self.gd.evaluate(lambda f: False)
        pd = res["progress_detail"]
        self.assertEqual(pd["bosses"]["base"]["total"] + pd["bosses"]["dlc"]["total"], res["progress"]["bosses"]["total"])
        self.assertEqual(sum(c["total"] for c in pd["items_by_category"].values()), res["progress"]["items"]["total"])

    def test_quest_steps(self):
        gd = GameData({**self.gd.sets, "quests": {"_meta": {"kind": "quests", "schema_version": 1}, "entries": [
            {"id": "q", "name": "Test", "npc": "NPC", "steps": [
                {"id": "a", "text": "krok 1", "flags": [1, 2], "mode": "all"},
                {"id": "b", "text": "krok 2", "flags": [3, 4], "mode": "any", "next": "idź tam"},
                {"id": "c", "text": "krok 3", "flags": [5]}]}]}})
        q = gd.evaluate(lambda f: f in {1, 2, 4})["quests"][0]
        self.assertEqual([s["done"] for s in q["steps"]], [True, True, False])
        self.assertEqual(q["next"], "krok 3")
        q = gd.evaluate(lambda f: f in {1})["quests"][0]
        self.assertEqual(q["next"], "krok 1")
        self.assertFalse(q["completed"])
        idx = gd.flag_index()
        self.assertEqual(idx[4][0][0], "quests")


if __name__ == "__main__":
    unittest.main()
