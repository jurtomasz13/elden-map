"""Portrety: render tylko gdy zmienił się podpis (zbroja + blok FACE + renderer) albo brak PNG; zdarzenie SSE 'portrait' po sukcesie."""
import os
import queue
import shutil
import sys
import tempfile
import time
import unittest

from helpers import copy_saves, source_save_dir

from erbackend import portraits as P
from erbackend.flags import FlagMap
from erbackend.gamedata import GameData
from erbackend.history import History
from erbackend.service import Service


@unittest.skipUnless(source_save_dir(), "brak save'ów Elden Ring")
class PortraitsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = copy_saves()
        self.out = tempfile.mkdtemp()
        # podmiana skryptu renderu na atrapę, która tylko tworzy oba PNG (głowa i cała postać)
        self.fake = os.path.join(self.out, "fake_render.py")
        with open(self.fake, "w", encoding="utf-8") as f:
            f.write("import os,sys\nif sys.argv[1:] == ['--version']:\n    print('render-1')\n    sys.exit(0)\n"
                    "for s in ('', '_full'):\n"
                    "    open(os.path.join(os.environ['ER_RENDERS'], f'char_{sys.argv[1]}_{sys.argv[2]}{s}.png'),'wb').write(b'x')\n")
        os.environ["ER_RENDERS"] = self.out
        self._orig = (P.SCRIPT, P.RENDERS, P.STATE)
        P.SCRIPT, P.RENDERS, P.STATE = self.fake, self.out, os.path.join(self.out, "portraits.json")
        self.service = Service(self.tmp, FlagMap.load(), GameData.load(), History(":memory:"))
        self.q = self.service.subscribe()
        self.p = P.Portraits(self.service, python=sys.executable)
        self.p.python = sys.executable
        self.kind, self.sf = next(iter(self.service.saves.items()))
        self.slot = self.sf.active_slots[0]

    def tearDown(self):
        P.SCRIPT, P.RENDERS, P.STATE = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.out, ignore_errors=True)

    def _events(self, timeout=10.0):
        out, end = [], time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                _id, ev, data = self.q.get(timeout=0.2)
            except queue.Empty:
                if out:
                    break
                continue
            if ev == "portrait":
                out.append(data)
        return out

    def test_renders_once_then_on_change(self):
        self.p.check(self.kind, self.slot, self.sf)
        ev = self._events()
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["file"], ev[0]["slot"]), (self.kind, self.slot))
        self.assertTrue(os.path.exists(os.path.join(self.out, f"char_{self.kind}_{self.slot}.png")))
        # ten sam podpis i PNG istnieje — bez renderu
        self.p.check(self.kind, self.slot, self.sf)
        self.assertEqual(self._events(timeout=1.5), [])
        # inny podpis (np. zmieniony hełm) — render ponownie
        self.p.done[f"{self.kind}:{self.slot}"] = "inny-hełm:xxx"
        self.p.check(self.kind, self.slot, self.sf)
        self.assertEqual(len(self._events()), 1)
        # nowa wersja renderera (aktualizacja aplikacji): portret rysowany od nowa, choć hełm i twarz bez zmian
        self.assertEqual(self.p.version, "render-1")
        self.p.version = "render-2"
        self.p.check(self.kind, self.slot, self.sf)
        self.assertEqual(len(self._events()), 1)

    def test_signature_has_head_and_face(self):
        sig, head = P.Portraits.signature(self.sf, self.slot)
        self.assertIn(":", sig)
        self.assertNotEqual(sig.split(":")[1], "-")       # blok FACE znaleziony


if __name__ == "__main__":
    unittest.main()
