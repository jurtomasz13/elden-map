"""Fragmenty mapy jak w grze: które części mapy odsłania każdy zebrany fragment mapy.

Gra trzyma każdy kafel mapy (L0, 256 px) w wariantach: bity w nazwie = zebrane fragmenty, które go dotyczą
(MENU_MapTile_M00_L0_x_y_<bity>), wariant 0 to pusta, ciemna faktura. Bit i = i-ty wiersz WorldMapPieceParam danej
mapy (M00: wiersze 0–69, M01: 100–199, M10: 1000–1069): +0x04 flaga zebrania mapy (62010 = Pogrobno, zachód),
+0x08 4×f32 obszar mapy do oglądania [lewo, prawo, góra, dół] w pikselach mapy (+0x18 druga flaga 63xxx —
w save'ach nigdy nieustawiona, pomijamy). Strona: obszar mapy = otwarte fragmenty + okolice, w których byłeś;
grafika — tylko tam, gdzie zebrana mapa (reszta: pusta faktura, jak w grze).

Tu zapisujemy dla każdego kafla i bitu parę wariantów różniących się tylko tym bitem (z bitem / bez niego);
build_map_pieces.mjs porównuje je piksel po pikselu i składa maskę zasięgu fragmentów (assets/map/<M>/pieces.png).
Wynik: assets/cache/map/pieces/*.dds + manifest.json, assets/data/map_pieces.json (flagi fragmentów każdej mapy).
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import formats as F  # noqa: E402
import params as P  # noqa: E402

MAPS = {"00": (0, 71), "01": (100, 200), "10": (1000, 1071)}   # mapa -> zakres wierszy WorldMapPieceParam
# wiersze 70 / 1070 (flagi 62000 / 62002) to obszar startowy (Cmentarzysko Rozbitków, początek DLC) — bez bitu kafli
LEVEL = 0


def piece_flags():
    """Fragmenty każdej mapy (kolejność = bity wariantów kafli):
    f — flaga otwarcia (zebrana mapa; 62000/62002 — obszar startowy, ustawiona od początku gry),
    r — obszar mapy, który da się oglądać po otwarciu fragmentu [lewo, prawo, góra, dół] w pikselach mapy."""
    rows, _ = P.rows(P.load_params()["WorldMapPieceParam"])
    out = {}
    for mp, (lo, hi) in MAPS.items():
        out["M" + mp] = [{"f": struct.unpack_from("<I", r, 4)[0], "r": [round(v, 1) for v in struct.unpack_from("<4f", r, 8)]}
                         for rid, r in sorted(rows) if lo <= rid < hi]
    return out


def main():
    out_dir = os.path.join(A.ROOT, "assets", "cache", "map", "pieces")
    os.makedirs(out_dir, exist_ok=True)
    _, mask_bnd = A.find("/menu/71_maptile.mtmskbnd.dcx")
    masks = {}
    for _, name, data in F.bnd4(mask_bnd):
        m = re.search(r"MapTile_M(\d+)\.mtmsk", name)
        masks[m.group(1)] = {int(i): int(k) for e, i, k in
                             re.findall(r'exists="(\d)" id="(\d+)" mask="(\d+)"', data.decode()) if e == "1"}

    _, bhd = A.find("/menu/71_maptile.tpfbhd")
    _, bdt = A.find("/menu/71_maptile.tpfbdt")
    variants = {}                                   # (mapa, x, y) -> {bity: (off, size)}
    for _, name, off, size, _ in F.bxf4_entries(bhd, len(bdt)):
        m = re.search(r"MENU_MapTile_M(\d+)_L(\d)_(\d+)_(\d+)_([0-9A-Fa-f]+)", name)
        if not m or int(m.group(2)) != LEVEL or m.group(1) not in MAPS:
            continue
        variants.setdefault((m.group(1), int(m.group(3)), int(m.group(4))), {})[int(m.group(5), 16)] = (off, size)

    def export(mp, x, y, bits):
        p = os.path.join(out_dir, f"M{mp}_{x}_{y}_{bits:x}.dds")
        if not os.path.exists(p):
            off, size = variants[(mp, x, y)][bits]
            (_, dds, _fmt), = F.tpf(A.undcx(bdt[off:off + size]))
            with open(p, "wb") as f:
                f.write(dds)
        return p

    manifest, blank = {}, None
    for (mp, x, y), vs in sorted(variants.items()):
        mask = masks.get(mp, {}).get(LEVEL * 10000 + x * 100 + y, 0)
        if not mask:
            continue                                # kafel niezależny od fragmentów — zawsze taki sam
        pairs = {}
        for i in range(32):
            if not mask >> i & 1:
                continue
            # para wariantów różniących się tylko bitem i — najprostsza (najmniej innych bitów)
            cands = sorted((v for v in vs if v >> i & 1 and (v ^ (1 << i)) in vs), key=lambda v: bin(v).count("1"))
            if cands:
                v = cands[0]
                pairs[i] = [export(mp, x, y, v), export(mp, x, y, v ^ (1 << i))]
        if pairs:
            manifest.setdefault("M" + mp, []).append({"x": x, "y": y, "mask": mask, "pairs": pairs})
        if blank is None and 0 in vs:
            blank = export(mp, x, y, 0)
    manifest["_blank"] = blank
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f)
    flags = piece_flags()
    data_dir = os.path.join(A.ROOT, "assets", "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "map_pieces.json"), "w", encoding="utf-8") as f:
        json.dump(flags, f)
    for k, v in manifest.items():
        if not k.startswith("_"):
            print(k, len(v), "kafli zależnych od fragmentów,", len(flags.get(k, [])), "fragmentów")


if __name__ == "__main__":
    main()
