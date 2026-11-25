"""Uruchamia backend elden-map.

    python backend/server.py                 # http://127.0.0.1:8765, folder save'a wykryty automatycznie
    python backend/server.py --port 9000 --save-dir "C:/kopia/save" -v

Tylko odczyt save'a, tylko biblioteka standardowa, nasłuch wyłącznie na interfejsie lokalnym.
"""
from __future__ import annotations

import argparse
import ipaddress
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erbackend.flags import DEFAULT_BST, FlagMap  # noqa: E402
from erbackend.gamedata import DATA_DIR, GameData  # noqa: E402
from erbackend.history import DEFAULT_DB, History  # noqa: E402
from erbackend.portraits import Portraits  # noqa: E402
from erbackend.server import make_server  # noqa: E402
from erbackend.service import Service, find_save_dir, find_save_dirs, save_roots  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Backend elden-map: API + SSE z pliku save Elden Ring (tylko odczyt).")
    ap.add_argument("--host", default="127.0.0.1", help="adres nasłuchu (tylko loopback), domyślnie 127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--save-dir", help="folder z ER0000.sl2/.co2 (domyślnie: ER_SAVE_DIR albo najświeższy w %%APPDATA%%/EldenRing "
                                       "lub w prefiksie Protona na Linuxie)")
    ap.add_argument("--bst", default=DEFAULT_BST, help="ścieżka do eventflag_bst.txt")
    ap.add_argument("--data-dir", default=DATA_DIR, help="folder z bosses/graces/items/quests.json")
    ap.add_argument("--db", default=DEFAULT_DB, help="baza historii SQLite (kronika, śmierci, sesje)")
    ap.add_argument("--poll", type=float, default=0.5, help="co ile sekund sprawdzać folder save'a")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):      # polskie znaki także przy przekierowaniu do pliku
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    host = a.host
    if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
        ap.error("--host musi być adresem lokalnym (127.0.0.1 / ::1 / localhost)")

    save_dirs = None if a.save_dir else find_save_dirs()   # .sl2 i .co2 mogą być w różnych prefiksach Protona
    save_dir = a.save_dir or find_save_dir()
    if not save_dir or not os.path.isdir(save_dir):
        ap.error("nie znaleziono folderu save'a (podaj --save-dir albo ER_SAVE_DIR); szukano w: " + ", ".join(save_roots()))
    if not os.path.exists(a.bst):
        ap.error(f"brak pliku {a.bst} (mapa ID flagi -> bajt/bit)")

    service = Service(save_dir, FlagMap.load(a.bst), GameData.load(a.data_dir), History(a.db), poll_interval=a.poll,
                      save_dirs=save_dirs)
    service.start()
    httpd = make_server(service, host, a.port)
    # portrety postaci: render w tle po zmianie hełmu/wyglądu (i brakujące przy starcie, gdy serwer już nasłuchuje)
    portraits = Portraits(service)
    service.listeners.append(portraits.check)
    portraits.scan_all()
    logging.info("elden-map backend: http://%s:%d/api/health  (save: %s, baza: %s, aktywny: %s)",
                 host, a.port, " | ".join(f"{k}: {v}" for k, v in service.save_dirs.items()), a.db, service.active)
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.stopping = True
        httpd.server_close()
        service.stop()
        service.history.close()


if __name__ == "__main__":
    main()
