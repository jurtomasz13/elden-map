"""Testy end-to-end: serwis + serwer HTTP na kopiach save'ów; SSE po podmianie pliku."""
import http.client
import json
import os
import shutil
import threading
import time
import unittest

from helpers import copy_saves, patched_bytes, replace_atomically, source_save_dir

from erbackend.flags import FlagMap
from erbackend.gamedata import GameData
from erbackend.history import History
from erbackend.savefile import SaveFile
from erbackend.server import make_server
from erbackend.service import Service


def read_sse_event(resp, timeout: float):
    """Czyta jedno zdarzenie SSE (pomija komentarze). Zwraca (event, data)."""
    resp.fp.raw._sock.settimeout(timeout)
    event, data = None, []
    while True:
        line = resp.fp.readline().decode("utf-8")
        if not line:
            raise EOFError("strumień SSE zamknięty")
        line = line.rstrip("\r\n")
        if line == "":
            if event or data:
                return event, json.loads("\n".join(data)) if data else None
            continue
        if line.startswith(":"):
            continue
        k, _, v = line.partition(": ")
        if k == "event":
            event = v
        elif k == "data":
            data.append(v)


@unittest.skipIf(source_save_dir() is None, "brak save'ów (ustaw ER_SAVE_DIR)")
class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = copy_saves()
        cls.fm = FlagMap.load()
        cls.history = History(os.path.join(cls.tmp, "history.sqlite"))
        cls.service = Service(cls.tmp, cls.fm, GameData.load(), cls.history, poll_interval=0.1, debounce=0.15)
        cls.service.start()
        cls.httpd = make_server(cls.service, "127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.stopping = True
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.service.stop()
        cls.history.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", path, headers=headers or {})
        r = c.getresponse()
        body = r.read()
        c.close()
        return r, json.loads(body) if body else None

    def kinds(self):
        return [k for k in ("sl2", "co2") if os.path.exists(os.path.join(self.tmp, "ER0000." + k))]

    # --- REST --------------------------------------------------------------------------------
    def test_health(self):
        r, body = self.get("/api/health")
        self.assertEqual(r.status, 200)
        self.assertTrue(body["ok"])

    def test_characters(self):
        r, body = self.get("/api/characters")
        self.assertEqual(r.status, 200)
        self.assertEqual([f["file"] for f in body["files"]], self.kinds())
        for f in body["files"]:
            self.assertTrue(f["characters"])
            for c in f["characters"]:
                self.assertEqual(set(c), {"slot", "name", "level", "playtime_s", "runes_memory", "map_id"})
        self.assertIsNotNone(body["active"])

    def test_state_contract(self):
        kind = self.kinds()[0]
        slot = SaveFile.read(os.path.join(self.tmp, "ER0000." + kind)).active_slots[0]
        r, st = self.get(f"/api/state?file={kind}&slot={slot}")
        self.assertEqual(r.status, 200)
        for key in ("character", "position", "regions_unlocked", "equipment", "inventory", "bosses", "graces", "items", "quests",
                    "progress", "save"):
            self.assertIn(key, st)
        self.assertEqual(set(st["character"]) >= {"slot", "name", "level", "playtime_s", "runes_memory", "archetype",
                                                  "deaths", "last_grace"}, True)
        self.assertEqual(set(st["position"]) >= {"map_id", "x", "y", "z"}, True)
        self.assertEqual(set(st["bosses"][0]) >= {"id", "name", "region", "defeated", "dlc"}, True)
        self.assertEqual(set(st["graces"][0]) >= {"id", "name", "region", "visited"}, True)
        self.assertEqual(set(st["items"][0]) >= {"id", "name", "category", "collected"}, True)
        for k in ("bosses", "graces", "items", "quests"):
            self.assertEqual(st["progress"][k]["total"], len(st[k]))
        self.assertEqual(st["save"]["file"], kind)
        # bez parametrów -> aktywny slot
        r, st2 = self.get("/api/state")
        self.assertEqual(r.status, 200)
        self.assertEqual((st2["save"]["file"], st2["character"]["slot"]),
                         (self.service.active["file"], self.service.active["slot"]))
        self.assertIn("progress_detail", st)
        self.assertEqual(len(st["regions"]), len(st["regions_unlocked"]))
        if self.service.worldmap.available and st["position"]["map_id"][:3] in ("m60", "m61"):
            self.assertIn(st["position"]["map"]["map"], ("M00", "M10"))
        # nazwa ostatniej łaski z danych świata (gdy są) — każda postać z save'a ma ją rozpoznaną
        if self.service.gamedata.grace_by_last_grace():
            self.assertIsNotNone(st["character"]["last_grace"]["name"])
        # filtr sekcji
        r, part = self.get(f"/api/state?file={kind}&slot={slot}&sections=bosses,progress")
        self.assertEqual(set(part), {"character", "save", "bosses", "progress"})
        r, part = self.get(f"/api/state?file={kind}&slot={slot}&sections=items,progress&item_kind=acquired_flag")
        self.assertTrue(part["items"] and all(i["kind"] == "acquired_flag" for i in part["items"]))
        self.assertEqual(part["progress"]["items"]["total"], st["progress"]["items"]["total"])   # postęp bez zmian

    def test_flags_endpoint(self):
        r, body = self.get("/api/flags?ids=76800,9140,1")
        self.assertEqual(r.status, 200)
        self.assertEqual(set(body["flags"]), {"76800", "9140", "1"})
        r, _ = self.get("/api/flags?ids=abc")
        self.assertEqual(r.status, 400)

    def test_errors(self):
        self.assertEqual(self.get("/api/state?file=xyz")[0].status, 400)
        self.assertEqual(self.get("/api/state?slot=abc")[0].status, 400)
        self.assertEqual(self.get(f"/api/state?file={self.kinds()[0]}&slot=9")[0].status, 404)
        self.assertEqual(self.get("/api/nope")[0].status, 404)
        self.assertEqual(self.get("/api/health", {"Host": "evil.example.com"})[0].status, 403)

    def test_cors(self):
        r, _ = self.get("/api/health", {"Origin": "http://localhost:5173"})
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "http://localhost:5173")
        r, _ = self.get("/api/health", {"Origin": "https://example.com"})
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))

    def test_data_endpoint(self):
        r, body = self.get("/api/data/bosses")
        self.assertEqual(r.status, 200)
        self.assertEqual(body["_meta"]["kind"], "bosses")

    # --- SSE ---------------------------------------------------------------------------------
    def test_sse_event_after_save_replaced(self):
        kind = self.kinds()[-1]
        path = os.path.join(self.tmp, "ER0000." + kind)
        sf = SaveFile.read(path)
        slot = sf.active_slots[-1]
        flags = sf.slot(slot).flags
        boss = next(b for b in self.service.gamedata.entries("bosses") if not self.fm.get(flags, b["defeat_flag"]))
        grace = next(g for g in self.service.gamedata.entries("graces") if not self.fm.get(flags, g["flag"]))

        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", "/api/events", headers={"Origin": "http://127.0.0.1:3000"})
        resp = c.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.getheader("Content-Type").startswith("text/event-stream"))
        self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), "http://127.0.0.1:3000")
        ev, data = read_sse_event(resp, 5)
        self.assertEqual(ev, "hello")

        # "gra zapisuje": atomowa podmiana kopii pliku z 2 nowymi flagami
        t0 = time.monotonic()
        replace_atomically(path, patched_bytes(path, slot, {boss["defeat_flag"]: True, grace["flag"]: True}, self.fm))
        ev, data = read_sse_event(resp, 10)
        latency = time.monotonic() - t0
        ev2, chron = read_sse_event(resp, 5)
        c.close()
        self.assertEqual(ev2, "chronicle")
        kinds = {e["kind"] for e in chron["events"]}          # flaga bossa bywa też krokiem questa
        self.assertLessEqual({"boss_defeated", "grace_discovered"}, kinds)
        self.assertLessEqual(kinds, {"boss_defeated", "grace_discovered", "quest_step"})
        _, body = self.get(f"/api/chronicle?file={kind}&slot={slot}&limit=5")
        self.assertLessEqual({boss["id"], grace["id"]}, {e["ref_id"] for e in body["events"]})
        self.assertEqual(body["character"]["slot"], slot)
        _, body = self.get(f"/api/chronicle?file={kind}&slot={slot}&kind=boss_defeated")
        self.assertEqual([e["ref_id"] for e in body["events"]], [boss["id"]])
        r, body = self.get(f"/api/deaths?file={kind}&slot={slot}")
        self.assertEqual(r.status, 200)
        self.assertEqual(body["recorded"], 0)
        r, body = self.get(f"/api/session?file={kind}&slot={slot}")
        self.assertEqual(r.status, 200)
        self.assertEqual([b["id"] for b in body["session"]["bosses"]], [boss["id"]])
        self.assertEqual(self.get("/api/chronicle?limit=0")[0].status, 400)
        r, body = self.get(f"/api/days?file={kind}&slot={slot}")
        self.assertEqual(r.status, 200)
        self.assertEqual([b["id"] for b in body["days"][0]["bosses"]], [boss["id"]])
        self.assertEqual(self.get("/api/days?before=wczoraj")[0].status, 400)
        self.assertEqual(ev, "save")
        self.assertEqual((data["file"], data["slot"]), (kind, slot))
        self.assertEqual(data["changed_flags_total"], 2)
        self.assertEqual({f["id"] for f in data["changed_flags"]}, {boss["defeat_flag"], grace["flag"]})
        self.assertEqual([b["id"] for b in data["completed"]["bosses"]], [boss["id"]])
        self.assertEqual([g["id"] for g in data["completed"]["graces"]], [grace["id"]])
        self.assertEqual(data["active"]["file"], kind)
        self.assertEqual(data["active"]["slot"], slot)
        self.assertLess(latency, 5)
        # stan po zapisie widzi nowe flagi
        _, st = self.get(f"/api/state?file={kind}&slot={slot}")
        self.assertTrue(next(b for b in st["bosses"] if b["id"] == boss["id"])["defeated"])
        self.assertTrue(st["save"]["is_active"])


if __name__ == "__main__":
    unittest.main()
