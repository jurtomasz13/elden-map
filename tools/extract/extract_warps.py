"""Teleporty ze skryptów zdarzeń (EMEVD) → assets/data/warps.json: skąd, dokąd i czego wymagają.

Instrukcje przenoszące gracza (układ argumentów z opisu EMEDF Elden Ring, DarkScript3):
  2003[14] WarpPlayer(u8 obszar, u8 blok, u8 region, u8 indeks, u32 encja celu, i32 napis)
  2002[11..13] cutscena z przeniesieniem(i32 cutscena, u32 tryb, u32 encja celu, i32 mapa AABBCCDD, …)
  2004[40/41/42/74] przeniesienie postaci(u32 kto, u8 typ, u32 encja celu, …); bierzemy tylko gracza (10000)
Wiele teleportów to wspólne zdarzenia z argumentami z wywołań (emevd.instances): brama 90005605 (+28 wymagana flaga,
np. włożony Nasycony klucz miecza), powrót do wejścia po bossie 90005645/90005646, wieczne więzienia 90005880/90005881,
windy z medalionem w common 930/936. Źródło: encja z warunku zdarzenia (przycisk akcji 3[24], obszar 3[2]/3[7],
odległość 3[3], śmierć 4[0]); skrzynia-pułapka to warunek 5[2] (otwarty obiekt) przed WarpPlayer.
Encje celu i źródła to części albo regiony (także punktowe) z plików map (msb.py).
Sprawdzone z listą bram na Fextralife: wszystkie 32 są w danych (np. Cztery Dzwonnice -> Farum Azula, Nokron,
Kaplica Oczekiwania; skrzynia w Smoczych Ruinach -> Kryształowe tunele Sellii).
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import emevd as E  # noqa: E402
import params as P  # noqa: E402
from extract_world import DATA, EntityPlaces, World, event_scripts, scope_tile  # noqa: E402

PLAYER = 10000
WARP_PLAYER, CUTSCENE_WARP, SHORT_WARP = (2003, 14), {(2002, 11), (2002, 12), (2002, 13)}, {(2004, 40), (2004, 41), (2004, 42), (2004, 74)}
SOURCE = (((3, 24), 8), ((3, 2), 8), ((3, 7), 4), ((3, 3), 8), ((4, 0), 4))   # condition, byte of the source entity
KIND = {90005605: "waygate", 90005645: "return", 90005646: "return", 90005880: "evergaol", 90005881: "evergaol", 930: "lift", 936: "lift"}
SKIP = {("common", 950)}     # one Limgrave event with 8 branches (flags 951/9000) that the scan would join wrongly


def main():
    world = World(P.load_params())
    scripts = event_scripts()
    calls = E.callers(scripts)
    where = EntityPlaces(world).where

    out, seen = [], set()
    for scope, events in scripts.items():
        for eid, ev in events.items():
            if (scope, eid) in SKIP:
                continue
            for k, (bank, iid, a) in enumerate(ev["instrs"]):
                op = (bank, iid)
                if op != WARP_PLAYER and op not in CUTSCENE_WARP and op not in SHORT_WARP:
                    continue
                for caller, call in E.instances(scripts, calls, scope, eid):
                    args = E.resolve(a, ev["params"], k, call)
                    here = scope_tile(caller)
                    if op == WARP_PLAYER:
                        area, block, region, _i, dent, _popup = struct.unpack_from("<4BIi", args)
                        dtile = (area, block, region)
                    elif op in CUTSCENE_WARP:
                        _cut, _mode, dent, mapid = struct.unpack_from("<iIIi", args)
                        dtile = (mapid // 1000000, mapid // 10000 % 100, mapid // 100 % 100)
                    else:
                        who, _t, dent = struct.unpack_from("<IB3xI", args)
                        if who != PLAYER:
                            continue
                        dtile = here
                    conds = [((b, i), E.resolve(x, ev["params"], j, call)) for j, (b, i, x) in enumerate(ev["instrs"]) if b < 6]
                    src = next((s for key, off in SOURCE for c, x in conds if c == key and len(x) >= off + 4
                                for ent in [struct.unpack_from("<I", x, off)[0]] if ent not in (0, PLAYER, 20000)
                                for s in [where(ent, here)] if s), None)
                    if not src:          # trap chests: the chest is in the actions, not in a condition (first entity found)
                        src = next((s for _c, x in [((b, i), E.resolve(x, ev["params"], j, call)) for j, (b, i, x) in enumerate(ev["instrs"])]
                                    for off in range(0, len(x) - 3, 4) for ent in [struct.unpack_from("<I", x, off)[0]]
                                    if ent > 10000000 and ent != dent for s in [where(ent, here)] if s), None)
                    dst = dent and where(dent, dtile)
                    if not src or not dst:
                        continue
                    kind = ("trap_chest" if op == WARP_PLAYER and any(c == (5, 2) for c, _ in conds)
                            else KIND.get(eid) or ("short" if op in SHORT_WARP else "cutscene" if op in CUTSCENE_WARP else "local"))
                    far = src["map"] != dst["map"] or ((src["px"] - dst["px"]) ** 2 + (src["py"] - dst["py"]) ** 2) ** .5 > 40
                    if not (kind in ("waygate", "trap_chest") or (far and kind not in ("return", "evergaol", "lift"))):
                        continue
                    if kind == "cutscene" and src["map_id"] == dst["map_id"]:     # boss intro moving the camera to the arena
                        continue
                    key = tuple(round(v, -1) for v in (src["px"], src["py"], dst["px"], dst["py"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    items = sorted({struct.unpack_from("<i", x, 4)[0] for c, x in conds if c == (3, 4)})
                    need = struct.unpack_from("<I", call, 28)[0] if eid == 90005605 and len(call) >= 32 else 0
                    out.append({"kind": kind, "src": src, "dst": dst, **({"flag": need} if need else {}),
                                **({"items": items} if items else {}), "script": f"{scope}:{eid}"})
    with open(os.path.join(DATA, "warps.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    kinds = {}
    for w in out:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    print(f"teleporty na mapie: {len(out)} {kinds}")


if __name__ == "__main__":
    main()
