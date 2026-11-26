"""Dane do liczenia obrażeń broni gracza → assets/data/weapon_calc.json (karta bossa: ile ciosów do zabicia).

Układ pól z publicznych definicji Paramdex (soulsmods/Paramdex ER/Defs), rozmiary wierszy zgodne z grą.
- EquipParamWeapon (wiersz = broń + nasycenie·100, ulepszenie liczone osobno): +0xC8/0xCA/0xCC/0xCE/0x18C u16 obrażenia
  bazowe (fizyczne, magia, ogień, błyskawice, święte), +0x24/0x28/0x2C/0x30/0x19C f32 skalowanie (Siła, Zręczność,
  Inteligencja, Wiara, Tajemność), +0xEC/0x17D/0x17E/0x17F/0x18E u8 krzywa CalcCorrectGraph dla każdego rodzaju obrażeń,
  +0xF2/0xF3/0xF4/0xF5/0x195 u8 wymagania, +0xDA s16 ReinforceParamWeapon, +0x22C s32 AttackElementCorrectParam,
  +0x104 u8 rodzaj ciosu fizycznego (0 cięte, 1 obuchowe, 2 kłute, 3 zwykłe).
- ReinforceParamWeapon (wiersz = typ + poziom): +0x00/0x04/0x08/0x0C/0x58 f32 mnożniki obrażeń, +0x1C/0x20/0x24/0x28/0x60
  f32 mnożniki skalowania.
- AttackElementCorrectParam: 25 bitów od +0x00 (rodzaj obrażeń × atrybut), od +0x04 s16 nadpisane skalowanie (-1 = broni).
Sprawdzone z kalkulatorem ThomasJClark/elden-ring-weapon-calculator (MIT): Długi miecz 120,64, Uchigatana +10 bystra
281,21 przy tych samych atrybutach. Wzór jest w mockup/app.js (weaponAR).
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import params as P  # noqa: E402
from extract_curves import graph  # noqa: E402

BASE = (0xC8, 0xCA, 0xCC, 0xCE, 0x18C)
SCALING = (0x24, 0x28, 0x2C, 0x30, 0x19C)
GRAPH = (0xEC, 0x17D, 0x17E, 0x17F, 0x18E)
REQ = (0xF2, 0xF3, 0xF4, 0xF5, 0x195)
REINFORCE_ATK = (0x00, 0x04, 0x08, 0x0C, 0x58)
REINFORCE_SCALING = (0x1C, 0x20, 0x24, 0x28, 0x60)


def main():
    ps = P.load_params()
    weapons = dict(P.rows(ps["EquipParamWeapon"])[0])
    reinforce = dict(P.rows(ps["ReinforceParamWeapon"])[0])
    element = dict(P.rows(ps["AttackElementCorrectParam"])[0])
    graphs = dict(P.rows(ps["CalcCorrectGraph"])[0])
    items = json.load(open(os.path.join(A.ROOT, "assets", "data", "items.json"), encoding="utf-8"))
    owned_bases = {i["id"] for i in items if i["category"] == "weapon"}
    out = {"weapons": {}, "reinforce": {}, "element": {}, "graphs": {}}
    for rid, r in weapons.items():
        if rid % 100 or rid - rid % 10000 not in owned_bases or not any(struct.unpack_from("<H", r, o)[0] for o in BASE):
            continue
        rtype, elem = struct.unpack_from("<h", r, 0xDA)[0], struct.unpack_from("<i", r, 0x22C)[0]
        out["weapons"][rid] = {"base": [struct.unpack_from("<H", r, o)[0] for o in BASE],
                               "scaling": [round(struct.unpack_from("<f", r, o)[0], 2) for o in SCALING],
                               "graph": [r[o] for o in GRAPH], "req": [r[o] for o in REQ],
                               "reinforce": rtype, "element": elem, "attr": r[0x104]}
        if rtype not in out["reinforce"]:
            out["reinforce"][rtype] = [[round(struct.unpack_from("<f", reinforce[rtype + lv], o)[0], 4) for o in REINFORCE_ATK + REINFORCE_SCALING]
                                       for lv in range(26) if rtype + lv in reinforce]
        if elem not in out["element"]:
            e = element[elem]
            bits = int.from_bytes(e[0:4], "little")
            out["element"][elem] = [[None if not (bits >> (t * 5 + s)) & 1 else struct.unpack_from("<h", e, 4 + 2 * (t * 5 + s))[0]
                                     for s in range(5)] for t in range(5)]     # None = stat does not scale this damage type
        for g in out["weapons"][rid]["graph"]:
            out["graphs"].setdefault(g, graph(graphs[g]))
    with open(os.path.join(A.ROOT, "assets", "data", "weapon_calc.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"obrażenia broni: {len(out['weapons'])} wierszy broni, {len(out['reinforce'])} typów ulepszeń, {len(out['graphs'])} krzywych")


if __name__ == "__main__":
    main()
