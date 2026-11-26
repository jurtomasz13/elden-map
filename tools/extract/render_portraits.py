"""Portrety 3D z plików gry: bossowie bez ikony i postacie (NPC) → assets/renders/<model>.png albo npc_<CharaInit>.png.

Uruchamiać po extract_world.py (pola "model" i "chara_init" w bosses_all.json i npcs.json). Uzupełnia pole "render".
Postać ludzka (c0000) jest składana z części jak postać gracza (render_character.render_npc: CharaInitParam
+ FaceParam), pozostałe modele eksportuje export_model.export i renderuje render.mjs w kadrze popiersia.
Gra nie ma portretów postaci w teksturach menu (sprawdzone: menu/hi i low, 00_solo, 01_common, 02_title, 05_dummy).
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
DATA = os.path.join(A.ROOT, "assets", "data")
MODELS = os.path.join(A.ROOT, "assets", "cache", "models")
RENDERS = os.path.join(A.ROOT, "assets", "renders")
# rozmowa z obiektem: niewidoczny model (Cienie bliźniaczej służki, ołtarze, Miecz Bernahla) i Stół Kowala / kościoły
NO_MODEL = {"c1000", "c0100"}
# render wychodzi niepełny (sprawdzone na oko 2026-11-26): Kalé ma złe materiały, Pidia i Albus to sam kij,
# Azur i Lusat nie mają szaty, Alexander i Słojątko to ułamki modelu; zostaje znak zamiast złego obrazka
BROKEN = {"c3200", "c3670", "c3710", "c3720", "c4490", "c4491"}


def portrait(o, force):
    """Render name for a boss or character (model or npc_<CharaInit>), rendering it when missing; None = no portrait."""
    model, ci = o.get("model"), o.get("chara_init")
    if not model or model in NO_MODEL or model in BROKEN:
        return None
    name = f"npc_{ci}" if model == "c0000" and ci else None if model == "c0000" else model
    if not name:
        return None
    png = os.path.join(RENDERS, name + ".png")
    if force or not os.path.exists(png):
        if model == "c0000":
            render_character.render_npc(ci, png)
        else:
            n, t = export_model.export(model, MODELS)
            subprocess.run(["node", os.path.join(HERE, "render.mjs"), os.path.join(MODELS, model), png, "256", "205", "bust"], check=True)
            print(f"  {model}: meshe {n}, z teksturą {t}")
    return name if os.path.exists(png) else None


def main(force=False):
    done = {}
    for fn, need in (("bosses_all.json", lambda o: not o.get("icon")), ("npcs.json", lambda o: True)):
        path = os.path.join(DATA, fn)
        rows = json.load(open(path, encoding="utf-8"))
        k = 0
        for o in rows:
            o.pop("render", None)
            if need(o):
                key = (o.get("model"), o.get("chara_init"))
                if key not in done:
                    done[key] = portrait(o, force)
                if done[key]:
                    o["render"] = done[key]
                    k += 1
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"render_portraits: {fn}: {k} z portretem 3D, bez obrazka: {sum(1 for o in rows if need(o) and not o.get('render'))}")


if __name__ == "__main__":
    main("--force" in sys.argv)
