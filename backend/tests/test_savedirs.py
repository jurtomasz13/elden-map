"""Wykrywanie save'ów na Linuxie: .sl2 i .co2 w różnych prefiksach Protona (Seamless Coop jako gra spoza Steama)."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from helpers import source_save_dir

from erbackend import service as S
from erbackend.flags import FlagMap
from erbackend.gamedata import GameData
from erbackend.history import History

STEAM_ID = "76561190000000001"


def proton_save_dir(home, appid):
    return os.path.join(home, ".local", "share", "Steam", "steamapps", "compatdata", appid, "pfx", "drive_c", "users",
                        "steamuser", "AppData", "Roaming", "EldenRing", STEAM_ID)


@unittest.skipUnless(source_save_dir(), "brak save'ów Elden Ring")
class SaveDirsTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        src = source_save_dir()
        self.game = proton_save_dir(self.home, "1245620")            # oficjalna gra
        self.coop = proton_save_dir(self.home, "3141592653")         # Seamless Coop dodany jako gra spoza Steama
        os.makedirs(self.game)
        os.makedirs(self.coop)
        shutil.copy2(os.path.join(src, "ER0000.sl2"), self.game)
        shutil.copy2(os.path.join(src, "ER0000.co2"), self.coop)
        self.env = mock.patch.dict(os.environ, {"APPDATA": ""}, clear=False)
        self.env.start()
        os.environ.pop("ER_SAVE_DIR", None)
        self.user = mock.patch("os.path.expanduser", lambda p: p.replace("~", self.home, 1))
        self.user.start()

    def tearDown(self):
        self.user.stop()
        self.env.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def test_finds_both_prefixes(self):
        dirs = S.find_save_dirs()
        self.assertEqual(os.path.normcase(dirs["sl2"]), os.path.normcase(self.game))
        self.assertEqual(os.path.normcase(dirs["co2"]), os.path.normcase(self.coop))

    def test_service_reads_both(self):
        dirs = S.find_save_dirs()
        svc = S.Service(S.find_save_dir(), FlagMap.load(), GameData.load(), History(":memory:"), save_dirs=dirs)
        files = {f["file"]: f for f in svc.characters()["files"]}
        self.assertIn("sl2", files)
        self.assertIn("co2", files)
        self.assertTrue(files["sl2"]["characters"])
        self.assertTrue(files["co2"]["characters"])


if __name__ == "__main__":
    unittest.main()
