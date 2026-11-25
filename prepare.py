"""Jednorazowe przygotowanie danych z TWOJEJ instalacji Elden Ring (tylko odczyt plików gry).

    python prepare.py            # wszystko: dane społeczności, ekstrakcja z gry, questy, dane backendu
    python prepare.py --skip-extract   # gdy assets/ już są (np. skopiowane z innego komputera)

Wynik (lokalnie, poza repozytorium): assets/ (mapa, ikony, dane świata), backend/data/*.json.
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = [sys.executable, "-X", "utf8"]


def step(title, cmd, optional=False):
    t = time.time()
    print(f"\n=== {title} ===", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode and not optional:
        sys.exit(f"Krok nie powiódł się: {title}")
    print(f"({time.time() - t:.0f} s{', z ostrzeżeniem' if r.returncode else ''})", flush=True)


def main():
    if sys.version_info < (3, 11):
        sys.exit("Wymagany Python 3.11+ (zalecany 3.14).")
    step("Dane społeczności (ER-Save-Lib, The Grand Archives)", PY + ["tools/fetch_community.py"])
    if "--skip-extract" not in sys.argv:
        step("Ekstrakcja z plików gry: mapa, ikony, dane świata, portrety", PY + ["tools/extract/run_all.py"])
    step("Questy", PY + ["tools/extract/build_quests.py"], optional=True)
    step("Pełne listy kroków questów", PY + ["tools/extract/quest_steps.py"], optional=True)
    step("Dodatkowe dane świata dla backendu", PY + ["backend/tools/extract_world_extras.py"])
    step("Dane backendu", PY + ["backend/tools/build_data.py"])
    step("Teksty questów bez spoilerów", PY + ["tools/extract/quest_spoilers.py"])
    print("\nGotowe. Uruchom:  python start.py")


if __name__ == "__main__":
    main()
