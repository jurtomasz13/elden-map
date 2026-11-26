"""MSB (Elden Ring, MSBE), minimalny odczyt: części (wrogowie, obiekty) i zdarzenia skarbów.

Układ ustalony na plikach gry (zgodny z SoulsFormats MSBE):
  lista parametrów: i32 wersja, i32 liczba+1, i64 offset nazwy, i64 offsety wpisów..., ostatni = następna lista
  część:  i64 nazwa, i32 instanceId, i32 typ, i32 indeks, i32 model, i64 sib, f32[3] pozycja, f32[3] obrót,
          f32[3] skala, ..., od +0x50 offsety: [0] unk1, [1] unk2, [2] dane encji (u32 EntityID), [3] dane typu
          wróg (typ 2): dane typu +0x08 ThinkParamID, +0x0C NpcParamID, +0x10 TalkID, +0x18 CharaInitID
                 (CharaInitParam: ekwipunek postaci ludzkich c0000; FaceParam o tym samym ID: wygląd)
  zdarzenie: i64 nazwa, i32 eventId, i32 typ, i32 indeks, i32 ?, i64 dane bazowe, i64 dane typu
          skarb (typ 4): dane typu +0x08 indeks części, +0x10 ItemLotID
  region: i64 nazwa, i32 typ, i32 indeks, u32 kształt, f32[3] pozycja (+0x14), f32[3] obrót w stopniach (+0x20), …,
          i64 dane kształtu (+0x48): circle/sphere r; cylinder r, h; rect szer., głęb.; box szer., głęb., wys.;
          i64 dane bazowe (+0x50): i32 indeks części aktywującej, u32 EntityID (cel teleportów to zwykle punkt)
Otwarty świat ma też pliki większej skali mAA_XX_YY_01 (kafel 2×2) i _02 (4×4): ich pozycje przeliczamy na układ
kafla poziomu 0 o numerach XX·2^L, YY·2^L (przesunięcie środka 128·(2^L − 1)), zob. tile().
"""
import re
import struct

import archive as A

PART_TYPES = {0: "map_piece", 2: "enemy", 4: "player", 5: "collision", 9: "dummy_asset", 10: "dummy_enemy",
              11: "connect_collision", 13: "asset"}
SHAPES = {0: "point", 1: "circle", 2: "sphere", 3: "cylinder", 4: "square", 5: "rect", 6: "box", 7: "composite"}
SHAPE_DIMS = {"circle": 1, "sphere": 1, "cylinder": 2, "rect": 2, "box": 3}


def tile(path: str) -> tuple[int, int, int, int]:
    """(area, x, z, level) in level-0 tiles; a level-L file covers 2^L x 2^L tiles starting at XX*2^L, YY*2^L."""
    area, gx, gz, level = (int(v) for v in re.search(r"m(\d\d)_(\d\d)_(\d\d)_(\d\d)", path).groups())
    return area, gx << level, gz << level, level


def map_id(area: int, gx: int, gz: int) -> str:
    return f"m{area:02d}_{gx:02d}_{gz:02d}_00"


def load(path):
    r = A.find(path)
    return parse(A.undcx(r[1]), 128 * (2 ** tile(path)[3] - 1)) if r else None


def parse(d, shift=0):
    assert d[:4] == b"MSB ", d[:4]

    def wstr(o):
        e = o
        while d[e:e + 2] != b"\0\0":
            e += 2
        return d[o:e].decode("utf-16le", "replace")

    lists, o = {}, 0x10
    while o:
        _ver, cnt, name_off = struct.unpack_from("<iiq", d, o)
        offs = struct.unpack_from(f"<{cnt}q", d, o + 16)
        lists[wstr(name_off)] = offs[:-1]
        o = offs[-1]

    parts = []
    for x in lists.get("PARTS_PARAM_ST", ()):
        name_off, _iid, typ, _idx, model = struct.unpack_from("<qiiii", d, x)
        px, py, pz = struct.unpack_from("<3f", d, x + 0x20)
        pos = (px + shift, py, pz + shift)
        offs = struct.unpack_from("<4q", d, x + 0x50)
        entity = struct.unpack_from("<I", d, x + offs[2])[0] if offs[2] else 0
        npc = talk = chara_init = None
        if typ in (2, 10) and offs[3]:
            npc, talk = struct.unpack_from("<ii", d, x + offs[3] + 0x0C)
            chara_init, = struct.unpack_from("<i", d, x + offs[3] + 0x18)
        parts.append({"name": wstr(x + name_off), "type": PART_TYPES.get(typ, typ), "pos": pos, "entity": entity,
                      "npc": npc, "talk": talk, "chara_init": chara_init})

    treasures = []
    for x in lists.get("EVENT_PARAM_ST", ()):
        name_off, _eid, typ, _idx, _u, _base, tdo = struct.unpack_from("<qiiiiqq", d, x)
        if typ != 4 or not tdo:
            continue
        part_idx, lot = struct.unpack_from("<i", d, x + tdo + 8)[0], struct.unpack_from("<i", d, x + tdo + 0x10)[0]
        part = parts[part_idx] if 0 <= part_idx < len(parts) else None
        treasures.append({"name": wstr(x + name_off), "lot": lot, "part": part["name"] if part else None,
                          "pos": part["pos"] if part else None})
    regions = []
    for x in lists.get("POINT_PARAM_ST", ()):
        name_off, _typ, _idx, shape = struct.unpack_from("<qiiI", d, x)
        shape = SHAPES.get(shape, shape)
        shape_off, base_off = struct.unpack_from("<2q", d, x + 0x48)
        n = SHAPE_DIMS.get(shape)
        px, py, pz = struct.unpack_from("<3f", d, x + 0x14)
        regions.append({"name": wstr(x + name_off), "shape": shape, "pos": (px + shift, py, pz + shift),
                        "rot_y": struct.unpack_from("<f", d, x + 0x24)[0],
                        "dims": struct.unpack_from(f"<{n}f", d, x + shape_off) if n and shape_off else (),
                        "entity": struct.unpack_from("<I", d, x + base_off + 4)[0] if base_off else 0})
    return {"parts": parts, "treasures": treasures, "regions": regions}
