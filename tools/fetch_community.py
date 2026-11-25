"""Pobiera dane społeczności potrzebne lokalnie (nie są w repozytorium — ich autorzy nie podali licencji).

- ClayAmore/ER-Save-Lib: eventflag_bst.txt (mapa blok flagi → pozycja w save'ie)  → docs/data/er-save-lib/
- The Grand Archives: Elden Ring CT (flagi questów i bossów, tylko do build_quests.py) → assets/cache/community/tga/

Użycie (z katalogu projektu):  python tools/fetch_community.py
"""
import io
import os
import sys
import tarfile
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BST_URL = ("https://raw.githubusercontent.com/ClayAmore/ER-Save-Lib/"
           "664ff9e83b7022a6fdc5a8332e8b7b22dce34e0f/src/res/eventflag_bst.txt")
TGA_URL = "https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA/archive/refs/heads/master.tar.gz"
UA = {"User-Agent": "elden-map-setup"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def main():
    bst = os.path.join(ROOT, "docs", "data", "er-save-lib", "eventflag_bst.txt")
    if not os.path.exists(bst):
        os.makedirs(os.path.dirname(bst), exist_ok=True)
        data = get(BST_URL)
        assert data.count(b"\n") > 10000, "nieoczekiwana zawartość eventflag_bst.txt"
        open(bst, "wb").write(data)
        print("pobrano", os.path.relpath(bst, ROOT))
    else:
        print("jest już", os.path.relpath(bst, ROOT))

    tga = os.path.join(ROOT, "assets", "cache", "community", "tga")
    if not os.path.isdir(os.path.join(tga, "Elden-Ring-CT-TGA-master")):
        os.makedirs(tga, exist_ok=True)
        print("pobieram tabelę The Grand Archives (kilkadziesiąt MB)…")
        with tarfile.open(fileobj=io.BytesIO(get(TGA_URL)), mode="r:gz") as tf:
            safe = [m for m in tf.getmembers() if not (m.name.startswith("/") or ".." in m.name.split("/"))]
            tf.extractall(tga, members=safe, filter="data")
        print("rozpakowano do", os.path.relpath(tga, ROOT))
    else:
        print("jest już tabela TGA")


if __name__ == "__main__":
    sys.exit(main())
