"""Dodatkowe dane świata dla backendu, wprost z plików gry (tylko odczyt, przez tools/extract):

  backend/data/world_extras.json
    play_regions   {id: {name, region, subregion, map_id, kind}}  — nazwy dla `regions_unlocked` z save'a
    boss_positions {flag: {map_id, x, y, z, source}}              — pozycja bossa (wróg w MSB o EntityID = flaga)
    legacy_conv    [[src_map, sx, sy, sz, dst_map, dx, dy, dz], ...] — WorldMapLegacyConvParam (loch -> świat)
    transform      map_transform (piksele mapy świata)
    warp_tabs / warp_subcategories — krainy i podregiony menu podróży

Użycie (z katalogu projektu; wymaga zainstalowanej gry, tak jak tools/extract/run_all.py):
    python backend/tools/extract_world_extras.py
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "extract"))

import extract_data as XD  # noqa: E402
import msb  # noqa: E402
from extract_world import World, maps  # noqa: E402
import params as P  # noqa: E402

OUT = os.path.join(ROOT, "backend", "data", "world_extras.json")
ASSETS = os.path.join(ROOT, "assets", "data")


def load_json(fn):
    p = os.path.join(ASSETS, fn)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def find_arena(regions, p):
    """Region przyzywania ducha („バディ…”) zawierający pozycję bossa (margines 2 m), a gdy żaden — najbliższy < 40 m."""
    import math
    import sys as _s
    _s.path.insert(0, os.path.join(ROOT, "backend"))
    from erbackend.worldmap import inside_shape
    buddy = [r for r in regions if "バディ" in r["name"] and r["dims"]]
    hit = next((r for r in buddy if inside_shape(region_shape(r), p, 2.0)), None)
    match = "inside"
    if hit is None:
        near = min(buddy, key=lambda r: math.dist(r["pos"], p), default=None)
        if near is None or math.dist(near["pos"], p) >= 40:
            return None
        hit, match = near, "near"
    return {**region_shape(hit), "region_name": hit["name"], "boss_in_region": match == "inside"}


def region_shape(r):
    return {"shape": r["shape"], "x": round(r["pos"][0], 2), "y": round(r["pos"][1], 2), "z": round(r["pos"][2], 2),
            "rot_y": round(r["rot_y"], 2), "dims": [round(v, 2) for v in r["dims"]]}


# Mapy, dla których gra nie podaje nazwy/krainy wprost (brak łaski, miejsca i PlaceName AABB00):
#  m12_08 / m12_09 — areny Ducha przodka i Ducha królewskiego przodka (bossowie na tych mapach, flagi 12080800 /
#    12090800); nazwa miejsca z PlaceName 6654604 „Świątynia Poroża” (Hallowhorn Grounds), kraina wg menu podróży
#    (Rzeka Siofra / podkategoria Nokron). m45_xx — koloseów nie ma w menu podróży; kraina wg położenia w grze.
MAP_OVERRIDES = {
    "m12_08": {"name": 6654604, "region": "Rzeka Siofra", "subregion": "Rzeka Siofra"},
    "m12_09": {"name": 6654604, "region": "Rzeka Siofra", "subregion": "Nokron, Wieczne Miasto"},
    "m45_00": {"region": "Leyndell, królewska stolica", "subregion": "Leyndell, królewska stolica"},
    "m45_01": {"region": "Pogrobno", "subregion": "Pogrobno"},
    "m45_02": {"region": "Caelid", "subregion": "Caelid"},
}


def nearest_grace_on_tile(graces, area, gx, gz):
    """Łaska z krainą na tym samym (albo najbliższym) kaflu świata."""
    best, bd = None, None
    for g in graces:
        if not g.get("region"):
            continue
        try:
            a, x, z = (int(v) for v in g["map_id"][1:].split("_")[:3])
        except ValueError:
            continue
        if a != area:
            continue
        d = abs(x - gx) + abs(z - gz)
        if bd is None or d < bd:
            best, bd = g, d
    return best


def play_region_names(ps, tabs, subs, graces, pois, conv, places):
    """PlayRegionParam ID -> nazwa. Struktura ID (ustalona na danych i save'ach):
      60 ...       — Ziemie Pomiędzy ogólnie
      61–65 xx yyy — Ziemie Pomiędzy: kraina = zakładka AA*1000, podregion AA*1000 + xx (6101000 -> Burzowe Wzgórze)
      68/69 xx yyy — Królestwo Cienia: kraina = zakładka AA*100, podregion = ID // 1000 (6820000 -> Zamek Ensis)
      AA BB yyy    — lochy/legacy: mapa mAA_BB; nazwa z miejsc (WorldMapPoint), PlaceName AABB00 albo łaski na mapie
    """
    by_map_grace: dict[str, list] = {}
    for g in graces:
        by_map_grace.setdefault(g["map_id"][:6], []).append(g)
    poi_by_map = {}
    for p in pois:
        # without the game's character markers (name null) and the mausoleums added by extract_landmarks.py (they move)
        if p.get("map_id") and p.get("name") and "walking" not in p:
            poi_by_map.setdefault(p["map_id"][:6], p)
    out = {}
    for rid, _ in P.rows(ps["PlayRegionParam"])[0]:
        if rid < 1000000:
            continue
        aa = rid // 100000
        e = {"name": None, "region": None, "subregion": None, "map_id": None, "kind": None}
        if aa == 60:
            e.update(kind="overworld", map_id="m60", name=XD.TRANSFORM["M00"]["name"])
        elif 61 <= aa <= 65:
            tab = aa * 1000
            sub = subs.get(tab + (rid // 1000) % 100)
            e.update(kind="overworld", region=tabs.get(tab), subregion=sub["subregion"] if sub else None, map_id="m60")
            e["name"] = e["subregion"] or e["region"]
        elif aa in (68, 69):
            tab = aa * 100
            sub = subs.get(rid // 1000)
            e.update(kind="overworld", region=tabs.get(tab), subregion=sub["subregion"] if sub else None, map_id="m61")
            e["name"] = e["subregion"] or e["region"]
        else:
            bb = (rid // 1000) % 100
            m6 = f"m{aa:02d}_{bb:02d}"
            gs = by_map_grace.get(m6, [])
            poi = poi_by_map.get(m6)
            tab_sub = subs.get(aa * 1000 + bb * 10) or subs.get(aa * 1000)   # np. 10000 Stormveil, 12020 Nokron
            e.update(kind="dungeon", map_id=f"{m6}_00_00")
            e["region"] = (gs[0].get("region") if gs else None) or (tab_sub or {}).get("region")
            e["subregion"] = (gs[0].get("subregion") if gs else None) or (tab_sub or {}).get("subregion")
            e["name"] = ((poi or {}).get("name") or places.get(aa * 10000 + bb * 100)   # PlaceName AABB00 = nazwa mapy
                         or (gs[0]["name"] if gs else None) or e["subregion"])
            if not e["region"]:                         # loch bez łaski: kraina wg kafla wejścia
                dst = next((c[4] for c in conv if c[0].startswith(m6 + "_") and c[4][:3] in ("m60", "m61")), None)
                if dst:
                    a, gx, gz = (int(v) for v in dst[1:].split("_")[:3])
                    g = nearest_grace_on_tile(graces, a, gx, gz)
                    if g:
                        e["region"], e["subregion"] = g["region"], g.get("subregion")
            ov = MAP_OVERRIDES.get(m6)
            if ov:                                      # mapy bez nazwy/krainy w danych — opis w MAP_OVERRIDES
                e.update({k: (places.get(v) if k == "name" and isinstance(v, int) else v) for k, v in ov.items()})
            if not e["name"]:
                e["name"] = f"Nienazwany obszar {m6}"
                e["named"] = False
        out[rid] = e
    return out


def main():
    t0 = time.time()
    ps = P.load_params()
    tabs, subs = XD.warp_regions(ps)
    tp = P.load_texts("polpl")
    places = {**tp.get("PlaceName", {}), **tp.get("PlaceName_dlc01", {}), **tp.get("PlaceName_dlc02", {})}
    graces = load_json("graces.json")
    pois = load_json("pois.json")
    bosses = load_json("bosses_all.json")
    boss_flags = {b["id"] for b in bosses}       # wiersz GameAreaParam = encja bossa w pliku mapy

    conv = [[msb.map_id(*src), *[round(v, 2) for v in sp], msb.map_id(*dst), *[round(v, 2) for v in dp]]
            for src, sp, dst, dp, _ in World(ps).conv]

    # GameAreaParam: +0x48 float[3] pozycja, +0x54 area/gx/gz (bywa mylące — tylko zapas, gdy brak wroga w MSB).
    # Uwaga: +0x3C to NIE jest PlayRegion areny (wartości niezgodne z położeniem bossów).
    ga = {}
    for rid, r in P.rows(ps["GameAreaParam"])[0]:
        if rid >= 1000:
            ga[rid] = {"pos": struct.unpack_from("<3f", r, 0x48), "map": (r[0x54], r[0x55], r[0x56])}

    # pozycje bossów z plików map: wróg o EntityID = flaga pokonania
    found = {}
    for path, _tile, mid, m in maps():
        for p in m["parts"]:
            if p["type"] in ("enemy", "dummy_enemy") and p["entity"] in boss_flags and p["entity"] not in found:
                found[p["entity"]] = {"map_id": mid, "file": path, "x": round(p["pos"][0], 2), "y": round(p["pos"][1], 2),
                                      "z": round(p["pos"][2], 2), "source": "msb"}
    boss_positions = {}
    for flag in sorted(boss_flags):
        g = ga.get(flag, {})
        pos = found.get(flag)
        if pos is None and g and g["map"][0]:
            pos = {"map_id": msb.map_id(*g["map"]), "x": round(g["pos"][0], 2), "y": round(g["pos"][1], 2),
                   "z": round(g["pos"][2], 2), "source": "game_area_param"}
        if pos:
            boss_positions[flag] = pos

    # areny: region „バディ…” (obszar przyzywania popiołów ducha w walce z bossem) z pliku mapy bossa
    # (boss z pliku większej skali _01/_02 ma arenę w tym samym pliku, nie w kaflu _00)
    reg_cache: dict[str, list] = {}
    for flag, pos in boss_positions.items():
        path = pos.pop("file", f"/map/mapstudio/{pos['map_id']}.msb.dcx")
        if path not in reg_cache:
            m = msb.load(path)
            reg_cache[path] = m["regions"] if m else []
        a = find_arena(reg_cache[path], (pos["x"], pos["y"], pos["z"]))
        if a:
            pos["arena"] = a

    regions = play_region_names(ps, tabs, subs, graces, pois, conv, places)
    out = {
        "_meta": {"generated_by": "backend/tools/extract_world_extras.py",
                  "source": "pliki gry (regulation.bin, MSB, GR_MenuText, PlaceName)",
                  "boss_positions": f"{sum(1 for v in boss_positions.values() if v['source'] == 'msb')} z MSB, "
                                    f"{sum(1 for v in boss_positions.values() if v['source'] != 'msb')} z GameAreaParam, "
                                    f"{len(boss_flags) - len(boss_positions)} bez pozycji; areny z regionu MSB: "
                                    f"{sum(1 for v in boss_positions.values() if v.get('arena'))}",
                  "play_regions": f"{len(regions)}, bez nazwy z gry: {sum(1 for v in regions.values() if v.get('named') is False)}"},
        "play_regions": {str(k): v for k, v in regions.items()},
        "boss_positions": {str(k): v for k, v in boss_positions.items()},
        "legacy_conv": conv,
        "transform": XD.TRANSFORM,
        "warp_tabs": {str(k): v for k, v in tabs.items()},
        "warp_subcategories": {str(k): v for k, v in subs.items()},
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(out["_meta"]["boss_positions"], "|", out["_meta"]["play_regions"], f"| konwersje {len(conv)}",
          f"| {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
