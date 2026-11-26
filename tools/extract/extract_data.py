"""Dane łask (miejsc łaski) z BonfireWarpParam + przeliczenie na piksele mapy.

Wynik: assets/data/graces.json, assets/data/map_transform.json
Przekształcenie świat -> piksele L0 (10496 x 10496, y od góry), dopasowane do kształtu lądu (±~100 m):
  px = gx*256 + x + 128 - OX
  py = 10496 - (gz*256 + z + 128 - OZ)
gdzie gx/gz = numer komórki siatki mapy m60/m61, x/z = pozycja lokalna w komórce.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import msb  # noqa: E402
import params as P  # noqa: E402

TRANSFORM = {
    # Kafle L0 mapy = komórki siatki świata, ten sam wzór dla obu map: ox = 28·256, oz = 24·256 — sprawdzone
    # w pełnym przybliżeniu na mostach, bramach, kościołach, fortach i wieżach (2026-11-25). Wcześniejsze stałe
    # z dopasowania zgrubnego: M00 oz 6112 (32 px za wysoko), M10 ox 7008 / oz 6048 (160 px na wschód, 96 px na północ).
    "M00": {"area": 60, "ox": 7168, "oz": 6144, "size": 10496, "name": "Ziemie Pomiędzy"},
    "M10": {"area": 61, "ox": 7168, "oz": 6144, "size": 10496, "name": "Królestwo Cienia"},
}


def to_map(area, gx, gz, x, z):
    for key, t in TRANSFORM.items():
        if t["area"] == area:
            return key, round(gx * 256 + x + 128 - t["ox"], 1), round(t["size"] - (gz * 256 + z + 128 - t["oz"]), 1)
    return None, None, None


DLC_AREAS = {20, 21, 22, 25, 28, 40, 41, 42, 43, 61}


def menu_texts(lang="polpl"):
    """GR_MenuText (nazwy zakładek i podkategorii menu podróży)."""
    import formats as F
    out = {}
    for f in ("menu", "menu_dlc01", "menu_dlc02"):
        r = A.find(f"/msg/{lang}/{f}.msgbnd.dcx")
        if not r:
            continue
        for _, name, data in F.bnd4(r[1]):
            if name.split("\\")[-1].startswith("GR_MenuText"):
                out.update({k: v for k, v in F.fmg(data).items() if v})
    return out


def warp_regions(ps, lang="polpl"):
    """Podkategoria menu podróży -> (kraina = nazwa zakładki, podregion = nazwa podkategorii).

    BonfireWarpSubCategoryParam: +0x04 tekst (GR_MenuText), +0x08 u16 id zakładki, +0x0A u16 kolejność.
    BonfireWarpTabParam: +0x04 tekst. (Łaska: BonfireWarpParam +0x14 = id podkategorii.)
    """
    menu = menu_texts(lang)
    tabs = {rid: (menu.get(struct.unpack_from("<i", r, 4)[0]) or "").strip() or None
            for rid, r in P.rows(ps["BonfireWarpTabParam"])[0]}
    subs = {}
    for rid, r in P.rows(ps["BonfireWarpSubCategoryParam"])[0]:
        text, tab = struct.unpack_from("<iH", r, 4)
        subs[rid] = {"tab": tab, "region": (tabs.get(tab) or "").strip() or None,
                     "subregion": (menu.get(text) or "").strip() or None}
    return tabs, subs


def main():
    data_dir = os.path.join(A.ROOT, "assets", "data")
    os.makedirs(data_dir, exist_ok=True)
    texts = P.load_texts("polpl")
    places = {**texts.get("PlaceName", {}), **texts.get("PlaceName_dlc01", {}), **texts.get("PlaceName_dlc02", {})}
    ps = P.load_params()
    _, subs = warp_regions(ps)
    rows, _ = P.rows(ps["BonfireWarpParam"])
    graces = []
    for rid, r in rows:
        flag, entity = struct.unpack_from("<iI", r, 4)
        if not flag:
            continue
        area, gx, gz = r[0x20], r[0x21], r[0x22]
        x, y, z = struct.unpack_from("<3f", r, 0x24)
        mp, px, py = to_map(area, gx, gz, x, z)
        sub = subs.get(struct.unpack_from("<i", r, 0x14)[0], {})   # +0x14 = podkategoria menu podróży
        graces.append({"id": rid, "flag": flag, "entity": entity,
                       "name": places.get(struct.unpack_from("<i", r, 0x30)[0]),
                       "region": sub.get("region"), "subregion": sub.get("subregion"),
                       "map_id": msb.map_id(area, gx, gz), "pos": [round(x, 2), round(y, 2), round(z, 2)],
                       "map": mp, "px": px, "py": py, "dlc": area in DLC_AREAS})
    with open(os.path.join(data_dir, "graces.json"), "w", encoding="utf-8") as f:
        json.dump(graces, f, ensure_ascii=False, indent=0)
    with open(os.path.join(data_dir, "map_transform.json"), "w", encoding="utf-8") as f:
        json.dump(TRANSFORM, f, ensure_ascii=False, indent=1)
    print("łaski:", len(graces), "na mapach świata:", sum(1 for g in graces if g["map"]))


if __name__ == "__main__":
    main()
