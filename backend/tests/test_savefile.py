import csv
import os
import shutil
import struct
import tempfile
import unittest

from helpers import BACKEND, copy_saves, patched_bytes, replace_atomically, source_save_dir

from erbackend.flags import FlagMap
from erbackend.savefile import FLAGS_SIZE, SaveBusy, SaveError, SaveFile, position_dict

CSV = os.path.join(BACKEND, "..", "docs", "data", "ct_event_flags.csv")


class FlagMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fm = FlagMap.load()

    @unittest.skipUnless(os.path.exists(CSV), "brak lokalnego wyciągu z tabeli CE (docs/data/ct_event_flags.csv)")
    def test_location_matches_cheat_table(self):
        """Wszystkie 600 flag z tabeli CE: ID -> (bajt, bit) zgadza się z offsetem z tabeli."""
        with open(CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertGreater(len(rows), 500)
        for r in rows:
            fid = int(r["flag_id"])
            self.assertEqual(self.fm.location(fid), (int(r["byte_offset"], 16), int(r["bit"])), fid)

    def test_inverse_and_diff(self):
        for fid in (76800, 2046410800, 9140, 65610):
            byte, bit = self.fm.location(fid)
            self.assertEqual(self.fm.flag_id_at(byte, bit), fid)
        old = bytes(FLAGS_SIZE)
        new = bytearray(old)
        for fid in (76800, 20000800):
            b, bit = self.fm.location(fid)
            new[b] |= 1 << bit
        d = self.fm.diff(old, bytes(new))
        self.assertEqual([(x[0], x[1]) for x in d], [(76800, True), (20000800, True)])
        self.assertEqual(self.fm.get(bytes(new), 76800), True)
        self.assertEqual(self.fm.get(bytes(new), 76801), False)
        self.assertIsNone(self.fm.get(bytes(new), 999_999_999_999))

    def test_position_global(self):
        p = position_dict("m61_49_43_00", -19.4, 386.2, 3.3)
        self.assertAlmostEqual(p["global"]["x"], 49 * 256 + 128 - 19.4, places=3)
        self.assertTrue(p["global"]["verified"])
        self.assertIsNone(position_dict("m11_00_00_00", 1, 2, 3)["global"])


@unittest.skipIf(source_save_dir() is None, "brak save'ów (ustaw ER_SAVE_DIR)")
class SaveFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = copy_saves()
        cls.fm = FlagMap.load()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def files(self):
        return [os.path.join(self.tmp, f) for f in ("ER0000.sl2", "ER0000.co2")
                if os.path.exists(os.path.join(self.tmp, f))]

    def test_parse_all_slots(self):
        self.assertTrue(self.files())
        for path in self.files():
            sf = SaveFile.read(path)
            self.assertTrue(all(e.md5_ok for e in sf.entries))
            self.assertTrue(sf.active_slots)
            self.assertIn(sf.last_slot, sf.active_slots)
            self.assertGreater(sf.steam_id, 76561197960265728)
            for c in sf.characters():
                s = sf.slot(c.slot)
                self.assertTrue(c.name)
                self.assertGreaterEqual(c.level, 1)
                self.assertEqual(len(s.flags), FLAGS_SIZE)
                self.assertRegex(s.map_id, r"^m\d\d_\d\d_\d\d_\d\d$")
                self.assertRegex(s.position["map_id"], r"^m\d\d_\d\d_\d\d_\d\d$")
                self.assertGreaterEqual(len(s.regions), 1)
                self.assertLess(s.deaths, 1_000_000)
                # sanity: bajt za flagami to terminator 0x00 (sprawdzane też w parserze)
                e = sf.entries[c.slot]
                self.assertEqual(sf.data[e.offset + 16 + s.flags_offset + FLAGS_SIZE], 0)
                # atrybuty z PlayerGameData: suma − 79 = poziom z profilu
                a = s.stats["attributes"]
                self.assertIsNotNone(a)
                self.assertEqual(sum(a.values()) - 79, c.level)
                self.assertGreater(s.stats["hp"]["max"], 0)

    def test_md5_mismatch_is_busy_then_retry_gives_up(self):
        path = self.files()[0]
        with open(path, "rb") as f:
            d = bytearray(f.read())
        sf = SaveFile.read(path)
        e = sf.entries[sf.active_slots[0]]
        d[e.offset + 100] ^= 0xFF          # zepsuta treść, MD5 się nie zgadza (jak w trakcie zapisu)
        bad = os.path.join(self.tmp, "broken.sl2")
        with open(bad, "wb") as f:
            f.write(d)
        with self.assertRaises(SaveBusy):
            SaveFile.read(bad, retries=2, delay=0.01)

    def test_truncated_and_garbage(self):
        path = self.files()[0]
        cut = os.path.join(self.tmp, "cut.sl2")
        with open(path, "rb") as src, open(cut, "wb") as f:
            f.write(src.read()[:0x1000000])
        with self.assertRaises(SaveError):
            SaveFile.read(cut, retries=1)
        junk = os.path.join(self.tmp, "junk.sl2")
        with open(junk, "wb") as f:
            f.write(b"NOPE" + bytes(100))
        with self.assertRaises(SaveError):
            SaveFile.read(junk, retries=1)

    def test_patched_flag_roundtrip(self):
        path = self.files()[0]
        sf = SaveFile.read(path)
        slot = sf.active_slots[-1]
        target = os.path.join(self.tmp, "patched." + path.rsplit(".", 1)[1])
        before = self.fm.get(sf.slot(slot).flags, 76800)
        replace_atomically(target, patched_bytes(path, slot, {76800: not before}, self.fm))
        sf2 = SaveFile.read(target)
        self.assertEqual(self.fm.get(sf2.slot(slot).flags, 76800), not before)
        self.assertNotEqual(sf.slot_md5(slot), sf2.slot_md5(slot))
        others = [i for i in sf.active_slots if i != slot]
        for i in others:
            self.assertEqual(sf.slot_md5(i), sf2.slot_md5(i))

    def test_profile_fields(self):
        for path in self.files():
            sf = SaveFile.read(path)
            for c in sf.characters():
                b = 0x195E + c.slot * 0x24C
                self.assertEqual(struct.unpack_from("<I", sf.profile, b + 0x22)[0], c.level)


if __name__ == "__main__":
    unittest.main()
