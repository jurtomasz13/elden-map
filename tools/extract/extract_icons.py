"""Ikony przedmiotów, ekrany ładowania i spis przedmiotów (polskie nazwy z gry).

Wynik:
  assets/cache/icons/<iconId>.dds, assets/cache/loading/<n>.dds  (potem build_icons.mjs -> PNG)
  assets/data/items.json   przedmioty: kategoria, id, nazwa (PL), iconId, DLC, rodzaj (`kind`, item_category z extract_world.py); ten sam przedmiot pod kilkoma
                           numerami (pusta i pełna flaszka, odnowiona wielka runa, kopie notatek) to jeden wpis,
                           pozostałe numery w `alt_ids`; przedmioty moda Seamless Coop
                           (gdy jest w folderze gry): nazwy nasze, opisy z jego pliku locale
  assets/data/bosses.json  wizerunki (remembrances) bossów -> iconId
  assets/cache/mapicons/   atlasy ikon miejsc na mapie + layout.json (potem build_icons.mjs -> assets/map/icons)
Ikony z /menu/low/00_solo (512 px, MENU_Knowledge_<iconId>); pola iconId w parametrach ustalone
empirycznie (patrz docs/08-assets.md).
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import bhd  # noqa: E402
import formats as F  # noqa: E402
import params as P  # noqa: E402
from extract_world import item_category  # noqa: E402

# (param, FMG z nazwami, offset u16 iconId, kategoria)
ITEM_TABLES = [
    ("EquipParamGoods", "GoodsName", 0x30, "goods"),
    ("EquipParamWeapon", "WeaponName", 0xBE, "weapon"),
    ("EquipParamProtector", "ProtectorName", 0xA6, "armor"),
    ("EquipParamAccessory", "AccessoryName", 0x26, "talisman"),
    ("EquipParamGem", "GemName", 0x34, "ash_of_war"),
]
# Wizerunki (remembrances) -> boss (nazwa EN dla dopasowania z danymi backendu)
REMEMBRANCE_BOSS = {
    2950: "Godrick the Grafted", 2951: "Starscourge Radahn", 2952: "Morgott, the Omen King", 2953: "Rykard, Lord of Blasphemy",
    2954: "Malenia, Blade of Miquella", 2955: "Mohg, Lord of Blood", 2956: "Maliketh, the Black Blade", 2957: "Godfrey, First Elden Lord",
    2958: "Dragonlord Placidusax", 2959: "Rennala, Queen of the Full Moon", 2960: "Lichdragon Fortissax", 2961: "Fire Giant",
    2962: "Regal Ancestor Spirit", 2963: "Elden Beast", 2964: "Astel, Naturalborn of the Void",
    2002900: "Commander Gaius", 2002901: "Messmer the Impaler", 2002902: "Scadutree Avatar", 2002903: "Rellana, Twin Moon Knight",
    2002904: "Romina, Saint of the Bud", 2002905: "Divine Beast Dancing Lion", 2002907: "Promised Consort Radahn",
    2002908: "Midra, Lord of Frenzied Flame", 2002909: "Metyr, Mother of Fingers", 2002910: "Putrescent Knight",
}

# Przedmioty moda Seamless Coop: identyfikatory z ersc.dll (stałe przy kluczach tekstów), klucze tekstów
# z SeamlessCoop/locale/english.json, polskie nazwy nasze (mod nie ma polskich tekstów)
SEAMLESS = {
    8380001: ("HOSTINGITEM", "Maleńki wielki garnek"), 8380002: ("JOININGITEM", "Wizerunek Malenii"),
    8380003: ("BREAKINITEM", "Sworzeń śmiałka"), 8380004: ("LEAVINGITEM", "Mgła rozłąki"),
    8380005: ("GAMERULECHANGEITEM", "Księga zasad sędziego"), 8380006: ("RUNEARCITEM", "Karafka run"),
    8380007: ("ROTITEM01", "Esencja zgnilizny: wycieńczenie"), 8380008: ("ROTITEM02", "Esencja zgnilizny: beznadzieja"),
    8380009: ("ROTITEM03", "Esencja zgnilizny: rozkład"), 8380010: ("ROTITEM04", "Esencja zgnilizny: bezbronność"),
    8380011: ("ROTITEM05", "Esencja zgnilizny: rozpacz"), 8380012: ("DRIEDFINGERITEM", "Zasuszone palce"),
}

# Rzadkość (0 brak/amunicja, 1 zwykły, 2 rzadki, 3 legendarny — złote tło w grze), u8 w wierszu parametru
RARITY_OFF = {"weapon": 0x240, "armor": 0xD7, "talisman": 0x41, "goods": 0x78, "ash_of_war": 0x32}
# Kumulacja statusu w SpEffectParam (i32); broń wskazuje efekty w spEffectBehaviorId0..2 (+0x44/+0x48/+0x4C)
STATUS_OFF = {"poison": 0xCC, "rot": 0xD0, "bleed": 0xD4, "death": 0xD8, "frost": 0x1A8, "sleep": 0x338, "madness": 0x33C}


def weapon_status(row, speffects):
    out = {}
    for o in (0x44, 0x48, 0x4C):
        sp = speffects.get(struct.unpack_from("<i", row, o)[0])
        if not sp:
            continue
        for k, so in STATUS_OFF.items():
            v = struct.unpack_from("<i", sp, so)[0]
            if 0 < v < 1000:
                out[k] = out.get(k, 0) + v
    return out


def item_stats(cat, rid, row, magic, speffects=None):
    """Statystyki z parametrów (offsety ustalone na znanych przedmiotach — docs/08-assets.md)."""
    f = lambda o: round(struct.unpack_from("<f", row, o)[0], 2)
    h = lambda o: struct.unpack_from("<H", row, o)[0]
    if cat == "weapon":
        return {"weight": f(0x10), "class": h(0x1A6),          # wepType: 1 sztylet, 3 miecz prosty, 13 katana… (docs/08)
                "attack": {"phys": h(0xC8), "magic": h(0xCA), "fire": h(0xCC), "lightning": h(0xCE), "holy": h(0x18C)},
                "scaling": {"str": f(0x24), "dex": f(0x28), "int": f(0x2C), "fai": f(0x30), "arc": f(0x19C)},
                "requires": {"str": row[0xF2], "dex": row[0xF3], "int": row[0xF4], "fai": row[0xF5], "arc": row[0x195]},
                "status": weapon_status(row, speffects or {})}
    if cat == "armor":
        cut = lambda o: round((1 - struct.unpack_from("<f", row, o)[0]) * 100, 1)
        return {"weight": f(0x24), "slot": row[0xD6],          # 0 głowa, 1 tułów, 2 ręce, 3 nogi
                "absorb": {"phys": cut(0xE4), "slash": cut(0xE8), "strike": cut(0xEC), "pierce": cut(0xF0),
                           "magic": cut(0xF4), "fire": cut(0xF8), "lightning": cut(0xFC), "holy": cut(0x11C)}}
    if cat == "goods" and rid in magic:
        m = magic[rid]
        return {"fp": struct.unpack_from("<h", m, 0x10)[0], "requires": {"int": m[0x22], "fai": m[0x23]}}
    return None


def seamless_items():
    """Catalog entries for the Seamless Coop items, when the mod is installed (descriptions from its locale file)."""
    path = os.path.join(bhd.GAME_DIR, "SeamlessCoop", "locale", "english.json")
    if not os.path.exists(path):
        print("Seamless Coop: brak moda w folderze gry, pomijam jego przedmioty")
        return []
    texts = json.load(open(path, encoding="utf-8"))
    return [{"category": "goods", "id": rid, "name": pl, "name_en": texts[f"MODGOODSNAME_{key}"], "icon": -1, "dlc": False,
             "info": texts[f"MODGOODSDESC_{key}"], "rarity": None, "kind": "seamless", "stats": None}
            for rid, (key, pl) in SEAMLESS.items()]


def map_icons(out_dir):
    """Ikony miejsc na mapie świata: atlasy SB_MapCursor* z /menu/hi/01_common (DDS) i współrzędne wycinków
    MENU_MAP_<id> z plików .layout (XML) → assets/cache/mapicons/<atlas>.dds + layout.json {id: [atlas, x, y, w, h]}."""
    os.makedirs(out_dir, exist_ok=True)
    _, tpf = A.find("/menu/hi/01_common.tpf.dcx")
    atlases = {n: d for n, d, _ in F.tpf(tpf) if n.startswith("SB_MapCursor")}
    for n, d in atlases.items():
        with open(os.path.join(out_dir, n + ".dds"), "wb") as f:
            f.write(d)
    _, bnd = A.find("/menu/hi/01_common.sblytbnd.dcx")
    layout = {}
    for _, n, d in F.bnd4(bnd):
        atlas = os.path.basename(n.replace("\\", "/")).removesuffix(".layout")
        if atlas in atlases:
            for m in re.finditer(r'MENU_MAP_(\d+)\.png" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', d.decode("utf-8")):
                layout[int(m.group(1))] = [atlas, *map(int, m.groups()[1:])]
    with open(os.path.join(out_dir, "layout.json"), "w", encoding="utf-8") as f:
        json.dump(layout, f)
    return len(layout)


def main():
    root = A.ROOT
    icon_dir = os.path.join(root, "assets", "cache", "icons")
    load_dir = os.path.join(root, "assets", "cache", "loading")
    data_dir = os.path.join(root, "assets", "data")
    for d in (icon_dir, load_dir, data_dir):
        os.makedirs(d, exist_ok=True)

    ps = P.load_params()
    magic = dict(P.rows(ps["Magic"])[0])
    speffects = dict(P.rows(ps["SpEffectParam"])[0])
    texts = P.load_texts("polpl")
    texts_en = P.load_texts("engus")
    items = []
    for param, fmg, off, cat in ITEM_TABLES:
        rows, _ = P.rows(ps[param])
        base, dlc = texts.get(fmg, {}), {**texts.get(fmg + "_dlc01", {}), **texts.get(fmg + "_dlc02", {})}
        en = {**texts_en.get(fmg, {}), **texts_en.get(fmg + "_dlc01", {}), **texts_en.get(fmg + "_dlc02", {})}
        seen = {}
        for rid, row in rows:
            name = (dlc.get(rid) or base.get(rid) or "").strip()
            if not name or name.startswith("[ERROR]"):
                continue
            if cat == "weapon" and rid % 10000:        # pomijamy warianty ulepszeń/nasyceń
                continue
            # the same item under several ids (e.g. multiplayer fingers 100/170, restored great runes): one catalog
            # entry, the other ids kept so the save still matches it
            key = (name, en.get(rid, ""))
            if key in seen:
                seen[key].setdefault("alt_ids", []).append(rid)
                continue
            info_fmg = fmg.replace("Name", "Info")
            info = ({**texts.get(info_fmg, {}), **texts.get(info_fmg + "_dlc01", {}), **texts.get(info_fmg + "_dlc02", {})}.get(rid) or "").strip()
            seen[key] = {"category": cat, "id": rid, "name": name, "name_en": en.get(rid, ""),
                         "icon": struct.unpack_from("<H", row, off)[0], "dlc": rid in dlc,
                         "info": info if info and not info.startswith("[ERROR]") else None,
                         "rarity": row[RARITY_OFF[cat]] if cat in RARITY_OFF else None,
                         # EquipParamGoods +0x3E goods type (7/8 spirit ashes, 5/17 sorceries…), see docs/10
                         "kind": item_category(cat, rid, row[0x3E] if cat == "goods" else None, name),
                         "stats": item_stats(cat, rid, row, magic, speffects)}
            if seen[key]["kind"] in ("golden_rune", "remembrance"):    # EquipParamGoods +0x14: runes gained on use
                seen[key]["runes"] = struct.unpack_from("<i", row, 0x14)[0]
            items.append(seen[key])
    items += seamless_items()                    # ikona -1: dostają wspólną ikonę kategorii niżej
    goods_icon = {it["id"]: it["icon"] for it in items if it["category"] == "goods"}
    bosses = [{"remembrance_id": gid, "boss_en": boss, "icon": goods_icon.get(gid),
               "remembrance": next((it["name"] for it in items if it["id"] == gid and it["category"] == "goods"), None)}
              for gid, boss in REMEMBRANCE_BOSS.items()]
    with open(os.path.join(data_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=0)
    with open(os.path.join(data_dir, "bosses.json"), "w", encoding="utf-8") as f:
        json.dump(bosses, f, ensure_ascii=False, indent=1)
    used = {it["icon"] for it in items}

    _, bhd = A.find("/menu/low/00_solo.tpfbhd")
    _, bdt = A.find("/menu/low/00_solo.tpfbdt")
    n_icons = n_load = 0
    for fid, name, off, size, _ in F.bxf4_entries(bhd, len(bdt)):
        m = re.search(r"MENU_(Knowledge|Load)_(\d+)\.tpf", name)
        if not m:
            continue
        kind, num = m.group(1), int(m.group(2))
        if kind == "Knowledge" and num not in used:
            continue
        (_, dds, _), = F.tpf(A.undcx(bdt[off:off + size]))[:1]
        target = os.path.join(icon_dir if kind == "Knowledge" else load_dir, f"{num}.dds")
        with open(target, "wb") as f:
            f.write(dds)
        n_icons += kind == "Knowledge"
        n_load += kind == "Load"
    # ikony, których nie ma w archiwach menu (np. część popiołów wojny) → wspólna ikona kategorii, jak w grze
    have = {int(f[:-4]) for f in os.listdir(icon_dir) if f.endswith(".dds")}
    fixed = 0
    for cat in {i["category"] for i in items}:
        ok = [i["icon"] for i in items if i["category"] == cat and i["icon"] in have]
        common = max(set(ok), key=ok.count) if ok else None
        for i in items:
            if i["category"] == cat and i["icon"] not in have and common is not None:
                i["icon"], i["icon_fallback"] = common, True
                fixed += 1
    with open(os.path.join(data_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=0)
    n_map = map_icons(os.path.join(root, "assets", "cache", "mapicons"))
    print(f"przedmioty {len(items)}, ikony {n_icons} (z {len(used)} używanych), ikony miejsc na mapie {n_map}, ekrany ładowania {n_load}, "
          f"zastępcze ikony: {fixed}")


if __name__ == "__main__":
    main()
