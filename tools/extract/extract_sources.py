"""Skąd zdobyć przedmiot (poza leżeniem na mapie): kupcy, łup z przeciwników, nagrody za bossów → assets/data/item_sources.json.

Źródła w plikach gry:
- Kupcy: ShopLineupParam (+0x00 ID przedmiotu, +0x04 cena, +0x17 typ: 0 broń, 1 zbroja, 2 talizman, 3 goods, 4 popiół wojny).
  Który kupiec sprzedaje który zakres wierszy: ze skryptów rozmów `/script/talk/<mapa>.talkesdbnd.dcx` (t<TalkID>.esd):
  wywołanie otwarcia sklepu ma argumenty (początek, koniec) zakresu wierszy; literał int w wyrażeniu ESD = bajt 0x82 + i32.
  TalkID → część MSB (dane wroga +0x10) → NpcParam (+0x0C nazwa) → imię kupca i miejsce na mapie.
- Przeciwnicy: NpcParam +0x30 → ItemLotParam_enemy (łup losowy), +0x34 → ItemLotParam_map (łup jednorazowy).
  Wiersz puli: +0x00 8×i32 ID, +0x20 8×i32 kategoria, +0x40 8×u16 waga losowania (szansa = waga / suma wag), +0x8A liczba.
  Położenie przeciwników: wszystkie części MSB z danym NpcParamID → assets/data/enemies.json ([mapa, px, py] raz na
  część), a grupa w item_sources.json ma tylko numery wierszy tego pliku (`at`).
- Bossowie: nagrody z bosses_all.json (po nazwie przedmiotu).
- Najeźdźcy: nagrody z invaders.json (extract_world.py); ich pule nie są już osobnym „zdarzeniem”.
- Popioły wojny na gotowej broni (EquipParamCustomWeapon +0x04 popiół): da się je zdjąć przy łasce, więc źródłem popiołu
  jest broń, którą da się zdobyć (pula kategorii 6 albo sklep rodzaju 5), np. Przebijający kieł z Nagakiby Yury.
- Podarunki od postaci: w skrypcie rozmowy wywołanie podprogramu (blok poleceń 6) z jednym argumentem, który jest pulą
  ItemLotParam_map (np. Wielki Dzban daje „Arsenał wielkiego naczynia”: t221006000, pula 104700).
"""
import json
import os
import re
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import formats as F  # noqa: E402
import emevd  # noqa: E402
import esd  # noqa: E402
import msb  # noqa: E402
import params as P  # noqa: E402
from talk_quests import ints  # noqa: E402
from extract_world import DATA, World, award_params, item_index, lot_ids, lot_item, lot_slots, maps, tile_ids  # noqa: E402

SHOP_TYPES = {0: "weapon", 1: "armor", 2: "talisman", 3: "goods", 4: "ash_of_war", 5: "custom_weapon"}
# ShopLineupParam +0x18 rodzaj kosztu (wniosek z przedmiotów w wierszach): 1 = Serce smoka (ołtarze Smoczej Komunii),
# 5 = Serce Bayle'a (dwie inkantacje Bayle'a); 4 = powielanie popiołu wojny (usługa, nie źródło)
COST_GOODS = {1: 10060, 5: 2008011}


def main():
    ps = P.load_params()
    world = World(ps)
    tp = P.load_texts("polpl")
    npc_names = {**tp.get("NpcName", {}), **tp.get("NpcName_dlc01", {}), **tp.get("NpcName_dlc02", {})}
    items = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
    by_item = item_index(items)
    by_name = {}
    for i in items:
        by_name.setdefault(i["name"], i)
    npc_rows = dict(P.rows(ps["NpcParam"])[0])
    lot_enemy = dict(P.rows(ps["ItemLotParam_enemy"])[0])
    lot_map = dict(P.rows(ps["ItemLotParam_map"])[0])
    custom = dict(P.rows(ps["EquipParamCustomWeapon"])[0])
    shop_rows = P.rows(ps["ShopLineupParam"])[0]
    shop_ids = [rid for rid, _ in shop_rows]
    shop = dict(shop_rows)
    mtrl = dict(P.rows(ps["EquipMtrlSetParam"])[0])

    def trade_item(row):
        """Wymiana: wiersz sklepu z materiałem (+0x08 EquipMtrlSetParam → +0x00 ID goods), np. wizerunek u Enii."""
        mid_ = struct.unpack_from("<i", row, 0x08)[0]
        r = mtrl.get(mid_)
        if not r:
            return None
        mid0 = struct.unpack_from("<i", r, 0)[0]
        it = next((by_item[(c, mid0)] for c in ("goods", "armor", "weapon", "talisman") if (c, mid0) in by_item), None)
        return it["name"] if it else None

    def key(cat, iid):
        if cat == "weapon":
            iid -= iid % 10000
        it = by_item.get((cat, iid))
        return f"{cat}:{it['id']}" if it and it.get("name") else None

    def lot_entries(table, lot):
        """(klucz przedmiotu, szansa %, liczba) z puli i kolejnych wierszy (lot+1…)."""
        out = []
        for lid in lot_ids(table, lot):
            slots = list(lot_slots(table[lid]))
            tot = sum(pt for _, _, pt, _ in slots) or 1
            for iid, c, pt, n in slots:
                cat, iid = lot_item(c, iid, custom)
                kk = key(cat, iid) if iid and cat else None
                if kk and pt:
                    out.append((kk, round(pt / tot * 100, 1), n or 1))
        return out

    # ---------- przejście po mapach: przeciwnicy i kupcy (części z TalkID) ----------
    enemy_spots = defaultdict(list)          # npc id -> [(map_id, pos dict)], każda część raz
    talk_parts = defaultdict(list)           # talk id -> [(map_id, npc, pos)]
    for _path, (area, gx, gz), mid, m in maps():
        for p in m["parts"]:
            if p["type"] != "enemy" or not p.get("npc"):
                continue
            pos = world.to_map(area, gx, gz, *p["pos"]) or {}
            pos = {**pos, "model": p["name"].split("_")[0]}
            enemy_spots[p["npc"]].append((mid, pos))
            if p.get("talk") not in (None, -1, 0):
                talk_parts[p["talk"]].append((mid, p["npc"], pos))

    # ---------- łup z przeciwników: wszystkie miejsca, grupy po imieniu albo modelu ----------
    handed = []                              # (pula, numer) naprawdę dawane w grze: do popiołów na gotowej broni
    placed = []                              # enemies.json: [mapa, px, py] przeciwników z łupem
    enemies = defaultdict(lambda: defaultdict(lambda: {"chance": 0, "count": 0, "at": [], "npcs": set()}))
    for npc, spots in enemy_spots.items():
        r = npc_rows.get(npc)
        if not r:
            continue
        name_id = struct.unpack_from("<i", r, 0x0C)[0]
        name = npc_names.get(name_id)
        if not name or "dummy" in name.lower() or name.startswith("["):
            name = "#" + spots[0][1].get("model", "?")            # zwykli przeciwnicy nie mają nazw w grze — grupujemy po modelu
        drops = []
        for off, table in ((0x30, lot_enemy), (0x34, lot_map)):
            lot = struct.unpack_from("<i", r, off)[0]
            if lot > 0:
                drops += lot_entries(table, lot)
                handed.append((table, lot))
        if not drops:
            continue
        at = []
        for mid, pos in spots:
            if pos.get("map"):
                placed.append([pos["map"], pos["px"], pos["py"]])
                at.append(len(placed) - 1)
        for kk, chance, _n in drops:
            e = enemies[kk][name]
            e["chance"] = max(e["chance"], chance)
            if npc in e["npcs"]:                 # ten sam przedmiot w dwóch wierszach puli: miejsca liczone raz
                continue
            e["npcs"].add(npc)
            e["count"] += len(spots)
            e["at"] += at

    # ---------- kupcy: zakresy sklepów ze skryptów rozmów ----------
    shop_owner = defaultdict(list)           # (start, end) -> talk ids whose script opens this range
    gift_talks = defaultdict(set)            # pula -> {talk id}, przedmioty dawane w rozmowie
    talk_tiles = {}                          # talk id -> kafel otwartego świata z flag skryptu (rozmowa bez postaci na mapie)
    talk_files = set(tile_ids()) | {"m60_00_00_00", "m61_00_00_00", "m00_00_00_00"}      # rozmowy z otwartego świata są we wspólnych archiwach
    for mid in sorted(talk_files):
        r = A.find(f"/script/talk/{mid}.talkesdbnd.dcx")
        if not r:
            continue
        for _, n, d in F.bnd4(r[1]):
            mt = re.search(r"t(\d+)\.esd", n)
            if not mt:
                continue
            talk = int(mt.group(1))
            lits = [struct.unpack_from("<i", d, m.start() + 1)[0] for m in re.finditer(rb"\x82", d) if m.start() + 5 <= len(d)]
            for a, b in zip(lits, lits[1:]):
                # zakres (początek, koniec); początek nie musi być istniejącym wierszem (np. wymiany u Enii od 9000000)
                if a <= b < a + 1000 and a >= 100000 and (a in shop or (a % 25 == 0 and any(a <= x <= b for x in shop_ids))):
                    if talk not in shop_owner[(a, b)]:
                        shop_owner[(a, b)].append(talk)
            for _, _, entry, conds in esd.Esd(d).states():
                for b, _, a in list(entry) + [c for _, pc in conds for c in pc]:
                    v = ints(a)
                    if b == 6 and len(v) == 1 and v[0] in lot_map:
                        gift_talks[v[0]].add(talk)
            # flagi 10XXYY…/20XXYY… należą do kafla m60_XX_YY / m61_XX_YY (np. Wielki Dzban: 1047419201 → m60_47_41)
            tiles = [(59 + v // 1000000000, v // 1000000 % 100, v // 10000 % 100) for v in lits
                     if 1000000000 <= v < 2100000000 and v // 100000000 in (10, 20)]
            if tiles:
                talk_tiles[talk] = max(set(tiles), key=tiles.count)

    # a one-row "range" inside another seller's range is a script checking that row (e.g. the Dragon Communion
    # priestess reads 100690 from the Twin Maiden Husks' stock), not a shop of its own
    for a, b in [r for r in shop_owner if r[0] == r[1]]:
        if any(x < y and x <= a <= y for x, y in shop_owner):
            del shop_owner[(a, b)]

    def talk_owner(talk):
        """Imię postaci o tym TalkID i jej miejsce na mapie (z części MSB)."""
        who, spot = None, None
        for mid, npc, pos in talk_parts.get(talk, []):
            r = npc_rows.get(npc)
            nm = npc_names.get(struct.unpack_from("<i", r, 0x0C)[0]) if r else None
            if nm and "dummy" in nm.lower():
                nm = None
            if nm and not who:
                who = nm
            if pos.get("map") and not spot:
                spot = {"map": pos["map"], "px": pos["px"], "py": pos["py"], "map_id": mid}
        if not spot and talk in talk_tiles:                  # obiekt bez części postaci (np. Wielki Dzban): środek kafla
            area, gx, gz = talk_tiles[talk]
            pos = world.to_map(area, gx, gz, 0, 0, 0)
            spot = pos and {"map": pos["map"], "px": pos["px"], "py": pos["py"], "map_id": msb.map_id(area, gx, gz), "approx": True}
        return who, spot

    shops = defaultdict(list)
    shop_custom = set()                      # gotowe bronie w sklepach (do popiołów wojny niżej)
    # towar każdego sklepu (TalkID -> wiersze): ShopLineupParam +0x0C flaga wyprzedania, +0x10 flaga odblokowania
    # (np. po oddaniu dzwonka), +0x14 liczba sztuk (-1 bez limitu); stan z save'a czyta strona przez /api/flags
    stock = defaultdict(lambda: {"who": None, "rows": []})
    # a range is also listed by shared scripts without a character on the map (e.g. 800001100 for nomadic merchants);
    # when a script of a placed character opens it too (Kalé 800006000), that character is the seller
    sellers = [((a, b), t) for (a, b), talks in shop_owner.items()
               for t in ([t for t in talks if talk_parts.get(t)] or talks)]
    for (a, b), talk in sellers:
        who, spot = talk_owner(talk)
        if talk == 1000 or 110000 <= a <= 111399:   # menu miejsca łaski: przeróbka odzienia (za oryginalną część)
            who, spot = "Przeróbka przy miejscu łaski", None
        if not who and talk // 1000000 == 800:     # skrypty 800… = koczowniczy kupcy (bez części o tym TalkID na mapie)
            who = "Koczowniczy kupiec"
        for rid in shop_ids:
            if a <= rid <= b:
                row = shop[rid]
                eid, price = struct.unpack_from("<ii", row, 0)
                stype = SHOP_TYPES.get(row[0x17])
                trade = trade_item(row) or (by_item[("goods", COST_GOODS[row[0x18]])]["name"] if row[0x18] in COST_GOODS else None)
                if 0 <= price <= 1 and not trade:            # usługi (np. duplikowanie u kowala), nie zakup
                    continue
                if stype == "custom_weapon":
                    shop_custom.add(eid)
                    stype, eid = lot_item(6, eid, custom)
                kk = key(stype, eid) if stype else None
                if kk:
                    stock[talk]["who"] = who or "Kupiec"
                    stock[talk]["rows"].append({"item": kk, "price": price if price > 0 and not trade else None, **({"trade": trade} if trade else {}),
                                                "qty": struct.unpack_from("<h", row, 0x14)[0],
                                                "sold": struct.unpack_from("<I", row, 0x0C)[0], "unlock": struct.unpack_from("<I", row, 0x10)[0]})
                if kk and not any(s["who"] == (who or "Kupiec") for s in shops[kk]):
                    shops[kk].append({"who": who or "Kupiec", "price": price if price > 0 and not trade else None,
                                      **({"trade": trade} if trade else {}), **(spot or {})})

    # ---------- nagrody ze skryptów zdarzeń (questy, podarunki NPC): AwardItemLot ----------
    treasure_lots = {t["lot"] for t in json.load(open(os.path.join(DATA, "item_locations.json"), encoding="utf-8"))}

    common = emevd.load("/event/common_func.emevd.dcx") or {}
    common_aw = award_params(common)
    event_award = defaultdict(set)           # lot -> {map_id}
    for mid in tile_ids() + ["common"]:
        evs = emevd.load(f"/event/{mid}.emevd.dcx")
        if not evs:
            continue
        local_aw = award_params(evs)
        for eid, ev in evs.items():
            for ii, (bank, iid, args) in enumerate(ev["instrs"]):
                v = emevd.ints(args)
                if bank == 2003 and iid in (4, 36) and v and not any(pi == ii for pi, *_ in ev["params"]):
                    event_award[v[0]].add(mid)
                elif bank == 2000 and iid in (0, 6) and len(v) >= 2:
                    srcs = local_aw.get(v[1], set()) | common_aw.get(v[1], set())
                    for src in srcs:
                        k = 8 + src
                        if k + 4 <= len(args):
                            event_award[struct.unpack_from("<i", args, k)[0]].add(mid)
    gifts = defaultdict(list)
    for lot, talks in gift_talks.items():
        # pula wywoływana w wielu rozmowach naraz to wspólny podprogram (np. ulepszenie flaszki), nie podarunek
        if lot in treasure_lots or len({t // 1000000 for t in talks}) > 3:
            continue
        for talk in sorted(talks):
            who, spot = talk_owner(talk)
            handed.append((lot_map, lot))
            for kk, _chance, _n in lot_entries(lot_map, lot):
                if not any(g["who"] == who for g in gifts[kk]):
                    gifts[kk].append({"who": who, **(spot or {})})
    invaders = json.load(open(os.path.join(DATA, "invaders.json"), encoding="utf-8"))
    invader_lots = {lot for x in invaders for lot in x["lots"]}
    events_src = defaultdict(list)
    for lot, mids in event_award.items():
        if lot <= 0 or lot in treasure_lots or lot in invader_lots or lot in gift_talks or lot not in lot_map:
            continue
        handed.append((lot_map, lot))
        for kk, chance, _n in lot_entries(lot_map, lot):
            for mid in sorted(mids):
                if mid != "common" and mid not in events_src[kk]:
                    events_src[kk].append(mid)
                elif mid == "common" and "common" not in events_src[kk]:
                    events_src[kk].append("common")

    # ---------- bossowie ----------
    bosses = json.load(open(os.path.join(DATA, "bosses_all.json"), encoding="utf-8"))
    boss_src = defaultdict(list)
    for b in bosses:
        for rw in b.get("rewards") or []:
            it = by_name.get(rw.get("name"))
            if it:
                kk = f"{it['category']}:{it['id']}"
                if b["id"] not in boss_src[kk]:
                    boss_src[kk].append(b["id"])

    # ---------- popioły wojny na gotowej broni, którą da się zdobyć ----------
    handed += [(lot_map, lot) for lot in treasure_lots | invader_lots if lot in lot_map]
    lot_custom = {iid for table, lot in handed for lid in lot_ids(table, lot) for iid, c, _w, _n in lot_slots(table[lid]) if c == 6}
    on_weapon = defaultdict(list)
    for cid in sorted(lot_custom | shop_custom):
        base, gem = struct.unpack_from("<ii", custom[cid], 0)
        wk, ak = key("weapon", base), key("ash_of_war", gem) if gem > 0 else None
        if wk and ak and wk not in on_weapon[ak]:
            on_weapon[ak].append(wk)

    # ---------- najeźdźcy ----------
    invader_src = defaultdict(list)
    for x in invaders:
        for rw in x["rewards"]:
            kk = key(rw["cat"], rw["id"])
            if kk and x["id"] not in invader_src[kk]:
                invader_src[kk].append(x["id"])

    out = {}
    for kk in set(enemies) | set(shops) | set(boss_src) | set(events_src) | set(invader_src) | set(gifts) | set(on_weapon):
        e = sorted(({"who": None if n.startswith("#") else n, "model": n[1:] if n.startswith("#") else None,
                     "chance": v["chance"], "count": v["count"], "at": v["at"]}
                    for n, v in enemies.get(kk, {}).items()), key=lambda x: (x["who"] is None, -x["chance"], -x["count"]))
        ev = [{"map_id": m, **(world.to_map(int(m[1:3]), int(m[4:6]), int(m[7:9]), 0, 0, 0) or {})} if m != "common" else {"map_id": m}
              for m in events_src.get(kk, [])][:4]
        out[kk] = {k: v for k, v in (("bosses", boss_src.get(kk)), ("invaders", invader_src.get(kk)), ("gifts", gifts.get(kk)), ("on_weapon", on_weapon.get(kk)), ("shops", shops.get(kk)),
                                     ("enemies", e), ("events", ev)) if v}
    with open(os.path.join(DATA, "item_sources.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA, "shops.json"), "w", encoding="utf-8") as f:
        json.dump(stock, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA, "enemies.json"), "w", encoding="utf-8") as f:
        json.dump(placed, f, separators=(",", ":"))
    print(f"źródła przedmiotów: {len(out)} (kupcy {len(shops)}, z przeciwników {len(enemies)}, za bossów {len(boss_src)}, "
          f"za najeźdźców {len(invader_src)}, podarunki {len(gifts)}, ze zdarzeń {len(events_src)}); miejsca przeciwników z łupem {len(placed)}; "
          f"zakresy sklepów {len(shop_owner)}, sklepy postaci {len(stock)}, z postacią na mapie {sum(1 for t in stock if talk_parts.get(t))}")


if __name__ == "__main__":
    main()
