"""Uruchamia backend (save → API na 127.0.0.1:8765) i stronę (127.0.0.1:5180), potem otwiera przeglądarkę.

    python start.py                      # folder save'a wykryty automatycznie (Windows / Linux + Proton)
    python start.py --save-dir ŚCIEŻKA   # albo zmienna ER_SAVE_DIR
    python start.py --no-browser

Ctrl+C zatrzymuje oba serwery. Wszystko nasłuchuje tylko lokalnie.
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="Elden Map — backend + strona")
    ap.add_argument("--save-dir", help="folder z ER0000.sl2 / ER0000.co2")
    ap.add_argument("--port", type=int, default=5180, help="port strony (domyślnie 5180)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(os.path.join(ROOT, "assets", "data", "bosses_all.json")):
        print("Brak danych z gry — najpierw uruchom:  python prepare.py")
    be = [sys.executable, "-X", "utf8", os.path.join(ROOT, "backend", "server.py")]
    if a.save_dir:
        be += ["--save-dir", a.save_dir]
    procs = [subprocess.Popen(be, cwd=ROOT),
             subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "static_server.py"), str(a.port)], cwd=ROOT)]
    url = f"http://127.0.0.1:{a.port}/mockup/"
    for _ in range(40):                                   # poczekaj, aż strona odpowie
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    print(f"\nElden Map: {url}   (API: http://127.0.0.1:8765/api/health)   — Ctrl+C kończy\n")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
