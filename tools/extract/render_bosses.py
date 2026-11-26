"""Portrety bossów bez ikony: eksport modelu 3D z plików gry + programowy render do assets/renders/<model>.png.

Uruchamiać po extract_world.py (potrzebne pole "model" w bosses_all.json). Uzupełnia pole "render".
c0000 (postać ludzka składana z części zbroi) pomijamy, bo wymaga osobnego składania modelu.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import export_model  # noqa: E402
import render_character  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(A.ROOT, "assets", "data", "bosses_all.json")
MODELS = os.path.join(A.ROOT, "assets", "cache", "models")
RENDERS = os.path.join(A.ROOT, "assets", "renders")


def main(force=False):
    bosses = json.load(open(DATA, encoding="utf-8"))
    todo = sorted({b["model"] for b in bosses if not b.get("icon") and b.get("model") and b["model"] != "c0000"})
    for m in todo:
        png = os.path.join(RENDERS, m + ".png")
        if os.path.exists(png) and not force:
            continue
        n, t = export_model.export(m, MODELS)
        subprocess.run(["node", os.path.join(HERE, "render.mjs"), os.path.join(MODELS, m), png, "256", "205", "bust"], check=True)
        print(f"  {m}: meshe {n}, z teksturą {t}")
    # postacie ludzkie (c0000): składane z części jak postać gracza (render_character.render_npc)
    for b in bosses:
        ci = b.get("chara_init")
        if not b.get("icon") and b.get("model") == "c0000" and ci:
            png = os.path.join(RENDERS, f"npc_{ci}.png")
            if force or not os.path.exists(png):
                render_character.render_npc(ci, png)
    k = 0
    for b in bosses:
        ci = b.get("chara_init")
        if not b.get("icon") and b.get("model") == "c0000" and ci and os.path.exists(os.path.join(RENDERS, f"npc_{ci}.png")):
            b["render"] = f"npc_{ci}"
            k += 1
            continue
        if not b.get("icon") and b.get("model") and os.path.exists(os.path.join(RENDERS, b["model"] + ".png")):
            b["render"] = b["model"]
            k += 1
    json.dump(bosses, open(DATA, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"render_bosses: {k} bossów z portretem 3D; bez obrazka: "
          + ", ".join(b["name"] for b in bosses if not b.get("icon") and not b.get("render")))


if __name__ == "__main__":
    main("--force" in sys.argv)
