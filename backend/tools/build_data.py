"""Generuje backend/data/{bosses,graces,items,quests}.json z docs/data/ct_event_flags.csv
plus ręcznie opisanej listy bossów DLC (flagi pokonania sprawdzone na save'ach użytkownika).

Jeśli istnieją assets/data/{bosses_all,graces,item_locations,quests}.json (dane świata), są
łączone z wpisami z tabeli CE (po fladze). Użycie (z katalogu projektu):
    python backend/tools/build_data.py

Uruchomienie nadpisuje pliki JSON. Ręczne poprawki rób tutaj, nie w JSON-ach.
"""
from __future__ import annotations

import csv
import json
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CSV = os.path.join(ROOT, "docs", "data", "ct_event_flags.csv")
OUT = os.path.join(ROOT, "backend", "data")

SOURCES = {
    "ct-hexinton": {
        "title": "Tabela Cheat Engine Hexinton v8.0.4 (wyciąg w docs/data/ct_event_flags.csv)",
        "url": "https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA",
        "license": "brak jasnej licencji; ID flag to fakty techniczne, używamy lokalnie",
    },
    "save-verified": {
        "title": "Sprawdzone na save'ach użytkownika (7 postaci, 2026-11-23)",
        "note": "Flaga zachowuje się spójnie: ustawiona tylko u postaci, które doszły dalej w DLC; "
                "dla 'verified' flaga mapy (…800/…850) zgadza się z globalną flagą bossa 9xxx/61xxx.",
    },
    "flag-convention": {
        "title": "Konwencja numeracji flag: <blok mapy>800/850/860 = boss mapy pokonany",
        "note": "Użyte, gdy CSV podawało inną flagę z grupy bossa; potwierdzone odczytem save'a.",
    },
    "world-data": {
        "title": "Dane świata wyciągnięte z plików gry (assets/data/*.json, tools/extract/run_all.py)",
        "note": "GameAreaParam (bossowie, flaga pokonania = id wiersza), ItemLotParam_map + MSB map (skarby), "
                "BonfireWarpParam (łaski). Nazwy PL z plików gry. Zweryfikowane na save'ach użytkownika.",
    },
    "game-files": {
        "title": "Pliki gry czytane wprost (backend/tools/extract_world_extras.py -> backend/data/world_extras.json)",
        "note": "Pozycje bossów z plików map (MSB: wróg o EntityID = flaga pokonania), krainy z menu podróży "
                "(BonfireWarpTab/SubCategory + GR_MenuText), nazwy PlayRegion, WorldMapLegacyConvParam.",
    },
    "general-knowledge": {
        "title": "Wiedza ogólna o grze (opisy lokacji i wskazówki dojścia, pisane przez Claude)",
        "note": "Niezweryfikowane ze źródłem — do sprawdzenia w grze.",
    },
    "questpath": {
        "title": "QuestPath (imCioco) — opisy kroków questów, tłumaczenie na polski (tools/extract/quest_steps.py)",
        "url": "https://github.com/imCioco/ER_QuestPath-Lang", "license": "MIT",
    },
}

DLC = "Shadow of the Erdtree"

# id, nazwa, region, lokacja, flaga pokonania, flagi dodatkowe, obowiązkowy, pewność flagi, źródła, notatka
# required: True = potrzebny do ukończenia DLC, False = opcjonalny, None = nie wiem na pewno
V = "verified"
BOSSES = [
    ("divine-beast-dancing-lion", "Divine Beast Dancing Lion", "Gravesite Plain", "Belurat, Tower Settlement",
     20000800, [9140, 61140], None, V, "Boss na końcu osady Belurat (wieża na północ od Gravesite Plain)."),
    ("rellana-twin-moon-knight", "Rellana, Twin Moon Knight", "Gravesite Plain", "Castle Ensis",
     2048440800, [9190, 61190], None, V, "Zamek Ensis na wschodnim krańcu Gravesite Plain; za nim przejście do Scadu Altus."),
    ("messmer-the-impaler", "Messmer the Impaler", "Scadu Altus", "Shadow Keep",
     21010800, [9146, 61146], True, V, "Szczyt Shadow Keep — przez Specimen Storehouse w górę do Dark Chamber Entrance. Daje Messmer's Kindling."),
    ("golden-hippopotamus", "Golden Hippopotamus", "Scadu Altus", "Shadow Keep (brama główna)",
     21000850, [9144, 61144], False, V, "Dziedziniec przed główną bramą Shadow Keep."),
    ("romina-saint-of-the-bud", "Romina, Saint of the Bud", "Rauh Base", "Church of the Bud (Ancient Ruins of Rauh)",
     2044450800, [9160, 61160], True, V, "Ancient Ruins of Rauh, na końcu ruin w Church of the Bud."),
    ("promised-consort-radahn", "Promised Consort Radahn", "Enir Ilim", "Enir Ilim — Gate of Divinity",
     20010800, [9143, 61143], True, V, "Ostatni boss DLC. Po Messmerze i Rominie spal ciernie Messmer's Kindling, wejdź do Enir Ilim i dojdź do Gate of Divinity."),
    ("scadutree-avatar", "Scadutree Avatar", "Scaduview", "Scadutree Base",
     2050480800, [9162, 61162], False, V, "Scaduview (tylne wyjście z Shadow Keep), zejście do Scadutree Base."),
    ("bayle-the-dread", "Bayle the Dread", "Jagged Peak", "Jagged Peak — szczyt",
     2054390800, [9163, 61163], False, V, "Jagged Peak: od Grand Altar of Dragon Communion w górę aż na szczyt."),
    ("midra-lord-of-frenzied-flame", "Midra, Lord of Frenzied Flame", "Abyssal Woods", "Midra's Manse",
     28000800, [9156, 61156], False, V, "Midra's Manse w Abyssal Woods; arena w Discussion Chamber."),
    ("metyr-mother-of-fingers", "Metyr, Mother of Fingers", "Scadu Altus", "Cathedral of Manus Metyr (Finger Birthing Grounds)",
     25000800, [9155, 61155], False, V, "Pod Cathedral of Manus Metyr, w Finger Birthing Grounds."),
    ("putrescent-knight", "Putrescent Knight", "Cerulean Coast", "Stone Coffin Fissure",
     22000800, [9148, 61148], False, V, "Stone Coffin Fissure (wejście od Cerulean Coast); arena Garden of Deep Purple."),
    ("jori-elder-inquisitor", "Jori, Elder Inquisitor", "Abyssal Woods", "Darklight Catacombs",
     2052430800, [9161, 61161], False, V, None),
    ("commander-gaius", "Commander Gaius", "Scadu Altus", "Shadow Keep — tylna brama",
     2049480800, [9164, 61164], False, V, None),
    ("chief-bloodfiend", "Chief Bloodfiend", "Gravesite Plain", "Rivermouth Cave",
     43000800, [9280, 61280], False, V, None),
    ("demi-human-swordsman-onze", "Demi-Human Swordsman Onze", "Gravesite Plain", "Belurat Gaol",
     41000800, [9275, 61275], False, V, None),
    ("lamenter", "Lamenter", "Gravesite Plain", "Lamenter's Gaol",
     41020800, [9277, 61277], False, V, None),
    ("curseblade-labirith", "Curseblade Labirith", "Scadu Altus", "Bonny Gaol",
     41010800, [9276, 61276], False, V, None),
    ("death-knight-fog-rift", "Death Knight (Fog Rift Catacombs)", "Gravesite Plain", "Fog Rift Catacombs",
     40000800, [9270, 61270], False, V, None),
    ("death-knight-scorpion-river", "Death Knight (Scorpion River Catacombs)", "Rauh Base", "Scorpion River Catacombs",
     40010800, [9271, 61271], False, V, None),
    ("ancient-dragon-man", "Ancient Dragon-Man", "Jagged Peak", "Dragon's Pit",
     43010800, [9281, 61281], False, V, None),
    ("ghostflame-dragon-gravesite", "Ghostflame Dragon (Gravesite Plain)", "Gravesite Plain", None,
     2045440800, [], False, "high", None),
    ("knight-of-the-solitary-gaol", "Knight of the Solitary Gaol", "Gravesite Plain", None,
     2046410800, [], False, "high", None),
    ("red-bear", "Red Bear", "Gravesite Plain", None,
     2046450800, [], False, "high", None),
    ("demi-human-queen-marigga", "Demi-Human Queen Marigga", "Gravesite Plain", "Charo's Hidden Grave",
     2046400800, [], False, "high", None),
    ("jagged-peak-drake-rhia", "Jagged Peak Drake (Finger Ruins of Rhia)", "Cerulean Coast", "Finger Ruins of Rhia",
     2049410800, [], False, "high", None),
    ("jagged-peak-drake", "Jagged Peak Drake (Jagged Peak)", "Jagged Peak", None,
     2052400800, [], False, "high", None),
    ("ancient-dragon-senessax", "Ancient Dragon Senessax", "Jagged Peak", None,
     2054390850, [], False, "high", None),
    ("black-knight-edredd", "Black Knight Edredd", "Scadu Altus", "Fort of Reprimand",
     2049430850, [], False, "high", None),
    ("black-knight-garrew", "Black Knight Garrew", "Scadu Altus", None,
     2047450800, [], False, "high", None),
    ("rakshasa", "Rakshasa", "Scadu Altus", None,
     2051440800, [], False, "high", None),
    ("ralva-the-great-red-bear", "Ralva the Great Red Bear", "Scadu Altus", None,
     2049450800, [], False, "high", None),
    ("fallingstar-beast-scaduview", "Fallingstar Beast (Scaduview)", "Scaduview", None,
     2052480800, [], False, "high", None),
    ("tree-sentinel-scaduview", "Tree Sentinel ×2 (Scaduview)", "Scaduview", None,
     2050480860, [], False, "medium", None),
    ("dancer-of-ranah", "Dancer of Ranah", "Cerulean Coast", None,
     2046380800, [], False, "medium", None),
    ("ghostflame-dragon-cerulean", "Ghostflame Dragon (Cerulean Coast)", "Cerulean Coast", None,
     2049430800, [], False, "medium", None),
    ("dryleaf-dane", "Dryleaf Dane", "Scadu Altus", "Moorth Ruins",
     2049442810, [], False, "low", None),
]

BOSS_NOTES = {
    "putrescent-knight": "CSV podaje 22000804; flaga 22000800 wg konwencji, zgodna z 9148 na save'ach.",
    "dancer-of-ranah": "CSV podaje 2046380804 (nieustawiona nawet u postaci z prawie całym DLC); 2046380800 wg konwencji, ustawiona tylko u 'finali'.",
    "ghostflame-dragon-cerulean": "CSV podaje 2049430804/828; 2049430800 wg konwencji, ustawiona tylko u 'finali'. W tym samym bloku jest Edredd (…850) — możliwa pomyłka przypisania.",
    "tree-sentinel-scaduview": "W CSV grupy 'Scadu Altus/Tree Sentinel' i 'Scaduview/Tree Sentinel' mieszają te same flagi; 2050480860 ustawiona tylko u 'finali'.",
    "dryleaf-dane": "Flaga z CSV nie jest ustawiona u żadnej postaci — niepotwierdzona, możliwe że to nie flaga pokonania.",
    "golden-hippopotamus": "Globalne flagi bossa w CSV jako 1144/61144; 9144 też zachowuje się spójnie.",
    "rellana-twin-moon-knight": "Globalne flagi bossa w CSV jako 1190/61190; 9190 też zachowuje się spójnie.",
}

GRACE_NAME_FIX = {
    "Belrat Tower Settlement": "Belurat Tower Settlement",
    "Saduview Cross": "Scaduview Cross",
    "Lamenter's Goall": "Lamenter's Gaol",
    "Recluses River Upstream": "Recluses' River Upstream",
    "Recluses River Downstream": "Recluses' River Downstream",
    "Ensis Moongazing Grounds (Twin Moon Knight)": "Ensis Moongazing Grounds",
}

ITEM_SKIP = {65600: "ustawiona od początku gry u każdej postaci — nie jest podniesieniem przedmiotu",
             65885: "'No Skill' — brak popiołu, nie przedmiot"}


def arena_for(flag: int) -> dict | None:
    """Arena tylko dla małych lochów DLC z jednym bossem (m40 katakumby, m41 więzienia, m43 jaskinie/jamy).

    Flaga mapy AABB0800 -> mapa mAA_BB_00_00. Bez współrzędnych: każda śmierć na tej mapie przed
    pokonaniem bossa liczy się jako próba (także śmierci od zwykłych przeciwników) — stąd pewność 'low'.
    """
    aa, bb = flag // 1_000_000, flag // 10_000 % 100
    if flag >= 100_000_000 or aa not in (40, 41, 43):
        return None
    return {"map_id": f"m{aa}_{bb:02d}_00_00", "x": None, "y": None, "z": None, "radius": None,
            "match": "map", "confidence": "low", "sources": ["flag-convention"]}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def group_parts(g: str) -> list[str]:
    g = g.replace("[ Enable ]/", "").replace("[ World / Npc Flags ]/", "")
    return [p.strip() for p in g.split("/")]


def meta(kind: str, used: list[str], extra: dict | None = None) -> dict:
    m = {"schema_version": 1, "kind": kind, "generated_by": "backend/tools/build_data.py",
         "sources": {k: SOURCES[k] for k in used},
         "confidence_levels": {
             "verified": "dwie niezależne flagi zgadzają się na save'ach albo potwierdzone w grze",
             "high": "flaga z CT + spójne zachowanie na save'ach",
             "medium": "wyprowadzone (konwencja/sprawdzenie save'a), może być pomyłka",
             "low": "niepotwierdzone"}}
    if extra:
        m.update(extra)
    return m


WORLD = os.path.join(ROOT, "assets", "data")

# Bossowie obowiązkowi gry podstawowej (do napisów końcowych) — wiedza ogólna; dopasowanie po name_en.
REQUIRED_BASE_EN = {"Morgott, the Omen King", "Fire Giant", "Godskin Duo", "Sir Gideon Ofnir, the All-Knowing",
                    "Radagon of the Golden Order"}
# po fladze, bo nazwa z GameAreaParam jest niejednoznaczna / obejmuje dwie fazy walki
REQUIRED_BASE_FLAGS = {11050800: "Godfrey w popielatej stolicy = Hoarah Loux (obowiązkowy)",
                       13000800: "wpis 'Beast Clergyman' obejmuje też walkę z Malikethem (obowiązkowy)",
                       19000800: "wpis obejmuje Radagona i Bestię Eldeńską (obowiązkowy)"}
# mapy małych lochów (katakumby, jaskinie, tunele, więzienia DLC): arena = cała mapa, gdy boss jest tam jedyny
DUNGEON_MAP_PREFIXES = ("m30", "m31", "m32", "m40", "m41", "m42", "m43")


DLC_MAP_PREFIXES = ("m20", "m21", "m22", "m25", "m28", "m40", "m41", "m42", "m43", "m61")


def is_dlc_map(map_id: str | None, fallback=False) -> bool:
    """Mapy DLC (Shadow of the Erdtree): m61 + lochy m20–m28, m40–m43. Zgodne z bosses_all/item_locations."""
    return map_id.startswith(DLC_MAP_PREFIXES) if map_id else bool(fallback)


ARENA_RADIUS = 60.0      # m — plama krwi w tym promieniu od miejsca bossa = próba


class Locator:
    """Kraina/podregion punktu = kraina najbliższej łaski (ta sama mapa lokalnie, inaczej przez współrzędne świata)."""

    def __init__(self, graces, worldmap):
        self.wm = worldmap
        self.by_map: dict[str, list] = {}
        self.world: list = []
        for g in graces:
            if not g.get("region") or not g.get("map_id") or not g.get("pos"):
                continue
            self.by_map.setdefault(g["map_id"], []).append(g)
            w = worldmap.world(g["map_id"], *g["pos"]) if worldmap else None
            if w:
                self.world.append((w["area"], w["X"], w["Z"], g))

    def locate(self, map_id, x, y, z):
        same = self.by_map.get(map_id)
        if same:
            return min(same, key=lambda g: (g["pos"][0] - x) ** 2 + (g["pos"][1] - y) ** 2 + (g["pos"][2] - z) ** 2)
        w = self.wm.world(map_id, x, y, z) if self.wm and x is not None else None
        if not w:
            return None
        cands = [c for c in self.world if c[0] == w["area"]]
        if not cands:
            return None
        return min(cands, key=lambda c: (c[1] - w["X"]) ** 2 + (c[2] - w["Z"]) ** 2)[3]


def load_extras():
    path = os.path.join(OUT, "world_extras.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_world(fn: str):
    path = os.path.join(WORLD, fn)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ct_lists(rows):
    """Listy z tabeli CE (jak dotąd): bossowie DLC, łaski DLC, osełki i popioły wojny."""
    bosses = []
    for (bid, name, region, loc, flag, alt, req, conf, hints) in BOSSES:
        src = ["ct-hexinton", "save-verified"]
        if bid in ("putrescent-knight", "dancer-of-ranah", "ghostflame-dragon-cerulean"):
            src.append("flag-convention")
        if loc or hints:
            src.append("general-knowledge")
        bosses.append({
            "id": bid, "name": name, "region": region, "location": loc,
            "defeat_flag": flag, "alt_flags": alt, "arena": arena_for(flag), "dlc": True, "required": req,
            "hints": hints, "sources": src, "confidence": conf,
            "notes": BOSS_NOTES.get(bid),
        })

    graces, seen = [], set()
    for r in rows:
        parts = group_parts(r["group"])
        if parts[0] != "Sites of Grace":
            continue
        fid = int(r["flag_id"])
        if fid in seen:
            continue
        seen.add(fid)
        raw = r["description"].strip()
        name = GRACE_NAME_FIX.get(raw, raw)
        graces.append({
            "id": f"grace-{fid}", "name": name, "region": parts[2] if len(parts) > 2 else None,
            "area": parts[3] if len(parts) > 3 else None, "flag": fid, "dlc": parts[1] == "DLC",
            "map_id": None, "position": None, "sources": ["ct-hexinton", "save-verified"],
            "confidence": "high",
            "notes": f"Nazwa poprawiona z CSV: '{raw}'" if name != raw else None,
        })

    items, seen = [], set()
    for r in rows:
        parts = group_parts(r["group"])
        fid = int(r["flag_id"])
        if parts[0] not in ("Whetblades", "Ashes of War") or fid in seen or fid in ITEM_SKIP:
            continue
        seen.add(fid)
        name = re.sub(r"\s+", " ", r["description"]).strip()
        cat = "whetblade" if parts[0] == "Whetblades" else "ash_of_war"
        dlc = len(parts) > 1 and parts[1] == "DLC"
        items.append({
            "id": f"{cat.replace('_', '-')}-{slug(name.replace('Ash of War:', ''))}", "name": name,
            "name_en": name, "category": cat, "kind": "acquired_flag", "flag": fid, "dlc": dlc,
            "region": None, "location": None, "map_id": None, "hints": None,
            "sources": ["ct-hexinton", "save-verified"],
            "confidence": "high" if cat == "whetblade" else "medium",
            "notes": "Flaga 'zdobyto' (globalna), nie podniesienie z konkretnego miejsca." if cat == "whetblade" else
            "Flaga 'popiół wojny zdobyty' wg CT; rozkład na save'ach sensowny (0 u postaci lvl 13, 110/116 u lvl 221).",
        })
    items.sort(key=lambda i: (i["category"], i["dlc"], i["name"]))
    return bosses, graces, items


def region_fallbacks(extras, ct_graces, world_graces):
    """Zapasowe źródła krainy bossa, gdy nie ma łaski w pobliżu:
    mapa lochu -> PlayRegion (world_extras), nazwa z danych świata -> zakładka/podkategoria menu podróży,
    region EN z tabeli CE -> kraina łask DLC z tej samej grupy CE."""
    by_map = {}
    for e in ((extras or {}).get("play_regions") or {}).values():
        if e.get("kind") == "dungeon" and e.get("region") and e.get("map_id"):
            by_map.setdefault(e["map_id"][:6], (e["region"], e.get("subregion")))
    by_name = {}
    for sub in ((extras or {}).get("warp_subcategories") or {}).values():
        if sub.get("subregion"):
            by_name.setdefault(sub["subregion"], (sub.get("region"), sub["subregion"]))
    for t in ((extras or {}).get("warp_tabs") or {}).values():
        if t:
            by_name.setdefault(t, (t, None))
    wg_by_flag = {g["flag"]: g for g in world_graces or []}
    en = {}
    for g in ct_graces:
        w = wg_by_flag.get(g["flag"])
        if w and w.get("region"):
            for k in (g.get("area"), g.get("region")):
                if k:
                    en.setdefault(k, {}).setdefault((w["region"], w.get("subregion")), 0)
                    en[k][(w["region"], w.get("subregion"))] += 1
    by_en = {k: max(v, key=v.get) for k, v in en.items()}

    def resolve(map_id=None, name_pl=None, region_en=None):
        return ((map_id and by_map.get(map_id[:6])) or (name_pl and by_name.get(name_pl))
                or (region_en and by_en.get(region_en)) or (None, None))
    return resolve


def unnamed_name(ct, subregion, pl_by_en):
    """Boss bez nazwy w plikach gry: polska nazwa tego samego gatunku od innego bossa (po nazwie EN z tabeli CE,
    bez dopisku w nawiasie) + podregion, np. „Smok upiornego płomienia (Modre wybrzeże)”; inaczej nazwa EN z CE."""
    if not ct:
        return None
    base = re.sub(r"\s*\(.*\)$", "", ct["name"]).strip()
    pl = pl_by_en.get(base.lower())
    return f"{pl} ({subregion})" if pl and subregion else pl or ct["name"]


def world_bosses(world, ct_bosses, extras=None, locator=None, fallback=None):
    ct_by_flag = {b["defeat_flag"]: b for b in ct_bosses}
    pl_by_en = {}
    for w in world:
        if w.get("name") and w.get("name_en"):
            pl_by_en.setdefault(w["name_en"].strip().lower(), w["name"])
    per_map: dict[str, int] = {}
    for w in world:
        per_map[w.get("map_id")] = per_map.get(w.get("map_id"), 0) + 1
    out, used = [], set()
    for w in world:
        flag = w["flag"]
        ct = ct_by_flag.get(flag)
        used.add(flag)
        arena = None
        mid = w.get("map_id")
        bpos = ((extras or {}).get("boss_positions") or {}).get(str(flag))
        region = subregion = None
        if bpos:                                # pozycja bossa z pliku mapy (wróg o EntityID = flaga)
            arena = {"map_id": bpos["map_id"], "x": bpos["x"], "y": bpos["y"], "z": bpos["z"], "radius": ARENA_RADIUS,
                     "match": "radius", "confidence": "medium" if bpos["source"] == "msb" else "low",
                     "sources": ["game-files"]}
            if bpos.get("arena"):               # obszar przyzywania ducha z pliku mapy = granice areny
                reg = {k: bpos["arena"][k] for k in ("shape", "x", "y", "z", "rot_y", "dims")}
                arena.update(match="region", region=reg, region_name=bpos["arena"]["region_name"],
                             confidence="high" if bpos["arena"]["boss_in_region"] else "medium")
            g = locator.locate(bpos["map_id"], bpos["x"], bpos["y"], bpos["z"]) if locator else None
            if g:
                region, subregion = g["region"], g.get("subregion")
        elif mid and mid.startswith(DUNGEON_MAP_PREFIXES) and per_map.get(mid) == 1:
            arena = {"map_id": mid, "x": None, "y": None, "z": None, "radius": None, "match": "map",
                     "confidence": "low", "sources": ["world-data"]}
        if not region and fallback:
            region, subregion = fallback(bpos["map_id"] if bpos else mid, w.get("region_pl"),
                                         (ct_by_flag.get(flag) or {}).get("region"))
        req = ct["required"] if ct else (
            True if (w.get("name_en") in REQUIRED_BASE_EN or flag in REQUIRED_BASE_FLAGS) else None)
        name = w.get("name") or w.get("name_en") or unnamed_name(ct, subregion, pl_by_en) or f"Boss {flag}"
        out.append({
            "id": f"boss-{flag}", "name": name,
            "name_en": w.get("name_en") or (re.sub(r"\s*\(.*\)$", "", ct["name"]) if ct else None),
            # kraina/podregion wg najbliższej łaski (menu podróży gry); region_pl = to samo (dawniej niespójne)
            "region": region or (ct["region"] if ct else w.get("region")), "subregion": subregion,
            "region_pl": region or w.get("region_pl"),
            "location": w.get("location") or (ct["location"] if ct else None),
            # extra_defeat_flags: wariant „12…” z danych świata — bossowie dużej mapy (Radahn 1052380800 → 1252380800)
            # zapisują śmierć pod nim; liczy się jako pokonanie (alt_flags = tylko „odkryty”, np. NG)
            "defeat_flag": flag, "alt_flags": ct["alt_flags"] if ct else [], "extra_defeat_flags": w.get("alt_flags") or [], "arena": arena,
            "dlc": bool(w.get("dlc")), "required": req, "hints": ct["hints"] if ct else None,
            "runes": w.get("runes"), "map_id": mid, "world_id": w.get("id"),
            "remembrance": w.get("remembrance"),
            "sources": ["world-data"] + (ct["sources"] if ct else []) +
                       (["general-knowledge"] if (not ct and req) else []),
            "confidence": ct["confidence"] if ct else "high",
            "notes": "; ".join(x for x in ((ct or {}).get("notes"), REQUIRED_BASE_FLAGS.get(flag),
                                           None if w.get("name") else "brak polskiej nazwy") if x) or None,
            "legacy_id": ct["id"] if ct else None,
        })
    for ct in ct_bosses:                       # bossowie z CT, których nie ma w danych świata
        if ct["defeat_flag"] not in used:
            reg, sub = fallback(None, None, ct.get("region")) if fallback else (None, None)
            out.append({**ct, "id": f"boss-{ct['defeat_flag']}", "name_en": ct["name"],
                        "region": reg or ct.get("region"), "subregion": sub, "region_pl": reg,
                        "runes": None, "map_id": None, "world_id": None, "remembrance": None,
                        "legacy_id": ct["id"]})
    return out


def world_graces(world, ct_graces):
    ct_by_flag = {g["flag"]: g for g in ct_graces}
    out, skipped = [], []
    for w in world:
        ct = ct_by_flag.get(w["flag"])
        name = w.get("name") or (ct["name"] if ct else None)
        if not name:
            skipped.append(w["flag"])
            continue
        pos = w.get("pos") or [None, None, None]
        out.append({
            "id": f"grace-{w['flag']}", "name": name, "name_en": ct["name"] if ct else None,
            # kraina = zakładka menu podróży, podregion = podkategoria (assets/graces.json, poprawione 2026-11-24)
            "region": w.get("region") or (ct["region"] if ct else None), "subregion": w.get("subregion"),
            "area": ct["area"] if ct else None,
            # pole dlc w assets/data/graces.json jest błędne (m60 = DLC, lochy DLC = gra podstawowa) — liczymy z mapy
            "flag": w["flag"], "dlc": is_dlc_map(w.get("map_id"), w.get("dlc")), "map_id": w.get("map_id"),
            "position": {"x": pos[0], "y": pos[1], "z": pos[2]} if pos[0] is not None else None,
            "pos": w.get("pos"),
            "entity": w.get("entity"),
            "last_grace_id": w["entity"] + 1000 if w.get("entity") else None,
            "sources": ["world-data"] + (ct["sources"] if ct else []),
            "confidence": "high", "notes": ct["notes"] if ct else None,
        })
    return out, skipped


def world_items(world, ct_items, locator=None, catalog=None):
    by_flag: dict[int, dict] = {}
    for w in world:
        e = by_flag.get(w["flag"])
        if e is None:
            region = subregion = None
            if locator and w.get("pos"):
                g = locator.locate(w.get("map_id"), *w["pos"])
                if g:
                    region, subregion = g["region"], g.get("subregion")
            first = w["items"][0] if w["items"] else {}
            names = [i.get("name") or i.get("name_en") for i in w["items"]]
            e = by_flag[w["flag"]] = {
                "id": f"item-{w['flag']}",
                "name": " + ".join(n for n in names if n) or f"Skarb {w['flag']}",
                "name_en": " + ".join(i.get("name_en") or "" for i in w["items"]) or None,
                "category": w.get("kind") or first.get("kind"), "kind": "map_lot", "flag": w["flag"],
                "dlc": bool(w.get("dlc")), "region": region or w.get("region_pl"), "subregion": subregion,
                "location": None,
                "map_id": w.get("map_id"), "map_ids": [w.get("map_id")], "lots": [w.get("lot")],
                "contents": [{"cat": i.get("cat"), "id": i.get("id"), "count": i.get("count")} for i in w["items"]],
                "hints": None, "sources": ["world-data"], "confidence": "high", "notes": None,
            }
        else:                                   # ta sama flaga na dwóch mapach (np. Leyndell i Leyndell w popiele)
            if w.get("map_id") not in e["map_ids"]:
                e["map_ids"].append(w.get("map_id"))
            if w.get("lot") not in e["lots"]:
                e["lots"].append(w.get("lot"))
    # wpis z CT o tej samej fladze co skarb z mapy (np. osełki) jest zbędny — zostaje skarb (ma mapę)
    ct_left = [c for c in ct_items if c["flag"] not in by_flag]
    if catalog:                                 # polskie nazwy osełek/popiołów z katalogu przedmiotów
        by_en = {}
        for it in catalog:
            if it.get("name_en") and it.get("name"):
                by_en.setdefault(it["name_en"].strip().lower(), it["name"])
        for c in ct_left:
            pl = by_en.get(c["name_en"].strip().lower()) or by_en.get(re.sub(r"\s+", " ", c["name_en"]).strip().lower())
            if pl:
                c["name"] = pl
    return ct_left + sorted(by_flag.values(), key=lambda e: (e["map_id"] or "", e["flag"]))


def world_quests(world, bosses):
    """Questy z assets/data/quests.json; `locks[].boss_id` tłumaczone na id bossa z bosses.json."""
    by_flag = {b["defeat_flag"]: b["id"] for b in bosses}
    by_en: dict[str, list[str]] = {}
    for b in bosses:
        by_en.setdefault(b.get("name_en") or "", []).append(b["id"])
    out, unresolved = [], []
    for q in world:
        e = dict(q)
        e.setdefault("sources", ["world-data"])
        e.setdefault("confidence", "medium")
        e.setdefault("npc", None)
        e.setdefault("steps", [])
        e["id"] = str(e["id"])
        locks = []
        for lk in e.get("locks") or []:
            lk = dict(lk)
            bid = by_flag.get(lk.get("boss_flag"))
            if bid is None and len(by_en.get(lk.get("boss_en") or "", [])) == 1:
                bid = by_en[lk["boss_en"]][0]
            if bid is None:
                unresolved.append((e["id"], lk.get("boss_en")))
            lk["boss_id"] = bid
            locks.append(lk)
        e["locks"] = locks
        out.append(e)
    return out, unresolved


def build():
    rows = []
    if os.path.exists(CSV):                # opcjonalny wyciąg z lokalnej tabeli Cheat Engine (nie jest w repozytorium)
        with open(CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        print(f"uwaga: brak {CSV} — pomijam dodatki z tabeli CE (dane świata z assets/data wystarczą)")
    bosses, graces, items = ct_lists(rows)
    quests = []
    cov = {"bosses": "Tylko bossowie DLC obecni w tabeli CT (36). Brak bossów gry podstawowej.",
           "graces": "Tylko łaski DLC z tabeli CT (flaga = łaska odkryta / dostępna do teleportu).",
           "items": "Osełki i popioły wojny z tabeli CT; bez lokalizacji.",
           "quests": "Pusto — brak rzetelnego źródła flag etapów questów."}
    src = {"bosses": ["ct-hexinton", "save-verified", "flag-convention", "general-knowledge"],
           "graces": ["ct-hexinton", "save-verified"], "items": ["ct-hexinton", "save-verified"], "quests": []}

    extras = load_extras()
    wg = load_world("graces.json")
    locator = None
    if wg:
        import sys
        sys.path.insert(0, os.path.join(ROOT, "backend"))
        from erbackend.worldmap import WorldMap
        locator = Locator(wg, WorldMap(extras) if extras else None)
    wb = load_world("bosses_all.json")
    if wb:
        bosses = world_bosses(wb, bosses, extras, locator, region_fallbacks(extras, graces, wg))
        cov["bosses"] = (f"{len(bosses)} bossów: {len(wb)} z danych świata (GameAreaParam, nazwy PL z gry) "
                         f"+ {len(bosses) - len(wb)} tylko z tabeli CT.")
        src["bosses"] = ["world-data", "game-files"] + src["bosses"]
    if wg:
        graces, skipped = world_graces(wg, graces)
        cov["graces"] = f"{len(graces)} łask z danych świata (pominięte bez nazwy: {skipped})."
        src["graces"] = ["world-data"] + src["graces"]
    wi = load_world("item_locations.json")
    if wi:
        items = world_items(wi, items, locator, load_world("items.json"))
        n_ct = sum(1 for i in items if i["kind"] == "acquired_flag")
        cov["items"] = (f"{n_ct} wpisów z tabeli CT (osełki/popioły, flaga 'zdobyto', kind=acquired_flag; "
                        f"te z flagą równą flagi skarbu pominięte) + {len(items) - n_ct} skarbów z map "
                        f"(ItemLotParam_map, kind=map_lot; {len(wi)} lotów połączonych po fladze).")
        src["items"] = ["world-data"] + src["items"]
    wq = load_world("quests.json")
    if wq:
        quests, unresolved = world_quests(wq if isinstance(wq, list) else wq.get("entries", []), bosses)
        cov["quests"] = (f"{len(quests)} questów z danych świata (assets/data/quests.json)."
                         + (f" Blokady bez bossa w bosses.json: {unresolved}." if unresolved else ""))
        src["quests"] = ["world-data"]
        if isinstance(wq, dict):                 # źródła opisane w pliku questów
            SOURCES.update({k: v for k, v in (wq.get("_meta") or {}).get("sources", {}).items() if k not in SOURCES})
            used = {x for q in quests for x in q.get("sources", [])}
            used |= {x for q in quests for st in q.get("steps", []) for x in st.get("sources", [])}
            src["quests"] = ["world-data"] + sorted(used - {"world-data"})

    write("bosses.json", meta("bosses", src["bosses"], {"coverage": cov["bosses"]}), bosses)
    write("graces.json", meta("graces", src["graces"], {"coverage": cov["graces"]}), graces)
    write("items.json", meta("items", src["items"], {"coverage": cov["items"]}), items)
    write("quests.json", meta("quests", src["quests"], {"coverage": cov["quests"]}), quests)
    print(f"bosses {len(bosses)}, graces {len(graces)}, items {len(items)}, quests {len(quests)}")


def write(fn: str, m: dict, entries: list):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, fn), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"_meta": m, "entries": entries}, f, ensure_ascii=False, indent=1)
        f.write("\n")


if __name__ == "__main__":
    build()
