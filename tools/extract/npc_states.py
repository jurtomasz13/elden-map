"""Stany (położenia) NPC z plików gry: przy każdej fladze bloku NPC (+0…+19) mapy, których skrypty zdarzeń ją
sprawdzają, i kwestie, które postać mówi w tym stanie.

    python tools/extract/npc_states.py 220 3660        # TalkID postaci i początek jej bloku flag

Mapy: skrypty zdarzeń /event/<mapa>.emevd.dcx (lista map z extract_world.msb_paths), flaga w argumentach
instrukcji. Zwykle to mapa, na której gra pokazuje postać w tym stanie. Kwestie: talk_quests.state_lines.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import emevd  # noqa: E402
import talk_quests as Q  # noqa: E402
from extract_world import msb_paths  # noqa: E402


def map_ints():
    """Map id -> every integer in the arguments of its event scripts."""
    out = {}
    for p in msb_paths():
        mid = os.path.basename(p).split(".")[0]
        ev = emevd.load(f"/event/{mid}.emevd.dcx")
        if ev:
            out[mid] = {x for e in ev.values() for _, _, a in e["instrs"] for x in emevd.ints(a)}
    return out


def grace_names():
    """Map id -> up to 3 grace names, so a map id is readable."""
    out = {}
    for g in json.load(open(os.path.join(A.ROOT, "assets", "data", "graces.json"), encoding="utf-8")):
        if g.get("map_id") and g.get("name"):
            names = out.setdefault(g["map_id"], [])
            if len(names) < 3 and g["name"] not in names:
                names.append(g["name"])
    return out


def states(talk_id, block, talk, menu):
    ints, names = map_ints(), grace_names()
    lines = Q.state_lines(talk_id, talk, menu, block)
    return {k: {"maps": [f"{m} ({', '.join(names.get(m, []))})" for m in sorted(m for m, s in ints.items() if block + k in s)],
                "lines": lines.get(k, [])}
            for k in range(20)}


if __name__ == "__main__":
    talk, menu = Q.texts()
    for k, v in states(int(sys.argv[1]), int(sys.argv[2]), talk, menu).items():
        if v["maps"] or v["lines"]:
            print(f"+{k}: mapy {v['maps']}")
            for ln in v["lines"]:
                print("     „" + ln + "”")
