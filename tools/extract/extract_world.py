"""Świat gry: bossowie, miejsca (lochy, ruiny…), przedmioty leżące na mapie i NPC, z pozycjami na mapie.

Wynik (assets/data/):
  bosses_all.json      wszyscy bossowie (GameAreaParam): flaga pokonania, runy, nazwy PL/EN, region, pozycja, ikona
  pois.json            miejsca z WorldMapPointParam (lochy, ruiny, kościoły…): kategoria, ikona, napisy zależne od flag
  item_locations.json  skarby z plików map (MSB): pula łupu, flaga podniesienia, przedmioty, kategoria, pozycja
  npcs.json            NPC z dialogiem (MSB: wróg z TalkID) z nazwą PL i pozycją
  invaders.json        najeźdźcy (czerwone fantomy NPC) z flagą pokonania, nagrodami i pozycją
Pozycje: mapy m60/m61 przeliczane wprost (map_transform), lochy przez WorldMapLegacyConvParam
(łańcuchy aż do m60/m61). Małe lochy (katakumby, jaskinie, tunele, lochy DLC) ląduje przy wejściu (`approx`).
Podziemia (m12): dokładnie, na osobnej mapie M01. Farum Azula (m13): w wirze burzy (stała FARUM).
"""
import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import emevd as E  # noqa: E402
import msb  # noqa: E402
import params as P  # noqa: E402
from extract_data import TRANSFORM  # noqa: E402

DATA = os.path.join(A.ROOT, "assets", "data")
ENTRANCE_AREAS = {30, 31, 32, 39, 40, 41, 42, 43}          # małe lochy -> punkt wejścia
UNDERGROUND = {"M00": "M01"}                                # podziemia (m12: Siofra, Ainsel, Głębiny) — osobna mapa gry
# Przeklęte Farum Azula (m13): gra rysuje je w wirze burzy na wschód od Szczytów Olbrzymów. Przesunięcie z wiersza 11
# WorldMapLegacyConvParam (punkt bazowy m13 -> m60_51_43), skala 1:1; najbliższy wiersz (10/132) prowadził na Szczyty.
FARUM = {"px": 8488.9, "py": 4835.7, "scale": 1.0, "x": 0.0, "z": 0.0}
DLC_AREAS = {20, 21, 22, 25, 28, 40, 41, 42, 43, 61}
# najeźdźcy (czerwone fantomy NPC): wspólne zdarzenia z common_func wywoływane w skryptach map
INVASION, INVADER_DEATH, FLAG_REWARD, QUEST_REWARDS = 90005790, 90005792, 90005774, 90005768
# znak przywołania postaci (pomocnicy jak Millicenta i czerwone pojedynki): (warunek, ?, flaga, encja, …); kilka wywołań
# z tym samym warunkiem w jednej mapie to seria pojedynków (trzej Rycerze wielkiego naczynia przy Wielkim Dzbanie),
# a trzeci argument to flaga pokonania rycerza (sprawdzone na save'ach: 1047410230-232)
SUMMON_SIGN = 90005793
# jednorazowy łup przeciwnika: wspólne zdarzenie (flaga, encja, pula, …) daje pulę przy jego śmierci (np. skarabeusze);
# poza tym przeciwnik z mapy, którego EntityID ma własny wiersz ItemLotParam_map z flagą, upuszcza ten wiersz
# (sprawdzone na save'ach: flagi takich pul są ustawione po zabiciu, np. Margit 10000850)
ENEMY_DROP = (90005300, 90005301)
# modele skarabeuszy (gra nie ma ich nazwy w NpcName; łupy zgodne z listą na Fextralife: popioły wojny, ponure kamienie)
SCARAB_MODELS = {"c4190", "c4191", "c4192"}
# Moore w DLC ma 6 takich wywołań; nie wiadomo, czy to prawdziwe inwazje, więc go pomijamy, dopóki nie sprawdzimy w grze
SKIP_INVADERS_EN = {"Moore"}
# kategorie w wierszach puli łupu (ItemLotParam); 6 = gotowa broń z EquipParamCustomWeapon (+0x00 broń bazowa),
# tak zapisane są m.in. Rapier Rogiera, Nagakiba i bronie z DLC dawane z ulepszeniem
LOT_CATS = {1: "goods", 2: "weapon", 3: "armor", 4: "talisman", 5: "ash_of_war", 6: "weapon"}


def lot_slots(row):
    """(item id, category code, weight, count) for the 8 slots of an ItemLotParam row."""
    return zip(struct.unpack_from("<8i", row, 0), struct.unpack_from("<8i", row, 0x20), struct.unpack_from("<8H", row, 0x40),
               row[0x8A:0x92])


# NpcParam (0x2E0 B, Paramdex NPC_PARAM_ST): +0x24 HP, +0x1A4.. 8x f32 damage multipliers (1.1 = takes 10% more),
# status resistances (999 = immune) and ResistCorrectParam row raising the threshold after each proc, +0x2A8 poise.
# Resident special effects (+0x4C 8x, +0x178 8x, +0x1E8 16x) include the area scaling that multiplies HP and
# resistances (SpEffectParam +0x10 maxHpRate, regist*ChangeRate). Checked on Margit against Fextralife:
# 2521 HP x 1.656 = 4174, slash -10, holy 40, statuses 316/414/704/1161, sleep and madness immune, poise 80.
# Defense: NpcParam +0xF8/0x100/0x102/0x104/0x15E u16 (phys, magic, fire, lightning, holy) times SpEffectParam
# +0x68/0x6C/0x70/0x74/0x1D4 (Margit 100 x 1.039 = 103.9, in the Capital Outskirts 111.9; Fextralife 103 / 111).
ABSORB = ("standard", "slash", "strike", "pierce", "magic", "fire", "lightning", "holy")
STATUS = {"poison": (0x108, 0x08, 0x108), "rot": (0x10A, 0x1D0, 0x10C), "bleed": (0x10C, 0x2B4, 0x110),
          "death": (0x10E, 0x2B8, 0x114), "frost": (0x1E0, 0x2BC, 0x2B4), "sleep": (0x126, 0x2C0, 0x340),
          "madness": (0x128, 0x2C4, 0x344)}    # NpcParam resist, NpcParam resistCorrectId, SpEffectParam rate


def enemy_stats(row, speffects, resist_correct):
    """HP, damage negation (%), status thresholds after 0..3 procs (None = immune) and poise of one NpcParam row."""
    effects = [speffects[e] for e in (*struct.unpack_from("<8i", row, 0x4C), *struct.unpack_from("<8i", row, 0x178),
                                      *struct.unpack_from("<16i", row, 0x1E8)) if e > 0 and e in speffects]
    scale = lambda off: math.prod(struct.unpack_from("<f", e, off)[0] for e in effects)  # noqa: E731
    status = {}
    for name, (off, corr_off, rate_off) in STATUS.items():
        base = struct.unpack_from("<H", row, off)[0]
        if base >= 999:
            status[name] = None
            continue
        first = base * scale(rate_off)
        corr = resist_correct.get(struct.unpack_from("<i", row, corr_off)[0])
        steps = struct.unpack_from("<5f", corr, 0)[:3] if corr and struct.unpack_from("<5f", corr, 0x14) == (1.0,) * 5 else ()
        status[name] = [round(first)] + [round(first + p) for p in steps]   # next threshold = first + increment
    defense = [round(struct.unpack_from("<H", row, off)[0] * scale(rate), 1)
               for off, rate in zip((0xF8, 0x100, 0x102, 0x104, 0x15E), (0x68, 0x6C, 0x70, 0x74, 0x1D4))]
    return {"hp": int(struct.unpack_from("<I", row, 0x24)[0] * scale(0x10)), "defense": defense,
            "absorb": {k: round((1 - v) * 100) for k, v in zip(ABSORB, struct.unpack_from("<8f", row, 0x1A4))},
            "status": status, "poise": round(struct.unpack_from("<f", row, 0x2A8)[0])}


def display_mask(row):
    """Model variants an NpcParam row shows: bit NN = meshes named '#NN#' (+0x14A/+0x14B/+0x14E/+0x14F, 32 bits).

    One model serves several characters (Pidia and Albus c3670, Kalé and the nomadic merchants c3200), the game picks
    clothes, robes and bodies per character with this mask (Azur: bit 2 = robe '#02#'; Pidia: 10, 11, 15)."""
    return row[0x14A] | row[0x14B] << 8 | row[0x14E] << 16 | row[0x14F] << 24


def lot_item(code, iid, custom):
    """(category, item id) of a lot slot; category None for codes outside LOT_CATS, a ready-made weapon -> its base weapon."""
    if code == 6 and iid > 0:
        iid = struct.unpack_from("<i", custom[iid], 0)[0]
    return LOT_CATS.get(code), iid


# ---------------- pozycje ----------------
class World:
    def __init__(self, ps):
        self.conv = []
        for _, r in P.rows(ps["WorldMapLegacyConvParam"])[0]:
            src, dst = (r[4], r[5], r[6]), (r[0x14], r[0x15], r[0x16])
            if src == dst:
                continue
            self.conv.append((src, struct.unpack_from("<3f", r, 0x08), dst, struct.unpack_from("<3f", r, 0x18), r[0x24]))

    def to_overworld(self, area, gx, gz, x, y, z, depth=0):
        """-> (area, gx, gz, x, y, z, approx) w m60/m61 albo None."""
        if area in (60, 61):
            return area, gx, gz, x, y, z, depth > 0 and False
        if depth > 5:
            return None
        cands = sorted((c for c in self.conv if c[0] == (area, gx, gz)),
                       key=lambda c: (c[2][0] not in (60, 61), (c[1][0] - x) ** 2 + (c[1][2] - z) ** 2))
        for src, sp, dst, dp, _ in cands:              # najpierw bezpośrednio do m60/m61, potem najbliższy punkt
            if area in ENTRANCE_AREAS:
                res = self.to_overworld(*dst, *dp, depth + 1)
                res = res and (*res[:6], True)
            else:
                res = self.to_overworld(*dst, dp[0] + x - sp[0], dp[1] + y - sp[1], dp[2] + z - sp[2], depth + 1)
            if res:
                return res
        # a map with no row of its own (Chapel of Anticipation m10_01) is placed by a row leading into it, read backwards
        if not cands:
            for src, sp, dst, dp, _ in self.conv:
                if dst == (area, gx, gz) and src != dst:
                    res = self.to_overworld(*src, sp[0] + x - dp[0], sp[1] + y - dp[1], sp[2] + z - dp[2], depth + 1)
                    if res:
                        return res
        return None

    def to_map(self, area, gx, gz, x, y, z):
        if area == 13:
            f = FARUM
            return {"map": "M00", "px": round(f["px"] + (x - f["x"]) * f["scale"], 1),
                    "py": round(f["py"] - (z - f["z"]) * f["scale"], 1), "approx": False}
        w = self.to_overworld(area, gx, gz, x, y, z)
        if not w:
            return None
        a, gx, gz, x, y, z, approx = w
        for key, t in TRANSFORM.items():
            if t["area"] == a:
                return {"map": UNDERGROUND.get(key, key) if area == 12 else key, "px": round(gx * 256 + x + 128 - t["ox"], 1),
                        "py": round(t["size"] - (gz * 256 + z + 128 - t["oz"]), 1), "approx": bool(approx)}
        return None


def award_params(evs):
    """Zdarzenie -> bajty argumentów wywołania, z których AwardItemLot (2003[4]/[36]) bierze pulę jako parametr."""
    out = {}
    for eid, ev in evs.items():
        for k, (bank, iid, _a) in enumerate(ev["instrs"]):
            if (bank, iid) in ((2003, 4), (2003, 36)):
                out.setdefault(eid, set()).update(src for pi, tgt, src, _n in ev["params"] if pi == k and tgt == 0)
    return out


def lot_ids(table, lot):
    """Pula i kolejne wiersze (lot+1, lot+2…, najwyżej 8): gra daje je razem, np. cały zestaw zbroi z jednego miejsca."""
    out = []
    while lot + len(out) in table and len(out) < 8:
        out.append(lot + len(out))
    return out


def item_index(items):
    """(category, id) -> catalog item, including the other ids of the same item (`alt_ids`, extract_icons.py)."""
    return {(i["category"], rid): i for i in items for rid in [i["id"], *i.get("alt_ids", [])]}


def maps():
    """(path, (area, gx, gz), map id, parsed MSB) for every map file; one pass takes a few minutes, so it prints progress."""
    paths = msb_paths()
    for i, path in enumerate(paths):
        if i % 200 == 0:
            print(f"  mapy {i}/{len(paths)}", flush=True)
        m = msb.load(path)
        if m:
            area, gx, gz, _level = msb.tile(path)
            yield path, (area, gx, gz), msb.map_id(area, gx, gz), m


def part_model(name):
    """Character model (cXXXX) of a map part, None for other parts. Parts of the big overworld tiles carry the small
    tile's name first: m60_52_38_00-c4730_9002 (Radahn)."""
    m = re.match(r"(?:m[\d_]+-)?(c\d{4})_", name)
    return m and m.group(1)


class EntityPlaces:
    """Entity id -> page position of a map part or region (also point regions) holding it, for scripted objects."""

    def __init__(self, world):
        self.world, self.places = world, {}
        for _path, tile, mid, m in maps():
            for o in m["parts"] + m["regions"]:
                if o["entity"]:
                    self.places.setdefault(o["entity"], []).append((mid, tile, o["pos"], o.get("npc")))

    def where(self, entity, tile=None):
        """{map_id, map, px, py, approx} of the entity, preferring the given level-0 tile (area, x, z); None if unknown."""
        hits = sorted(self.places.get(entity, []), key=lambda h: h[1] != tile)
        if not hits:
            return None
        mid, t, pos, _npc = hits[0]
        px = self.world.to_map(*t, *pos)
        return px and {"map_id": mid, **px}

    def npc(self, entity):
        """NpcParam id of the enemy part with this entity, or None."""
        return next((h[3] for h in self.places.get(entity, []) if h[3]), None)


def event_scripts():
    """Event scripts of every level-0 tile plus "common" and "common_func": {scope: events}, for emevd.callers/instances."""
    scripts = {mid: E.load(f"/event/{mid}.emevd.dcx") or {} for mid in tile_ids() + ["common"]}
    scripts["common_func"] = E.load("/event/common_func.emevd.dcx")
    if not scripts["common_func"]:
        raise SystemExit("brak /event/common_func.emevd.dcx w plikach gry: bez niego nie ma teleportów ani znaków przywołania")
    return scripts


def scope_tile(scope):
    """(area, x, z) of the map a script belongs to, None for common scripts."""
    return msb.tile(scope)[:3] if scope.startswith("m") else None


def tile_ids():
    """Level-0 tile ids (mAA_XX_YY_00) covered by the map files; event and talk scripts exist only for these."""
    return sorted({msb.map_id(*msb.tile(p)[:3]) for p in msb_paths()})


def msb_paths():
    """Map files (MSB) present in the archives: names are guessed and checked by hash, the list is cached."""
    cache_path = os.path.join(A.ROOT, "assets", "cache", "map_files.txt")
    if os.path.exists(cache_path):
        return [ln.strip() for ln in open(cache_path, encoding="utf-8") if ln.strip()]
    import bhd
    arcs = [A.Archive(n) for n in bhd.ARCHIVES]
    found = []
    # lochy: poziom 00; otwarty świat także pliki większej skali 01 i 02 (duzi przeciwnicy, wozy, część skarbów)
    for area in list(range(10, 46)) + [60, 61]:
        for level in ((0, 1, 2) if area in (60, 61) else (0,)):
            xs, zs = (range(100 >> level), range(100 >> level)) if area in (60, 61) else (range(30), range(3))
            for a in xs:
                for b in zs:
                    p = f"/map/mapstudio/m{area:02d}_{a:02d}_{b:02d}_{level:02d}.msb.dcx"
                    if any(A.path_hash(p) in arc.files for arc in arcs):
                        found.append(p)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write("\n".join(found))
    return found


_blocks = None


def flag_blocks():
    """Bloki flag istniejące w save'ie (eventflag_bst.txt: ID // 1000) — flagi spoza nich gra nie zapisuje."""
    global _blocks
    if _blocks is None:
        path = os.path.join(A.ROOT, "docs", "data", "er-save-lib", "eventflag_bst.txt")
        _blocks = {int(ln.split(",")[0]) for ln in open(path) if ln.strip()}
    return _blocks


def ct_boss_flags(cache_path):
    """Flagi bossów z tabeli Cheat Engine w folderze gry (opisy EN + grupy); format adresu: oba warianty."""
    import xml.etree.ElementTree as ET
    import bhd
    ct = next((os.path.join(bhd.GAME_DIR, f) for f in os.listdir(bhd.GAME_DIR) if f.lower().endswith(".ct")), None)
    if not ct:
        return []
    bst = {int(b): int(p) for b, p in (ln.strip().split(",") for ln in open(os.path.join(A.ROOT, "docs", "data", "er-save-lib", "eventflag_bst.txt")) if ln.strip())}
    inv = {p: b for b, p in bst.items()}
    out = []

    def walk(e, path):
        for ce in e.findall("./CheatEntries/CheatEntry"):
            d = (ce.findtext("Description") or "").strip('"').strip()
            p = path + [d]
            if "Revive Bosses" in p and ce.findtext("VariableType") == "Binary":
                addr = (ce.findtext("Address") or "").strip()
                offs = [o.text for o in ce.findall("./Offsets/Offset")]
                byte = None
                m = re.fullmatch(r"\[\[EventFlagMan\]\+28\]\+([0-9A-Fa-f]+)", addr)
                if m:
                    byte = int(m.group(1), 16)
                elif addr == "EventFlagMan" and len(offs) == 2 and int(offs[1], 16) == 0x28:
                    byte = int(offs[0], 16)
                blk = inv.get(byte // 125) if byte is not None else None
                if blk is not None:
                    bit = int(ce.findtext("BitStart") or 0)
                    out.append({"group": "/".join(p[p.index("Revive Bosses") + 1:-1]), "desc": d,
                                "flag": blk * 1000 + (byte % 125) * 8 + (7 - bit)})
            walk(ce, p)
    walk(ET.parse(ct).getroot(), [])
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return out


# ---------------- kategorie przedmiotów ----------------
KIND_PRIORITY = ["great_rune", "remembrance", "weapon", "armor", "talisman", "ash_of_war", "sorcery", "incantation", "spirit_ash",
                 "golden_seed", "sacred_tear", "crystal_tear", "somber_stone", "dlc_blessing", "memory_stone", "whetblade",
                 "bell_bearing", "key_item", "stonesword_key", "map_fragment", "cookbook", "smithing_stone", "upgrade",
                 "golden_rune", "note", "material", "consumable", "ammo"]


def item_category(cat, item_id, goods_type, name):
    n = (name or "").lower()
    if cat == "weapon":
        return "ammo" if any(k in n for k in ("strzał", "bełt", "pocisk do")) else "weapon"
    if cat in ("armor", "talisman", "ash_of_war"):
        return cat
    t = goods_type
    if t in (5, 17):
        return "sorcery"
    if t in (16, 18):
        return "incantation"
    if t in (7, 8):
        return "spirit_ash"
    if t == 3:
        return "remembrance"
    if t == 15:
        return "great_rune"
    if t == 10:
        return "crystal_tear"
    if t == 2:
        return "material"
    if t == 14:
        if "złote nasiono" in n:
            return "golden_seed"
        if "święta łza" in n:
            return "sacred_tear"
        if "ponury kamień kowalski" in n:
            return "somber_stone"
        if "kamień kowalski" in n:
            return "smithing_stone"
        if "ostrodrzew" in n or "czcigodnego ducha" in n:
            return "dlc_blessing"
        return "upgrade"
    if t == 1:
        if "dzwon" in n:
            return "bell_bearing"
        if "kamień pamięci" in n:
            return "memory_stone"
        if "osełka" in n or re.fullmatch(r"\w+ ostrze", n):          # Żelazne/Rozżarzone/Uświęcone/Błyskamienne ostrze
            return "whetblade"
        if "klucz kamiennego miecza" in n:
            return "stonesword_key"
        if n.startswith("mapa"):
            return "map_fragment"
        if "receptur" in n or "notatnik" in n or "książka kucharska" in n or "przepis" in n:
            return "cookbook"
        return "key_item"
    if t == 12:
        return "cookbook" if any(k in n for k in ("receptur", "notatnik", "przepis")) else "note"
    if "złoty run" in n or "run bohatera" in n or "run numena" in n or "run władcy" in n or n.startswith("run "):
        return "golden_rune"                                       # także DLC: Run Królestwa Cieni [n], Run Mariki…
    return "consumable"


# główne lochy (legacy dungeons) — najpierw, żeby „Zamek…”, „Święte Drzewo…” nie trafiły do zamków/drzew
LEGACY_NAMES = ("leyndell", "farum azula", "akademia rai lucarii", "elphael", "wulkaniczny dwór", "donżon cienia", "enir-ilim",
                "zamek burzowego całunu", "święte drzewo miquelli", "nokron", "pałac mohgwynów", "zamek cieni", "belurat")
POI_RULES = [("katakumby", "catacombs"), ("jaskini", "cave"), ("grota", "cave"), ("pieczar", "cave"), ("kryjówk", "cave"),
             ("smocza jama", "cave"), ("tunel", "tunnel"),
             ("wieczne więzienie", "evergaol"), ("grobowiec bohatera", "hero_grave"), ("grób bohatera", "hero_grave"),
             ("mogilnik", "hero_grave"), ("mauzoleum", "mausoleum"),
             ("wieża", "tower"), ("ruiny", "ruins"), ("kościół", "church"), ("kaplica", "church"), ("katedr", "church"),
             ("zamek", "castle"), ("twierdz", "castle"), ("fort", "fort"), ("szopa", "shack"), ("chata", "shack"),
             ("drzewo", "minor_erdtree"), ("wioska", "village"), ("osad", "village"), ("most", "landmark")]


def poi_category(name):
    n = name.lower().strip()
    if n.startswith("loch ") and "podziemny" not in n:        # DLC: Loch Belurat, Loch Bonny, Loch płaczki
        return "gaol"
    if any(k in n for k in LEGACY_NAMES):
        return "legacy"
    for key, cat in POI_RULES:
        if key in n:
            return cat
    return "landmark"


def main():
    ps = P.load_params()
    world = World(ps)
    tp, te = P.load_texts("polpl"), P.load_texts("engus")
    npc_pl = {**tp.get("NpcName", {}), **tp.get("NpcName_dlc01", {}), **tp.get("NpcName_dlc02", {})}
    npc_en = {**te.get("NpcName", {}), **te.get("NpcName_dlc01", {}), **te.get("NpcName_dlc02", {})}
    en2pl = {v.lower(): npc_pl.get(k) for k, v in npc_en.items() if npc_pl.get(k)}
    places = {**tp.get("PlaceName", {}), **tp.get("PlaceName_dlc01", {}), **tp.get("PlaceName_dlc02", {})}
    places_en = {**te.get("PlaceName", {}), **te.get("PlaceName_dlc01", {}), **te.get("PlaceName_dlc02", {})}
    region_pl = {v.lower(): places.get(k) for k, v in places_en.items() if places.get(k)}
    region_pl.update({"liurnia": region_pl.get("liurnia of the lakes"), "altus plateau": region_pl.get("altus plateau"),
                      "mountaintops": region_pl.get("mountaintops of the giants"), "leyndell": region_pl.get("leyndell, royal capital")})
    items = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
    by_item = item_index(items)
    npc_rows = dict(P.rows(ps["NpcParam"])[0])
    speffects, resist_correct = dict(P.rows(ps["SpEffectParam"])[0]), dict(P.rows(ps["ResistCorrectParam"])[0])
    lots = dict(P.rows(ps["ItemLotParam_map"])[0])
    custom = dict(P.rows(ps["EquipParamCustomWeapon"])[0])

    def lot_items(lot_id):
        r = lots.get(lot_id)
        if not r:
            return [], 0
        out = []
        for iid, c, _w, n in lot_slots(r):
            cat, iid = lot_item(c, iid, custom)
            if not iid or not cat:
                continue
            base = iid - iid % 10000 if cat == "weapon" else iid
            it = by_item.get((cat, iid)) or by_item.get((cat, base))
            name = it["name"] if it else None
            if not name:                                       # przedmioty bez nazwy w grze (atrapy, wycięte) — pomijamy
                continue
            out.append({"cat": cat, "id": iid, "name": name, "name_en": it and it["name_en"], "icon": it and it["icon"],
                        "count": n or 1, "kind": it["kind"]})
        return out, struct.unpack_from("<I", r, 0x80)[0]

    def lot_chain(lot_id):
        its, flag = lot_items(lot_id)
        for lid in lot_ids(lots, lot_id)[1:]:
            its += lot_items(lid)[0]
        return its, flag

    def place_lot(lot, mid, local, **extra):
        """A one-time reward on the map (treasure or an enemy's drop) -> item_locations.json; False when the lot is empty."""
        its, flag = lot_chain(lot)
        if not its:
            return False
        area, gx, gz, _level = msb.tile(mid)
        treasures.append({"lot": lot, "flag": flag, "map_id": mid, "items": its,
                          "kind": min((i["kind"] for i in its), key=lambda k: KIND_PRIORITY.index(k) if k in KIND_PRIORITY else 99),
                          "dlc": area in DLC_AREAS,
                          "pos": [round(c, 1) for c in local],    # lokalnie w pliku mapy (do łask w tym samym lochu)
                          **extra, **(world.to_map(area, gx, gz, *local) or {})})
        return True

    # ---------- przejście po wszystkich plikach map ----------
    treasures, npcs, enemies_by_entity, enemies_by_name = [], [], {}, {}
    for _path, (area, gx, gz), mid, m in maps():
        for p in m["parts"]:
            if p["type"] == "enemy" and p["entity"]:
                enemies_by_entity[p["entity"]] = (mid, p)
            if p["type"] == "enemy" and p["npc"] in npc_rows:     # do znalezienia modelu bossa po nazwie
                enemies_by_name.setdefault(struct.unpack_from("<i", npc_rows[p["npc"]], 0x0C)[0], []).append((mid, p))
            if p["type"] == "enemy" and p["talk"] not in (None, -1, 0) and p["npc"] in npc_rows:
                name_id = struct.unpack_from("<i", npc_rows[p["npc"]], 0x0C)[0]
                if name_id > 0 and npc_pl.get(name_id):
                    pos = world.to_map(area, gx, gz, *p["pos"])
                    npcs.append({"name": npc_pl[name_id], "name_en": npc_en.get(name_id), "map_id": mid, "entity": p["entity"],
                                 "talk": p["talk"], "model": part_model(p["name"]), "chara_init": p["chara_init"] if (p["chara_init"] or 0) > 0 else None,
                                 "mask": display_mask(npc_rows[p["npc"]]),
                                 "pos": [round(c, 1) for c in p["pos"]], **(pos or {})})
        for t in m["treasures"]:
            if t["lot"] > 0 and t["pos"]:
                place_lot(t["lot"], mid, t["pos"])

    # ---------- skrypty zdarzeń (EMEVD): nazwy bossów i nagrody ----------
    # Wspólne zdarzenia: 90005870 (pasek życia bossa: encja, ID nazwy w NpcName),
    # 90005860 (nagroda za bossa polowego: flaga, 0, encja, 0, pula ItemLotParam_map).
    # Nagrody — tylko pewne źródła:
    #  a) wywołania wspólnych funkcji przyznających łup (common_func: AwardItemLot / AwardItemsIncludingClients
    #     z parametrem), pula czytana z dokładnej pozycji argumentu, i tylko gdy w tym samym wywołaniu jest flaga bossa;
    #  b) zdarzenia mapy z literalnym AwardItemLot, które sprawdzają flagę tego bossa (i tylko jednego bossa).
    award_src = award_params(E.load("/event/common_func.emevd.dcx") or {})
    boss_name_by_entity, reward_by_flag, name_near_flag, global_flag, reward_by_global = {}, {}, {}, {}, {}
    invasions, invader_lots, quest_lots = {}, {}, {}        # flaga pokonania -> encja / pule nagród
    duels = {}                                              # (mapa, warunek) -> [(flaga pokonania, encja)] znaków przywołania
    enemy_drop = {}                                         # encja przeciwnika -> pula dawana przy jego śmierci
    # bossowie polowi (Nocna Kawaleria, Ptak śmierci…): wiersz GameAreaParam ma numer encji bossa, a śmierć zapisuje
    # wspólne zdarzenie 90005860/90005861(flaga pokonania, …, encja, …) pod inną flagą (…800 / …850)
    field_defeat = {}
    global_flag_weak = {}
    ga_flags = {rid for rid, _ in P.rows(ps["GameAreaParam"])[0] if rid > 1000 and not 9999990 <= rid <= 9999999}
    for mid in tile_ids():
        evs = E.load(f"/event/{mid}.emevd.dcx")
        if not evs:
            continue
        local_src = award_params(evs)           # nagrody też w zdarzeniach samej mapy (np. Nocna Kawaleria z glewią)
        for ev in evs.values():
            ev_flags, ev_lots = set(), []
            for bank, iid, a in ev["instrs"]:
                x = E.ints(a)
                if (bank, iid) in ((2000, 0), (2000, 6)) and len(x) >= 2:   # Initialize(Common)Event(0, id, args...)
                    cid, args = x[1], a[8:]
                    cargs = E.ints(args)
                    if cid in (90005860, 90005861) and cargs:
                        for v in cargs[1:]:
                            if v in ga_flags and v != cargs[0]:
                                field_defeat.setdefault(v, cargs[0])
                    if cid == INVASION and len(cargs) >= 5:              # (warunek, flaga pokonania, obszar, obszar, encja, …)
                        invasions.setdefault(cargs[1], cargs[4])
                    elif cid in ENEMY_DROP and len(cargs) >= 3 and cargs[2] in lots:
                        enemy_drop.setdefault(cargs[1], cargs[2])
                    elif cid == SUMMON_SIGN and len(cargs) >= 4:
                        duels.setdefault((mid, cargs[0]), []).append((cargs[2], cargs[3]))
                    elif cid == INVADER_DEATH and len(cargs) >= 5 and cargs[4] in lots and cargs[4] > 0:   # (flaga, obszar, obszar, encja, pula, …)
                        invader_lots.setdefault(cargs[0], []).append(cargs[4])
                    elif cid == FLAG_REWARD and len(cargs) >= 2 and cargs[1] in lots and cargs[1] > 0:     # (flaga, pula, flaga otrzymania)
                        invader_lots.setdefault(cargs[0], []).append(cargs[1])
                    elif cid == QUEST_REWARDS and cargs:                  # (flaga, pula, flaga, pula, …): nagroda zależna od questu
                        quest_lots.setdefault(cargs[0], []).extend(v for v in cargs[1::2] if v > 0 and v in lots)
                    if cid == 90005870 and len(cargs) >= 2 and cargs[1] in npc_pl:
                        boss_name_by_entity.setdefault(cargs[0], cargs[1])
                    srcs = award_src.get(cid, set()) | local_src.get(cid, set())
                    if srcs:
                        flags_here = [v for v in cargs if v in ga_flags]
                        for src in srcs:
                            if src + 4 <= len(args):
                                lot = struct.unpack_from("<i", args, src)[0]
                                if lot in lots and len(set(flags_here)) == 1:
                                    reward_by_flag.setdefault(flags_here[0], []).append(lot)
                    for v in cargs:                                     # zapasowo: ID nazwy NPC obok flagi bossa
                        if v in ga_flags:
                            nm = next((w for w in cargs if 900000000 <= w < 1000000000 and w in npc_pl), None)
                            if nm:
                                name_near_flag.setdefault(v, nm)
                if (bank, iid) == (2003, 11) and len(x) >= 4 and x[3] in npc_pl:   # DisplayBossHealthBar(on, encja, slot, nazwa)
                    boss_name_by_entity.setdefault(x[1], x[3])
                ev_flags.update(v for v in x if v in ga_flags)
                if (bank, iid) in ((2003, 4), (2003, 36)) and x and x[0] in lots:
                    ev_lots.append(x[0])
            if len(ev_flags) == 1 and ev_lots:
                reward_by_flag.setdefault(next(iter(ev_flags)), []).extend(ev_lots)
            # zdarzenie bossa ustawia globalną flagę 9xxx „boss pokonany” — wprost (2003[66]) albo w argumentach
            # wspólnej funkcji; bierzemy zdarzenia, które dotyczą dokładnie jednego bossa
            defeat = [E.ints(a)[0] for b2, i2, a in ev["instrs"] if (b2, i2) == (2003, 12) and len(a) >= 4]
            strong = len(set(defeat)) == 1 and defeat[0] in ga_flags
            owner = defeat[0] if strong else (next(iter(ev_flags)) if len(ev_flags) == 1 else None)
            if owner:
                target = global_flag if strong else global_flag_weak      # zdarzenie HandleBossDefeat ma pierwszeństwo
                for b2, i2, a in ev["instrs"]:
                    x2 = E.ints(a)
                    if (b2, i2) == (2003, 66) and len(x2) >= 3 and 9000 <= x2[1] < 10000 and x2[2] == 1:
                        target.setdefault(owner, x2[1])
                    elif (b2, i2) == (2000, 6) and owner in x2[2:]:
                        g = next((v for v in x2[2:] if 9000 <= v < 10000), None)
                        if g:
                            global_flag_weak.setdefault(owner, g)
    # common.emevd: InitializeEvent(slot, id, flaga_9xxx, pula, …) — nagrody przyznawane po globalnej fladze bossa
    for ev in (E.load("/event/common.emevd.dcx") or {}).values():
        for bank, iid, a in ev["instrs"]:
            x = E.ints(a)
            if (bank, iid) == (2000, 0):
                for k in range(2, len(x) - 1):
                    if 9000 <= x[k] < 10000 and x[k + 1] in lots:
                        reward_by_global.setdefault(x[k], []).append(x[k + 1])
    for boss_flag in set(global_flag) | set(global_flag_weak):
        gf = global_flag.get(boss_flag) or global_flag_weak.get(boss_flag)
        if gf in reward_by_global:
            reward_by_flag.setdefault(boss_flag, []).extend(reward_by_global[gf])
    print(f"  EMEVD: funkcje nagród {len(award_src)}, nazwy {len(boss_name_by_entity)}, nagrody {len(reward_by_flag)}, nazwy przy fladze {len(name_near_flag)}")

    # ---------- najeźdźcy: część mapy o encji z wywołania inwazji, nagrody z zdarzeń jej flagi pokonania ----------
    invaders = []
    gauntlet = {flag: entity for calls in duels.values() if len(calls) > 1 for flag, entity in calls}
    for flag, entity in sorted(invasions.items()) + sorted(gauntlet.items()):
        mid, part = enemies_by_entity.get(entity, (None, None))
        row = npc_rows.get(part["npc"]) if part else None
        if not row:
            raise SystemExit(f"najeźdźca: brak części mapy albo NpcParam dla encji {entity} (flaga {flag})")
        nid = struct.unpack_from("<i", row, 0x0C)[0]
        if npc_en.get(nid) in SKIP_INVADERS_EN:
            continue
        area, gx, gz = (int(v) for v in mid[1:].split("_")[:3])
        lots_ = list(dict.fromkeys(invader_lots.get(flag, []) + quest_lots.get(flag, [])))
        invaders.append({"id": entity, "flag": flag, "name": npc_pl.get(nid), "name_en": npc_en.get(nid), "map_id": mid,
                         "dlc": area in DLC_AREAS, "pos": [round(c, 1) for c in part["pos"]], "lots": lots_,
                         "quest_rewards": flag in quest_lots, **({"summoned": True} if flag in gauntlet else {}),
                         "stats": enemy_stats(row, speffects, resist_correct),
                         "rewards": [x for lot in lots_ for x in lot_chain(lot)[0]],
                         **(world.to_map(area, gx, gz, *part["pos"]) or {})})

    # ---------- bossowie ----------
    ct = ct_boss_flags(os.path.join(A.ROOT, "assets", "cache", "ct_boss_flags.json"))
    ct_by_flag = {}
    for c in ct:
        ct_by_flag.setdefault(c["flag"], c)
    remembrance = {b["boss_en"].lower(): b for b in json.load(open(os.path.join(DATA, "bosses.json"), encoding="utf-8"))}
    bosses = []
    for rid, r in P.rows(ps["GameAreaParam"])[0]:
        if rid < 1000 or 9999990 <= rid <= 9999999:
            continue
        runes = struct.unpack_from("<i", r, 4)[0]
        x, y, z = struct.unpack_from("<3f", r, 0x48)
        area, gx, gz = r[0x54], r[0x55], r[0x56]
        c = ct_by_flag.get(rid)
        name_en = loc = region = None
        if c:
            m = re.match(r"^(.*?)\s*(?:\((.*)\))?$", c["desc"])
            name_en, loc = m.group(1).strip(), m.group(2)
            region = c["group"].split("/")[-1] if c["group"] else None
        name_pl, named_by = None, "ct" if c else None
        nid = boss_name_by_entity.get(rid) or name_near_flag.get(rid)
        ent = enemies_by_entity.get(rid)
        if not nid and ent and ent[1]["npc"] in npc_rows:
            nid = struct.unpack_from("<i", npc_rows[ent[1]["npc"]], 0x0C)[0] or None
        if nid:                                        # nazwy z gry mają pierwszeństwo przed tabelą CE
            name_pl, named_by = npc_pl.get(nid), "game"
            name_en = npc_en.get(nid) or name_en
        if name_en and not name_pl:
            name_pl = en2pl.get(name_en.lower())
        letters = lambda s: re.sub(r"[^a-z]", "", (s or "").lower())
        rem = next((v for k, v in remembrance.items() if name_en and letters(k)[:10] == letters(name_en)[:10]), None)
        notable = ("weapon", "armor", "talisman", "ash_of_war", "sorcery", "incantation", "spirit_ash", "remembrance", "great_rune", "key_item", "bell_bearing")
        reward = []
        for lot in dict.fromkeys(reward_by_flag.get(rid, [])):
            reward += lot_items(lot)[0]
        placeholder = lambda it: it["cat"] == "armor" and it["id"] < 101000   # „Głowa/Tułów/…” (10000…, 100000…) = brak zbroi
        reward = [it for it in reward if not placeholder(it)]
        drop = (next((it for it in reward if it["kind"] in notable and it["icon"]), None)
                or next((it for it in reward if it["kind"] != "golden_rune" and it["icon"]), None))
        # pozycja: faktyczne rozmieszczenie bossa w pliku mapy (encja = flaga), zapasowo pola GameAreaParam
        pos = None
        if ent:
            ea, egx, egz = (int(v) for v in re.match(r"m(\d\d)_(\d\d)_(\d\d)", ent[0]).groups())
            pos = world.to_map(ea, egx, egz, *ent[1]["pos"])
            area, gx, gz = ea, egx, egz
        pos = pos or world.to_map(area, gx, gz, x, y, z)
        local = [round(c, 1) for c in (ent[1]["pos"] if ent else (x, y, z))]   # pozycja w układzie pliku mapy (map_id)
        # model 3D (cXXXX) — z części mapy o encji bossa, zapasowo wróg o tej samej nazwie (najpierw na tej mapie)
        cand = [ent] if ent else sorted(enemies_by_name.get(nid, []), key=lambda e: e[0] != msb.map_id(area, gx, gz))
        model = next((part_model(e[1]["name"]) for e in cand if e and part_model(e[1]["name"])), None)
        # postać ludzka (c0000): ekwipunek i wygląd z CharaInitParam/FaceParam — ID z części bossa albo imiennika na tej mapie
        same = sorted(enemies_by_name.get(nid, []), key=lambda e: e[0] != msb.map_id(area, gx, gz)) if nid else []
        chara_init = next((e[1]["chara_init"] for e in ([ent] if ent else []) + same if e and (e[1].get("chara_init") or 0) > 0), None) if model == "c0000" else None
        flag = field_defeat.get(rid, rid)
        npc_id = next((e[1]["npc"] for e in ([ent] if ent else []) + same if e and e[1]["npc"] in npc_rows), None)
        bosses.append({**({"stats": enemy_stats(npc_rows[npc_id], speffects, resist_correct), "mask": display_mask(npc_rows[npc_id])} if npc_id else {}),"id": rid, "flag": flag, "name": name_pl or name_en, "name_en": name_en, "location": loc, "region": region,
                       "region_pl": region_pl.get((region or "").lower()) or region,
                       "runes": runes, "map_id": msb.map_id(area, gx, gz), "dlc": area in DLC_AREAS or bool(c and c["group"].startswith("DLC")),
                       "icon": (rem and rem.get("icon")) or (drop and drop["icon"]), "remembrance": rem and rem.get("remembrance"),
                       "rewards": [{"name": it["name"], "icon": it["icon"], "kind": it["kind"]} for it in reward if it["name"]],
                       "named_by": named_by, "model": model, "chara_init": chara_init, "pos": local,
                       # bossowie dużej mapy (Radahn, Borealis) zapisują śmierć pod flagą z prefiksem 12 zamiast 10
                       "alt_flags": [flag + 200000000] if 1000000000 <= flag < 1100000000 and (flag + 200000000) // 1000 in flag_blocks() else [],
                       **(pos or {})})

    # ---------- jednorazowe łupy przeciwników: znaczniki jak skarby, z nazwą przeciwnika ----------
    treasure_lots = {t["lot"] for t in treasures}
    not_drops = {b["id"] for b in bosses} | {b["flag"] for b in bosses} | {x["id"] for x in invaders}
    n_drops = 0
    for entity, (mid, part) in sorted(enemies_by_entity.items()):
        lot = enemy_drop.get(entity) or (entity if entity in lots and struct.unpack_from("<I", lots[entity], 0x80)[0] else 0)
        if not lot or lot in treasure_lots or entity in not_drops or not part["pos"]:
            continue
        model = part_model(part["name"])
        row = npc_rows.get(part["npc"])
        name = npc_pl.get(struct.unpack_from("<i", row, 0x0C)[0]) if row else None
        name = "Skarabeusz" if model in SCARAB_MODELS else name if name and "dummy" not in name.lower() else None
        n_drops += place_lot(lot, mid, part["pos"], enemy={"name": name, **({"stats": enemy_stats(row, speffects, resist_correct)} if row else {})})
    print(f"  jednorazowe łupy przeciwników na mapie: {n_drops}")

    # ---------- miejsca ----------
    # WorldMapPointParam: +0x04 flaga pokazania punktu (6001 = zawsze), +0x0C ikona MENU_MAP_<id>, +0x30 + 12·i do 8 napisów
    # (tekst, flaga włączenia, flaga wyłączenia; flaga < 10 = zawsze), +0x90 + i rodzaj napisu (0 miejsce z PlaceName,
    # 1 postać z NpcName: gra dopisuje pod miejscem, kto tam teraz stoi, np. Blaidd po spotkaniu).
    # Napisy z flagami to stany świata (krater po Radahnie: 9417, Leyndell w popiele: 118) i prośby Wulkanicznego Dworu.
    map_icons = {int(k) for k in json.load(open(os.path.join(A.ROOT, "assets", "cache", "mapicons", "layout.json"), encoding="utf-8"))}
    pois = []
    for rid, r in P.rows(ps["WorldMapPointParam"])[0]:
        names, people = [], []
        for i in range(8):
            tid, on, off = struct.unpack_from("<3i", r, 0x30 + 12 * i)
            text = (places if r[0x90 + i] == 0 else npc_pl).get(tid)
            if text:
                (names if r[0x90 + i] == 0 else people).append([text.strip(), on if on >= 10 else 0, off if off >= 10 else 0])
        if not names and not people:
            continue
        # a point with only character names is the game's own character marker (hooded figure), name null
        name = names[0][0] if names else None
        area, gx, gz = r[0x20], r[0x21], r[0x22]
        local = struct.unpack_from("<3f", r, 0x24)
        pos = world.to_map(area, gx, gz, *local)
        show, icon = struct.unpack_from("<i", r, 0x04)[0], struct.unpack_from("<H", r, 0x0C)[0]
        if pos:
            pois.append({"id": rid, "name": name, "category": poi_category(name) if name else "npc", "map_id": msb.map_id(area, gx, gz),
                         "dlc": area in DLC_AREAS, "pos": [round(c, 1) for c in local], "flag": 0 if show == 6001 else show,
                         "icon": icon if icon in map_icons else None,
                         **({"names": names} if len(names) > 1 or (names and (names[0][1] or names[0][2])) else {}),
                         **({"people": people} if people else {}), **pos})

    # powtórzony wiersz w tym samym punkcie odpada, chyba że ma inne napisy z flagami (np. Wielka Winda Rold)
    seen_poi, uniq = set(), []
    for p_ in pois:
        k = (p_["name"], p_.get("map"), round(p_.get("px") or 0, -1), round(p_.get("py") or 0, -1), json.dumps(p_.get("names")), json.dumps(p_.get("people")))
        if k not in seen_poi:
            seen_poi.add(k)
            uniq.append(p_)
    pois = uniq
    # NPC: ta sama postać w kilku fazach questa stoi w tym samym miejscu — jeden znacznik na postać i okolicę (~40 m)
    uniq = []
    for n_ in npcs:
        if not any(u["name"] == n_["name"] and u.get("map") == n_.get("map") and n_.get("px") is not None and u.get("px") is not None
                   and (u["px"] - n_["px"]) ** 2 + (u["py"] - n_["py"]) ** 2 < 40 ** 2 for u in uniq):
            uniq.append(n_)
    npcs = uniq
    # bossowie bez nazwy w grze: nazwa z angielskiej tabeli → polska (NpcName), np. Awatar cienistego słonecznika
    rem_boss = {x["remembrance"]: x["boss_en"] for x in json.load(open(os.path.join(DATA, "bosses.json"), encoding="utf-8")) if x.get("remembrance")}
    for b in bosses:
        if b["name"] or not b.get("rewards"):
            continue
        rem = next((r["name"] for r in b["rewards"] if r.get("kind") == "remembrance"), None)
        if rem and rem_boss.get(rem):                               # wizerunek → boss (EN) → polska nazwa z gry
            b["name_en"] = rem_boss[rem]
            b["name"], b["named_by"] = en2pl.get(rem_boss[rem].lower()) or rem_boss[rem], "remembrance"
            b["remembrance"] = rem
            continue
        # nagroda z imieniem bossa (np. „Glewia Lansseax”) → to ta sama walka co nazwany wpis — scalamy
        words = {w for r in b["rewards"] for w in re.findall(r"[A-ZŁŚŻŹĆ][\wąęółśżźćń]{4,}", r["name"] or "")}
        twin = next((x for x in bosses if x is not b and x["name"] and any(w in x["name"] for w in words)), None)
        if twin:
            twin.setdefault("alt_flags", []).append(b["flag"])
            twin["rewards"] = twin.get("rewards") or b["rewards"]
            b["merged_into"] = twin["flag"]
    bosses = [b for b in bosses if not b.get("merged_into")]
    # wizerunek przypisany po angielskiej nazwie trafia też do „cieni” i drugich walk (Godfrey-cień, drugi Tańczący Lew):
    # zostaje tylko przy walce z największą liczbą run
    by_rem = {}
    for b in bosses:
        if b.get("remembrance"):
            by_rem.setdefault(b["remembrance"], []).append(b)
    for rem, bs in by_rem.items():
        best = max(bs, key=lambda x: x.get("runes") or 0)
        for b in bs:
            if b is not best:
                b["remembrance"] = None
    # partnerzy walk w duecie (0 run, ta sama mapa co boss z runami) → dodatkowa flaga głównego bossa, bez osobnego wpisu
    merged = set()
    for b in bosses:
        if (b.get("runes") or 0) == 0 and not b["dlc"] and b["name"]:
            main_b = next((x for x in bosses if x is not b and x["map_id"] == b["map_id"] and (x.get("runes") or 0) > 0), None)
            if main_b:
                main_b.setdefault("alt_flags", []).append(b["flag"])
                merged.add(id(b))
    bosses = [b for b in bosses if id(b) not in merged]
    # bossowie bez własnej nagrody/wizerunku: ikona imiennika (kolejni Strażnicy Drzewa, Nocna Kawaleria…)
    icon_by_name = {}
    for b in bosses:
        if b["icon"] and b["name"]:
            icon_by_name.setdefault(re.sub(r"\s*\(.*\)$", "", b["name"]), b["icon"])
    for b in bosses:
        if not b["icon"] and b["name"]:
            b["icon"] = icon_by_name.get(re.sub(r"\s*\(.*\)$", "", b["name"]))
            b["icon_from"] = "namesake" if b["icon"] else None
    # region geograficznie: kraina najbliższej łaski na tej samej mapie (polskie nazwy z gry)
    graces = json.load(open(os.path.join(DATA, "graces.json"), encoding="utf-8"))
    # gra podstawowa: podkraina z menu podróży (Płaczący Półwysep, Nokron…) — widok bossów zagnieżdża ją w krainie;
    # DLC: w głównych lochach podkraina (Belurat, Enir-Ilim…), poza nimi kraina główna (drobne podkrainy DLC
    # nie mają miejsca w drzewie krain strony)
    def sub_or_region(g):
        legacy_dlc = 20 <= int((g.get("map_id") or "m00")[1:3]) <= 28      # główne lochy DLC
        return ((not g.get("dlc") or legacy_dlc) and g.get("subregion")) or g["region"]
    by_map = {}
    for g in graces:
        if g.get("region") and g.get("map_id") and g.get("pos"):
            by_map.setdefault(g["map_id"], []).append(g)
    graces = [g for g in graces if g.get("map") and g.get("region") and (g.get("map_id") or "")[:3] in ("m60", "m61")]   # tylko otwarty świat
    def nearest_region(o):
        mid = o.get("map_id") or ""
        if mid[:3] not in ("m60", "m61") and by_map.get(mid):        # loch: najbliższa łaska z tego samego pliku mapy
            return sub_or_region(min(by_map[mid], key=lambda g: sum((a - b) ** 2 for a, b in zip(g["pos"], o["pos"]))))
        # a map without graces (Chapel of Anticipation m10_01): PlaceName of the file, id AA*1000 + BB*10
        if mid[:3] not in ("m60", "m61") and places.get(int(mid[1:3]) * 1000 + int(mid[4:6]) * 10):
            return places[int(mid[1:3]) * 1000 + int(mid[4:6]) * 10].strip()
        same = [g for g in graces if g["map"] == o.get("map")]
        if not same or o.get("px") is None:
            return None
        g = min(same, key=lambda g: (g["px"] - o["px"]) ** 2 + (g["py"] - o["py"]) ** 2)
        return sub_or_region(g)
    for coll in (bosses, treasures, pois, npcs, invaders):
        for o in coll:
            o["region_pl"] = nearest_region(o) or o.get("region_pl")
            if o["region_pl"] == "Land of the Tower":                 # brak polskiej nazwy w grze
                o["region_pl"] = "Ziemie Wieży"
            if o["region_pl"] == "Nokron Eternal City":
                o["region_pl"] = "Nokron, Wieczne Miasto"
            if isinstance(o.get("name"), str):
                o["name"] = o["name"].strip()
    for b in bosses:                                               # opis miejsca z tabeli CE jest po angielsku — nie pokazujemy
        b["location"] = None

    # łaski w lochach (Farum Azula, Leyndell, podziemia, katakumby…): extract_data liczy tylko m60/m61 — tu przeliczamy
    # przez WorldMapLegacyConvParam jak bossów i skarby (główne lochy: dokładnie, małe lochy: przy wejściu, approx)
    gpath = os.path.join(DATA, "graces.json")
    all_graces = json.load(open(gpath, encoding="utf-8"))
    placed = 0
    for g in all_graces:
        if not g.get("map_id") or not g.get("pos") or g["map_id"][:3] in ("m60", "m61"):
            continue                                             # otwarty świat: z extract_data; lochy: zawsze od nowa
        area, gx, gz = (int(v) for v in g["map_id"][1:].split("_")[:3])
        pos = world.to_map(area, gx, gz, *g["pos"])
        if pos:
            g.update(pos)
            placed += 1
    with open(gpath, "w", encoding="utf-8") as f:
        json.dump(all_graces, f, ensure_ascii=False, indent=0)
    print(f"łaski w lochach umieszczone na mapie: {placed}, bez pozycji: {sum(1 for g in all_graces if not g.get('map'))}")

    for fn, data in (("bosses_all", bosses), ("pois", pois), ("item_locations", treasures), ("npcs", npcs), ("invaders", invaders)):
        with open(os.path.join(DATA, fn + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    placed = lambda L: sum(1 for x in L if x.get("map"))
    print(f"bossowie {len(bosses)} (z nazwą {sum(1 for b in bosses if b['name'])}, na mapie {placed(bosses)}, z ikoną {sum(1 for b in bosses if b['icon'])})")
    print(f"miejsca {len(pois)}, skarby {len(treasures)} (na mapie {placed(treasures)}), NPC {len(npcs)} (na mapie {placed(npcs)}), "
          f"najeźdźcy {len(invaders)} (na mapie {placed(invaders)}, z nagrodą {sum(1 for x in invaders if x['rewards'])})")


if __name__ == "__main__":
    main()
