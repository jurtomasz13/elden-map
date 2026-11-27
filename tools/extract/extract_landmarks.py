"""Miejsca bez własnego punktu w WorldMapPointParam, dopisywane do assets/data/pois.json (po extract_world.py).

- Boskie Wieże: posąg, przy którym przywraca się Wielki run. Wspólne zdarzenie common_func 90005110 uruchamiane
  z pliku mapy wieży, argumenty: flaga przywrócenia, flaga ze świata, encja posągu, encja obiektu, run nieprzywrócony,
  efekt, przycisk akcji. Flaga przywrócenia to zarazem id przywróconego runu w EquipParamGoods (191 Godrick … 196
  Malenia). Wynik: pole `restore` [{flag, rune}] przy najbliższym punkcie Boskiej Wieży (posąg stoi kilka pikseli
  od napisu wieży).
- Wędrowne Mauzolea: przeciwnicy z modelem c4450 w plikach map (5 chodzi, w tym 1 pod ziemią w m12_03, a 2 stoją
  na Polu Mauzoleów w Liurnii; NpcParam 445000xx chodzi, 44501020 stoi). Gra nie ma ich nazwy w NpcName, nazwa
  z opisów zbroi strażników. Pozycja chodzących to miejsce startu.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import emevd as E  # noqa: E402
import params as P  # noqa: E402
from extract_world import DATA, EntityPlaces, World, event_scripts, maps, scope_tile  # noqa: E402

RESTORE_EVENT = 90005110
MAUSOLEUM_MODEL = "c4450_"
MAUSOLEUM_NAME = "Wędrowne Mauzoleum"     # ProtectorCaption 1740100: „strzegących Wędrownego Mauzoleum”
STANDING_NPC = 44501020                    # the two mausoleums of the Mausoleum Compound do not walk


def main():
    world = World(P.load_params())
    path = os.path.join(DATA, "pois.json")
    pois = [p for p in json.load(open(path, encoding="utf-8")) if "walking" not in p]      # without an earlier run's
    goods = {i["id"]: i["name"] for i in json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8")) if i["category"] == "goods"}

    scripts = event_scripts()
    where = EntityPlaces(world).where
    towers = [p for p in pois if p.get("category") == "tower"]
    for t in towers:
        t.pop("restore", None)
    for scope, args in E.instances(scripts, E.callers(scripts), "common_func", RESTORE_EVENT):
        flag, _world_flag, statue = (int.from_bytes(args[i:i + 4], "little") for i in (0, 4, 8))
        at = where(statue, scope_tile(scope))
        if not at or flag not in goods:
            raise SystemExit(f"extract_landmarks: posąg Wielkiego runu {statue} (flaga {flag}) bez pozycji albo runu")
        tower = min((t for t in towers if t["map"] == at["map"]), key=lambda t: (t["px"] - at["px"]) ** 2 + (t["py"] - at["py"]) ** 2)
        if (tower["px"] - at["px"]) ** 2 + (tower["py"] - at["py"]) ** 2 > 80 ** 2:
            raise SystemExit(f"extract_landmarks: posąg {statue} daleko od najbliższej wieży ({tower['name']})")
        tower.setdefault("restore", []).append({"flag": flag, "rune": goods[flag]})

    found = 0
    for _path, tile, mid, m in maps():
        for p in m["parts"]:
            # parts of the big overworld tiles carry the small tile's name: m60_36_47_00-c4450_9000
            if p["type"] == "enemy" and p["name"].split("-")[-1].startswith(MAUSOLEUM_MODEL):
                pos = world.to_map(*tile, *p["pos"])
                if pos:
                    found += 1
                    pois.append({"id": p["entity"], "name": MAUSOLEUM_NAME, "category": "mausoleum", "map_id": mid, "dlc": False,
                                 "pos": [round(c, 1) for c in p["pos"]], "flag": 0, "icon": None,
                                 "walking": p["npc"] != STANDING_NPC, **pos})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False)
    print(f"extract_landmarks: posągi Wielkich run przy {sum(1 for t in towers if t.get('restore'))} wieżach, "
          f"Wędrowne Mauzolea: {found}")


if __name__ == "__main__":
    main()
