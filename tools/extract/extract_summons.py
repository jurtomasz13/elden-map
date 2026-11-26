"""Znaki przywołania postaci (NPC) ze skryptów zdarzeń → assets/data/summons.json: kto, gdzie stoi znak.

2003[25] PlaceNPCSummonSign(typ znaku, encja postaci, region znaku, flaga przywołania, flaga odejścia, …), zwykle we
wspólnych zdarzeniach z argumentami z wywołań (emevd.instances). Typ 20 to biały znak pomocnika (opis EMEDF); innych
typów opis nie nazywa, więc strona pokazuje je jako znak bez rodzaju. Imię z NpcParam +0x0C części o encji postaci,
pozycja z regionu znaku (zapasowo z części postaci). Sprawdzone: Nepheli i Rogier przy Godricku, Melina przy Morgocie.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import emevd as E  # noqa: E402
import params as P  # noqa: E402
from extract_world import DATA, SKIP_INVADERS_EN, EntityPlaces, World, event_scripts, scope_tile  # noqa: E402

PLACE_SIGN = (2003, 25)


def main():
    ps = P.load_params()
    npc_rows = dict(P.rows(ps["NpcParam"])[0])
    t = P.load_texts("polpl")
    names = {**t.get("NpcName", {}), **t.get("NpcName_dlc01", {}), **t.get("NpcName_dlc02", {})}
    te = P.load_texts("engus")
    names_en = {**te.get("NpcName", {}), **te.get("NpcName_dlc01", {}), **te.get("NpcName_dlc02", {})}
    # duel opponents (Great Jar knights, Eleonora, Vyke…) are already invaders with a defeat state: one marker each
    invaders = {x["id"] for x in json.load(open(os.path.join(DATA, "invaders.json"), encoding="utf-8"))}
    places = EntityPlaces(World(ps))
    scripts = event_scripts()
    calls = E.callers(scripts)
    out, seen = [], set()
    for scope, events in scripts.items():
        for eid, ev in events.items():
            for k, (bank, iid, a) in enumerate(ev["instrs"]):
                if (bank, iid) != PLACE_SIGN:
                    continue
                for caller, call in E.instances(scripts, calls, scope, eid):
                    sign_type, entity, area = E.ints(E.resolve(a, ev["params"], k, call))[:3]
                    tile = scope_tile(caller)
                    npc = places.npc(entity)
                    name_id = struct.unpack_from("<i", npc_rows[npc], 0x0C)[0] if npc in npc_rows else None
                    name = names.get(name_id)
                    if entity in invaders or names_en.get(name_id) in SKIP_INVADERS_EN:
                        continue
                    pos = places.where(area, tile) or places.where(entity, tile)
                    if not name or not pos or (name, round(pos["px"]), round(pos["py"])) in seen:
                        continue
                    seen.add((name, round(pos["px"]), round(pos["py"])))
                    out.append({"name": name.strip(), "helper": sign_type == 20, **pos})
    with open(os.path.join(DATA, "summons.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    print(f"znaki przywołania postaci: {len(out)} (pomocnicy {sum(1 for s in out if s['helper'])})")


if __name__ == "__main__":
    main()
