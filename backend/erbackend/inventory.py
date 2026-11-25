"""Ekwipunek postaci: `inventory_held` (0x9010 B) i `storage_box` (0x6010 B) ze slotu save'a.

Układ (zweryfikowany na 7 postaciach, 2026-11-23):
    u32 liczba_zwykłych, N × {u32 gaitem_handle, u32 ilość, u32 indeks_zdobycia},
    u32 liczba_kluczowych, K × {to samo}, u32 licznik_equip_index, u32 licznik_acquisition_index
    inventory_held: N = 0xA80, K = 0x180;  storage_box: N = 0x780, K = 0x80.
Pusty wpis: handle 0 albo 0xFFFFFFFF.

Typ z górnych 4 bitów handle:
    0x8 broń, 0x9 zbroja, 0xC popiół wojny  -> handle wskazuje wpis GaItem (handle -> item_id),
    0xA talizman, 0xB goods                 -> ID przedmiotu = handle & 0x0FFFFFFF (bez GaItem).
item_id z GaItem: broń 0x0xxxxxxx, zbroja 0x1xxxxxxx, popiół 0x8xxxxxxx (zdejmujemy prefiks typu).
Broń: id = base_id + affinity*100 + upgrade (base_id = id - id % 10000) — jak w EquipParamWeapon.
"""
from __future__ import annotations

import struct

ENTRY = 12
HELD_COMMON, HELD_KEY = 0xA80, 0x180
STORAGE_COMMON, STORAGE_KEY = 0x780, 0x80
HELD_SIZE = 4 + HELD_COMMON * ENTRY + 4 + HELD_KEY * ENTRY + 8          # 0x9010
STORAGE_SIZE = 4 + STORAGE_COMMON * ENTRY + 4 + STORAGE_KEY * ENTRY + 8  # 0x6010

AFFINITIES = ["standard", "heavy", "keen", "quality", "fire", "flame_art", "lightning", "sacred",
              "magic", "cold", "poison", "blood", "occult"]
# Zaślepki, które gra trzyma w ekwipunku zawsze: goła ręka i "brak" hełmu/zbroi/rękawic/nogawic
PLACEHOLDERS = {"weapons": {110000}, "armor": {10000, 10100, 10200, 10300}}
KIND_BY_NIBBLE = {0x8: "weapons", 0x9: "armor", 0xA: "talismans", 0xB: "goods", 0xC: "ashes"}


def read_list(s: bytes, off: int, n_common: int, n_key: int) -> tuple[list, list]:
    """Zwraca (zwykłe, kluczowe) jako listy (handle, ilość, indeks_zdobycia), bez pustych wpisów."""
    def entries(o, n):
        out = []
        for i in range(n):
            h, q, a = struct.unpack_from("<III", s, o + i * ENTRY)
            if h not in (0, 0xFFFFFFFF):
                out.append((h, q, a))
        return out

    common = entries(off + 4, n_common)
    ko = off + 4 + n_common * ENTRY
    key = entries(ko + 4, n_key)
    return common, key


def _resolve(handle: int, gaitems: dict[int, int]) -> tuple[str, int] | None:
    kind = KIND_BY_NIBBLE.get(handle >> 28)
    if kind is None:
        return None
    if kind in ("talismans", "goods"):
        return kind, handle & 0x0FFFFFFF
    item_id = gaitems.get(handle)
    if item_id is None:
        return None
    return kind, item_id & 0x0FFFFFFF


def build(held: tuple[list, list], storage: tuple[list, list], gaitems: dict[int, int],
          weapon_ash: dict[int, int]) -> dict:
    """Składa ekwipunek w kształt API. `count` = przy sobie, `storage` = w skrzyni."""
    groups: dict[str, dict[tuple, dict]] = {k: {} for k in ("weapons", "armor", "talismans", "goods", "ashes")}
    keys: dict[int, dict] = {}
    unknown = 0

    def add(entries, where, is_key):
        nonlocal unknown
        for h, q, _ in entries:
            r = _resolve(h, gaitems)
            if r is None:
                unknown += 1
                continue
            kind, iid = r
            if iid in PLACEHOLDERS.get(kind, ()):
                continue
            if is_key and kind == "goods":
                e = keys.setdefault(iid, {"id": iid, "count": 0, "storage": 0})
                e[where] += q
                continue
            ash = None
            if kind == "weapons":
                ah = weapon_ash.get(h)
                if ah and ah in gaitems:
                    ash = gaitems[ah] & 0x0FFFFFFF
            key = (iid, ash)
            e = groups[kind].get(key)
            if e is None:
                e = {"id": iid, "count": 0, "storage": 0}
                if kind == "weapons":
                    rest = iid % 10000
                    aff = rest // 100
                    e.update({"base_id": iid - rest, "upgrade": rest % 100,
                              "affinity": AFFINITIES[aff] if aff < len(AFFINITIES) else aff, "ash_id": ash})
                groups[kind][key] = e
            e[where] += q

    add(held[0], "count", False)
    add(held[1], "count", True)
    add(storage[0], "storage", False)
    add(storage[1], "storage", True)
    out = {k: sorted(v.values(), key=lambda e: (e["id"], e.get("ash_id") or 0)) for k, v in groups.items()}
    out["key_items"] = sorted(keys.values(), key=lambda e: e["id"])
    out["totals"] = {
        "held_entries": len(held[0]) + len(held[1]), "held_capacity": HELD_COMMON + HELD_KEY,
        "storage_entries": len(storage[0]) + len(storage[1]), "storage_capacity": STORAGE_COMMON + STORAGE_KEY,
        "unresolved": unknown,
    }
    return out
