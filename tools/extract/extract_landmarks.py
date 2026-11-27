"""Places without their own WorldMapPointParam row, added to assets/data/pois.json (after extract_world.py).

- Divine Towers: the statue where a Great Rune is restored. Common event common_func 90005110 started from the
  tower's map script, arguments: restored flag, world flag, statue entity, object entity, unrestored rune, effect,
  action button. The restored flag is also the restored rune's EquipParamGoods id (191 Godrick ... 196 Malenia).
  Result: `restore` [{flag, rune}] on the nearest Divine Tower point (the statue stands a few pixels from its label).
- Walking Mausoleums: enemies with model c4450 in the map files (5 walk, one of them underground in m12_03, and 2 stand
  in the Mausoleum Compound in Liurnia; NpcParam 445000xx walks, 44501020 stands). NpcName has no name for them,
  the name comes from the captions of their guards' armour. A walking one's position is where it starts.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import emevd as E  # noqa: E402
import params as P  # noqa: E402
from extract_world import DATA, EntityPlaces, World, event_scripts, maps, part_model, scope_tile  # noqa: E402

RESTORE_EVENT = 90005110
MAUSOLEUM_MODEL = "c4450"
MAUSOLEUM_NAME = "Wędrowne Mauzoleum"     # ProtectorCaption 1740100: "strzegących Wędrownego Mauzoleum"
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
            if p["type"] == "enemy" and part_model(p["name"]) == MAUSOLEUM_MODEL:
                pos = world.to_map(*tile, *p["pos"])
                if not pos:
                    raise SystemExit(f"extract_landmarks: Wędrowne Mauzoleum {p['entity']} ({mid}) bez pozycji na mapie")
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
