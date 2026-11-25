"""Krzywe przyrostu statystyk z regulation.bin (CalcCorrectGraph) → assets/data/stat_curves.json.

Wiersz (0x50 B): +0x00 5×f32 progi atrybutu (stageMaxVal), +0x14 5×f32 wartości na progach (stageMaxGrowVal),
+0x28 5×f32 wykładniki krzywizny między progami (adjPt_maxGrowVal). Wartość dla x w przedziale [s_i, s_i+1]:
  r = (x - s_i) / (s_i+1 - s_i);  r = r**e (e > 0)  albo  1 - (1 - r)**(-e) (e < 0);  v = g_i + (g_i+1 - g_i) * r

Używane wiersze (ustalone po wartościach, docs/08-assets.md):
  100 HP ← Witalność, 101 PF ← Umysł, 104 wytrzymałość ← Wytrwałość, 220 udźwig ← Wytrwałość,
  0 skalowanie fizyczne (Siła/Zręczność), 4 skalowanie żywiołów (Inteligencja/Wiara), 6 statusy (Tajemność).
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import params as P  # noqa: E402

USE = {100: "hp", 101: "fp", 104: "stamina", 220: "equip_load", 0: "phys_scaling", 4: "elem_scaling", 6: "status_scaling"}


def main():
    rows = dict(P.rows(P.load_params()["CalcCorrectGraph"])[0])
    out = {}
    for rid, key in USE.items():
        r = rows[rid]
        out[key] = {"graph": rid, "stages": [round(v, 3) for v in struct.unpack_from("<5f", r, 0)],
                    "values": [round(v, 3) for v in struct.unpack_from("<5f", r, 0x14)],
                    "exp": [round(v, 3) for v in struct.unpack_from("<5f", r, 0x28)]}
    path = os.path.join(A.ROOT, "assets", "data", "stat_curves.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("krzywe statystyk:", ", ".join(f"{k} {v['stages'][1:4]}" for k, v in out.items()))


if __name__ == "__main__":
    main()
