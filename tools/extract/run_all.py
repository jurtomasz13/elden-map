"""Pełna ekstrakcja zasobów z gry jednym poleceniem: python tools/extract/run_all.py"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    [sys.executable, "-X", "utf8", "extract_map.py"],
    ["node", "--max-old-space-size=4096", "build_tiles.mjs"],
    [sys.executable, "-X", "utf8", "extract_icons.py"],
    ["node", "build_icons.mjs"],
    [sys.executable, "-X", "utf8", "extract_data.py"],
    [sys.executable, "-X", "utf8", "extract_curves.py"],
    [sys.executable, "-X", "utf8", "extract_world.py"],
    [sys.executable, "-X", "utf8", "render_bosses.py"],     # portrety 3D bossów bez ikony (renderuje tylko brakujące)
    [sys.executable, "-X", "utf8", "extract_sources.py"],   # skąd zdobyć przedmioty (kupcy, wrogowie, bossowie, zdarzenia)
    [sys.executable, "-X", "utf8", "quest_spoilers.py"],    # wersje kroków questów bez spoilerów
]

for cmd in STEPS:
    t = time.time()
    print(">>", " ".join(cmd[-1:]), flush=True)
    subprocess.run(cmd, cwd=HERE, check=True)
    print(f"   {time.time() - t:.0f} s", flush=True)
print("Gotowe. Wyniki w assets/ (tylko lokalnie — zasoby gry, nie publikować).")
