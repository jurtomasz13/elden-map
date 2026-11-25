"""Wyciąga kafle mapy świata (najdokładniejszy poziom L0) w wariancie „pełna mapa”.

Wynik: assets/cache/map/<M>/<x>_<y>.dds (+ manifest.json), potem build_tiles.mjs robi piramidę PNG.
Wariant kafla = bity zebranych fragmentów mapy; pełna mapa to maska z 71_maptile.mtmskbnd
(id maski = poziom*10000 + x*100 + y). Wybieramy wariant równy masce albo jej największy podzbiór.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import formats as F  # noqa: E402

MAPS = ["00", "01", "10", "11"]   # 00 Ziemie Pomiędzy, 01 podziemia, 10 Królestwo Cienia (DLC), 11 podziemia DLC
LEVEL = 0


def popcount(v):
    return bin(v).count("1")


def main():
    out_root = os.path.join(A.ROOT, "assets", "cache", "map")
    _, mask_bnd = A.find("/menu/71_maptile.mtmskbnd.dcx")
    masks = {}
    for _, name, data in F.bnd4(mask_bnd):
        m = re.search(r"MapTile_M(\d+)\.mtmsk", name)
        masks[m.group(1)] = {int(i): int(k) for e, i, k in
                             re.findall(r'exists="(\d)" id="(\d+)" mask="(\d+)"', data.decode()) if e == "1"}

    _, bhd = A.find("/menu/71_maptile.tpfbhd")
    _, bdt = A.find("/menu/71_maptile.tpfbdt")
    best = {}
    for fid, name, off, size, _ in F.bxf4_entries(bhd, len(bdt)):
        m = re.search(r"MENU_MapTile_M(\d+)_L(\d)_(\d+)_(\d+)_([0-9A-Fa-f]+)", name)
        if not m or int(m.group(2)) != LEVEL or m.group(1) not in MAPS:
            continue
        mp, x, y, bits = m.group(1), int(m.group(3)), int(m.group(4)), int(m.group(5), 16)
        mask = masks.get(mp, {}).get(LEVEL * 10000 + x * 100 + y, 0)
        if bits & ~mask:
            continue
        key = (mp, x, y)
        if key not in best or popcount(bits) > best[key][0]:
            best[key] = (popcount(bits), off, size, bits)

    manifest = {}
    for (mp, x, y), (_, off, size, bits) in best.items():
        d = os.path.join(out_root, "M" + mp)
        os.makedirs(d, exist_ok=True)
        (tname, dds, _fmt), = F.tpf(A.undcx(bdt[off:off + size]))
        p = os.path.join(d, f"{x}_{y}.dds")
        with open(p, "wb") as f:
            f.write(dds)
        manifest.setdefault("M" + mp, []).append({"x": x, "y": y, "bits": bits, "file": p})
    with open(os.path.join(out_root, "manifest.json"), "w") as f:
        json.dump(manifest, f)
    for k, v in manifest.items():
        xs, ys = [t["x"] for t in v], [t["y"] for t in v]
        print(k, len(v), "kafli, x", min(xs), "-", max(xs), " y", min(ys), "-", max(ys))


if __name__ == "__main__":
    main()
