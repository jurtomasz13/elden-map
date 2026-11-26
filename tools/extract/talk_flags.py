"""Badanie skryptów rozmów NPC (talk ESD): które flagi czyta i ustawia skrypt danej postaci.

    python tools/extract/talk_flags.py 223 3940        # TalkID (z NpcName 1<ID>00) i początek bloku flag NPC

Skrypty: /script/talk/<mapa>.talkesdbnd.dcx → t<ID><wariant>.esd. Literał int w wyrażeniu ESD = 0x82 + i32.
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import formats as F  # noqa: E402

DATA = os.path.join(A.ROOT, "assets", "data")


def talk_archives():
    mids = {"m60_00_00_00", "m61_00_00_00", "m00_00_00_00"}
    for fn in ("graces", "item_locations", "npcs", "bosses_all"):
        p = os.path.join(DATA, fn + ".json")
        if os.path.exists(p):
            mids |= {o["map_id"][:12] for o in json.load(open(p, encoding="utf-8")) if o.get("map_id")}
    return sorted(mids)


_ALL = None


def all_scripts():
    """Wszystkie skrypty rozmów z archiwów map (wczytane raz): {"mapa/tNNN.esd": bajty}."""
    global _ALL
    if _ALL is None:
        _ALL = {}
        for mid in talk_archives():
            r = A.find(f"/script/talk/{mid}.talkesdbnd.dcx")
            if not r:
                continue
            for _, n, d in F.bnd4(r[1]):
                _ALL[f"{mid}/{os.path.basename(n.replace(chr(92), '/'))}"] = d
    return _ALL


def scripts(talk_id):
    pre = f"t{talk_id}"
    return {k: d for k, d in all_scripts().items()
            if k.split("/")[-1].startswith(pre) and len(k.split("/")[-1]) == len(pre) + 6 + 4}


def literals(d):
    return [struct.unpack_from("<i", d, m.start() + 1)[0] for m in re.finditer(rb"\x82", d) if m.start() + 5 <= len(d)]


if __name__ == "__main__":
    tid, block = int(sys.argv[1]), int(sys.argv[2])
    for name, d in scripts(tid).items():
        lits = literals(d)
        blk = sorted({x for x in lits if block <= x < block + 20})
        other = sorted({x for x in lits if 1000 <= x < 1_100_000_000 and not block <= x < block + 20 and x not in range(10_000_000, 99_999_999)})
        msgs = sorted({x for x in lits if 10_000_000 <= x < 99_999_999})
        print(name, f"{len(d)} B | blok: {blk} | inne flagi: {other[:30]} | wiadomości: {len(msgs)} ({msgs[:3]}…)")
