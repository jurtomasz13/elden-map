"""Świat gry: bossowie, miejsca (lochy, ruiny…), przedmioty leżące na mapie, NPC — z pozycjami na mapie.

Wynik (assets/data/):
  bosses_all.json      — wszyscy bossowie (GameAreaParam): flaga pokonania, runy, nazwy PL/EN, region, pozycja, ikona
  pois.json            — miejsca z WorldMapPointParam (lochy, ruiny, kościoły…) z kategorią
  item_locations.json  — skarby z plików map (MSB): pula łupu, flaga podniesienia, przedmioty, kategoria, pozycja
  npcs.json            — NPC z dialogiem (MSB: wróg z TalkID) z nazwą PL i pozycją
Pozycje: mapy m60/m61 przeliczane wprost (map_transform), lochy przez WorldMapLegacyConvParam
(łańcuchy aż do m60/m61). Małe lochy (katakumby, jaskinie, tunele, lochy DLC) ląduje przy wejściu (`approx`).
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import msb  # noqa: E402
import params as P  # noqa: E402
from extract_data import TRANSFORM  # noqa: E402

DATA = os.path.join(A.ROOT, "assets", "data")
ENTRANCE_AREAS = {12, 30, 31, 32, 39, 40, 41, 42, 43}      # małe lochy -> punkt wejścia
DLC_AREAS = {20, 21, 22, 25, 28, 40, 41, 42, 43, 61}
LOT_CATS = {1: "goods", 2: "weapon", 3: "armor", 4: "talisman", 5: "ash_of_war"}


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
        return None

    def to_map(self, area, gx, gz, x, y, z):
        w = self.to_overworld(area, gx, gz, x, y, z)
        if not w:
            return None
        a, gx, gz, x, y, z, approx = w
        for key, t in TRANSFORM.items():
            if t["area"] == a:
                return {"map": key, "px": round(gx * 256 + x + 128 - t["ox"], 1),
                        "py": round(t["size"] - (gz * 256 + z + 128 - t["oz"]), 1), "approx": bool(approx)}
        return None


def discover_msbs(cache_path):
    """Lista plików map (MSB) istniejących w archiwach — nazwy zgadywane i sprawdzane hashem."""
    import bhd
    arcs = [A.Archive(n) for n in bhd.ARCHIVES]
    found = []
    for area in list(range(10, 46)) + [60, 61]:
        xs, zs = (range(100), range(100)) if area in (60, 61) else (range(30), range(3))
        for a in xs:
            for b in zs:
                p = f"/map/mapstudio/m{area:02d}_{a:02d}_{b:02d}_00.msb.dcx"
                if any(A.path_hash(p) in arc.files for arc in arcs):
                    found.append(p)
    with open(cache_path, "w") as f:
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


def map_id_of(path):
    m = re.search(r"m(\d\d)_(\d\d)_(\d\d)_(\d\d)", path)
    return tuple(int(v) for v in m.groups()[:3])


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
             ("mogilnik", "hero_grave"),
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
    npc_pl = {**tp.get("NpcName", {}), **tp.get("NpcName_dlc01", {})}
    npc_en = {**te.get("NpcName", {}), **te.get("NpcName_dlc01", {})}
    en2pl = {v.lower(): npc_pl.get(k) for k, v in npc_en.items() if npc_pl.get(k)}
    places = {**tp.get("PlaceName", {}), **tp.get("PlaceName_dlc01", {}), **tp.get("PlaceName_dlc02", {})}
    places_en = {**te.get("PlaceName", {}), **te.get("PlaceName_dlc01", {}), **te.get("PlaceName_dlc02", {})}
    region_pl = {v.lower(): places.get(k) for k, v in places_en.items() if places.get(k)}
    region_pl.update({"liurnia": region_pl.get("liurnia of the lakes"), "altus plateau": region_pl.get("altus plateau"),
                      "mountaintops": region_pl.get("mountaintops of the giants"), "leyndell": region_pl.get("leyndell, royal capital")})
    items = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
    by_item = {(i["category"], i["id"]): i for i in items}
    goods_type = {rid: r[0x3E] for rid, r in P.rows(ps["EquipParamGoods"])[0]}
    npc_rows = dict(P.rows(ps["NpcParam"])[0])
    lots = dict(P.rows(ps["ItemLotParam_map"])[0])

    def lot_items(lot_id):
        r = lots.get(lot_id)
        if not r:
            return [], 0
        ids, cats = struct.unpack_from("<8i", r, 0), struct.unpack_from("<8i", r, 0x20)
        nums = r[0x8A:0x92]
        out = []
        for i, (iid, c) in enumerate(zip(ids, cats)):
            cat = LOT_CATS.get(c)
            if not iid or not cat:
                continue
            base = iid - iid % 10000 if cat == "weapon" else iid
            it = by_item.get((cat, iid)) or by_item.get((cat, base))
            name = it["name"] if it else None
            if not name:                                       # przedmioty bez nazwy w grze (atrapy, wycięte) — pomijamy
                continue
            out.append({"cat": cat, "id": iid, "name": name, "name_en": it and it["name_en"], "icon": it and it["icon"],
                        "count": nums[i] or 1, "kind": item_category(cat, iid, goods_type.get(iid), name)})
        return out, struct.unpack_from("<I", r, 0x80)[0]

    # ---------- przejście po wszystkich plikach map ----------
    msb_cache = os.path.join(A.ROOT, "assets", "cache", "msb_list.txt")
    msb_list = ([ln.strip() for ln in open(msb_cache) if ln.strip()] if os.path.exists(msb_cache) else discover_msbs(msb_cache))
    treasures, npcs, enemies_by_entity, enemies_by_name = [], [], {}, {}
    for i, path in enumerate(msb_list):
        m = msb.load(path)
        if not m:
            continue
        area, gx, gz = map_id_of(path)
        mid = f"m{area:02d}_{gx:02d}_{gz:02d}_00"
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
                                 "talk": p["talk"], **(pos or {})})
        for t in m["treasures"]:
            if t["lot"] <= 0 or not t["pos"]:
                continue
            its, flag = lot_items(t["lot"])
            k = 1                                      # kolejne pule (lot+1, lot+2…) to dodatkowe przedmioty z tego samego miejsca
            while t["lot"] + k in lots and k < 8:
                more, _ = lot_items(t["lot"] + k)
                its += more
                k += 1
            if not its:
                continue
            pos = world.to_map(area, gx, gz, *t["pos"])
            treasures.append({"lot": t["lot"], "flag": flag, "map_id": mid, "items": its,
                              "kind": min((i["kind"] for i in its), key=lambda k: KIND_PRIORITY.index(k) if k in KIND_PRIORITY else 99),
                              "dlc": area in DLC_AREAS,
                              "pos": [round(c, 1) for c in t["pos"]],    # lokalnie w pliku mapy (do łask w tym samym lochu)
                              **(pos or {})})
        if i % 100 == 0:
            print(f"  mapy {i}/{len(msb_list)}", flush=True)

    # ---------- skrypty zdarzeń (EMEVD): nazwy bossów i nagrody ----------
    # Wspólne zdarzenia: 90005870 (pasek życia bossa: encja, ID nazwy w NpcName),
    # 90005860 (nagroda za bossa polowego: flaga, 0, encja, 0, pula ItemLotParam_map).
    # Nagrody — tylko pewne źródła:
    #  a) wywołania wspólnych funkcji przyznających łup (common_func: AwardItemLot / AwardItemsIncludingClients
    #     z parametrem), pula czytana z dokładnej pozycji argumentu, i tylko gdy w tym samym wywołaniu jest flaga bossa;
    #  b) zdarzenia mapy z literalnym AwardItemLot, które sprawdzają flagę tego bossa (i tylko jednego bossa).
    import emevd as E
    award_src = {}
    for eid, ev in (E.load("/event/common_func.emevd.dcx") or {}).items():
        for k, (bank, iid, _a) in enumerate(ev["instrs"]):
            if (bank, iid) in ((2003, 4), (2003, 36)):
                award_src.setdefault(eid, []).extend(p[2] for p in ev["params"] if p[0] == k)
    boss_name_by_entity, reward_by_flag, name_near_flag, global_flag, reward_by_global = {}, {}, {}, {}, {}
    global_flag_weak = {}
    ga_flags = {rid for rid, _ in P.rows(ps["GameAreaParam"])[0] if rid > 1000 and not 9999990 <= rid <= 9999999}
    for path in msb_list:
        evs = E.load(path.replace("/map/mapstudio/", "/event/").replace(".msb.dcx", ".emevd.dcx"))
        if not evs:
            continue
        for ev in evs.values():
            ev_flags, ev_lots = set(), []
            for bank, iid, a in ev["instrs"]:
                x = E.ints(a)
                if (bank, iid) == (2000, 6) and len(x) >= 2:          # InitializeCommonEvent(0, id, args...)
                    cid, args = x[1], a[8:]
                    cargs = E.ints(args)
                    if cid == 90005870 and len(cargs) >= 2 and cargs[1] in npc_pl:
                        boss_name_by_entity.setdefault(cargs[0], cargs[1])
                    if cid in award_src:
                        flags_here = [v for v in cargs if v in ga_flags]
                        for src in award_src[cid]:
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
        cand = [ent] if ent else sorted(enemies_by_name.get(nid, []), key=lambda e: e[0] != f"m{area:02d}_{gx:02d}_{gz:02d}_00")
        model = next((re.match(r"(c\d{4})_", e[1]["name"]).group(1) for e in cand if e and re.match(r"c\d{4}_", e[1]["name"])), None)
        # postać ludzka (c0000): ekwipunek i wygląd z CharaInitParam/FaceParam — ID z części bossa albo imiennika na tej mapie
        same = sorted(enemies_by_name.get(nid, []), key=lambda e: e[0] != f"m{area:02d}_{gx:02d}_{gz:02d}_00") if nid else []
        chara_init = next((e[1]["chara_init"] for e in ([ent] if ent else []) + same if e and (e[1].get("chara_init") or 0) > 0), None) if model == "c0000" else None
        bosses.append({"id": rid, "flag": rid, "name": name_pl or name_en, "name_en": name_en, "location": loc, "region": region,
                       "region_pl": region_pl.get((region or "").lower()) or region,
                       "runes": runes, "map_id": f"m{area:02d}_{gx:02d}_{gz:02d}_00", "dlc": area in DLC_AREAS or bool(c and c["group"].startswith("DLC")),
                       "icon": (rem and rem.get("icon")) or (drop and drop["icon"]), "remembrance": rem and rem.get("remembrance"),
                       "rewards": [{"name": it["name"], "icon": it["icon"], "kind": it["kind"]} for it in reward if it["name"]],
                       "named_by": named_by, "model": model, "chara_init": chara_init, "pos": local,
                       # bossowie dużej mapy (Radahn, Borealis) zapisują śmierć pod flagą z prefiksem 12 zamiast 10
                       "alt_flags": [rid + 200000000] if 1000000000 <= rid < 1100000000 and (rid + 200000000) // 1000 in flag_blocks() else [],
                       **(pos or {})})

    # ---------- miejsca ----------
    pois = []
    for rid, r in P.rows(ps["WorldMapPointParam"])[0]:
        name = places.get(struct.unpack_from("<i", r, 0x30)[0])
        if not name:
            continue
        area, gx, gz = r[0x20], r[0x21], r[0x22]
        pos = world.to_map(area, gx, gz, *struct.unpack_from("<3f", r, 0x24))
        if pos:
            pois.append({"id": rid, "name": name, "category": poi_category(name), "map_id": f"m{area:02d}_{gx:02d}_{gz:02d}_00",
                         "dlc": area in DLC_AREAS, **pos})

    seen_poi, uniq = set(), []
    for p_ in pois:
        k = (p_["name"].strip(), p_.get("map"), round(p_.get("px") or 0, -1), round(p_.get("py") or 0, -1))
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
    # bez ikony: render modelu 3D z plików gry (tools/extract/render_bosses.py -> assets/renders/<model>.png)
    for b in bosses:
        if not b["icon"] and b.get("model") and os.path.exists(os.path.join(A.ROOT, "assets", "renders", b["model"] + ".png")):
            b["render"] = b["model"]

    # region geograficznie: kraina najbliższej łaski na tej samej mapie (polskie nazwy z gry)
    graces = json.load(open(os.path.join(DATA, "graces.json"), encoding="utf-8"))
    be = os.path.join(A.ROOT, "backend", "data", "graces.json")     # krainy łask DLC (EN) z danych backendu, po fladze
    if os.path.exists(be):
        dlc_region = {e["flag"]: e.get("region") for e in json.load(open(be, encoding="utf-8")).get("entries", [])}
        for g in graces:
            if not g.get("region") and dlc_region.get(g["flag"]):
                g["region"] = region_pl.get(dlc_region[g["flag"]].lower()) or dlc_region[g["flag"]]
    by_map = {}
    for g in graces:
        if g.get("region") and g.get("map_id"):
            by_map.setdefault(g["map_id"], []).append(g["region"])
    graces = [g for g in graces if g.get("map") and g.get("region")]
    def nearest_region(o):
        mid = o.get("map_id") or ""
        if mid[:3] not in ("m60", "m61") and by_map.get(mid):        # loch: kraina łask z tego samego pliku mapy
            regs = by_map[mid]
            return max(set(regs), key=regs.count)
        same = [g for g in graces if g["map"] == o.get("map")]
        return min(same, key=lambda g: (g["px"] - o["px"]) ** 2 + (g["py"] - o["py"]) ** 2)["region"] if same and o.get("px") is not None else None
    for coll in (bosses, treasures, pois, npcs):
        for o in coll:
            o["region_pl"] = nearest_region(o) or o.get("region_pl")
            if o["region_pl"] == "Land of the Tower":                 # brak polskiej nazwy w grze
                o["region_pl"] = "Kraina Wieży"
            if o["region_pl"] == "Nokron Eternal City":
                o["region_pl"] = "Nokron, Wieczne Miasto"
            if isinstance(o.get("name"), str):
                o["name"] = o["name"].strip()
    for b in bosses:                                               # opis miejsca z tabeli CE jest po angielsku — nie pokazujemy
        b["location"] = None

    for fn, data in (("bosses_all", bosses), ("pois", pois), ("item_locations", treasures), ("npcs", npcs)):
        with open(os.path.join(DATA, fn + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    placed = lambda L: sum(1 for x in L if x.get("map"))
    print(f"bossowie {len(bosses)} (z nazwą {sum(1 for b in bosses if b['name'])}, na mapie {placed(bosses)}, z ikoną {sum(1 for b in bosses if b['icon'])})")
    print(f"miejsca {len(pois)}, skarby {len(treasures)} (na mapie {placed(treasures)}), NPC {len(npcs)} (na mapie {placed(npcs)})")


if __name__ == "__main__":
    main()
