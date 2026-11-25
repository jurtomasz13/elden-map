"""Elden Ring save probe — odczyt (tylko read-only) pliku ER0000.sl2 / ER0000.co2.

Użycie:
    python er_save_probe.py <ścieżka do .sl2/.co2> [ct_event_flags.csv]

Wypisuje aktywne postacie, ich poziom, mapę ostatniego zapisu, liczbę odblokowanych
regionów i (opcjonalnie) stan flag z tabeli CE. Format opisany w docs/03-format-save.md.
Skrypt NIE modyfikuje pliku. Najlepiej podawać mu kopię save'a.
"""
import csv
import hashlib
import struct
import sys

SLOT_COUNT = 10
SLOT_SIZE = 0x280010            # 0x10 MD5 + 0x280000 danych
FIRST_SLOT_OFFSET = 0x300
PROFILE_ENTRY = 10              # USER_DATA010
PROFILE_ACTIVE = 0x1954         # bool[10]
PROFILE_SUMMARY = 0x195E        # 10 x 0x24C
PROFILE_SUMMARY_SIZE = 0x24C
FLAGS_SIZE = 0x1BF99F
FLAGS_AFTER_REGIONS = 0x1CA5E   # odległość od końca listy regionów do początku flag


def load_bst(path):
    """eventflag_bst.txt (ClayAmore/ER-Save-Lib): linie 'blok,pozycja'."""
    with open(path, encoding="utf-8") as f:
        return {int(b): int(p) for b, p in (ln.strip().split(",") for ln in f if ln.strip())}


def flag_location(bst, flag_id):
    """ID flagi -> (bajt w bloku flag, numer bitu liczony od najmłodszego)."""
    block, index = divmod(flag_id, 1000)
    if block not in bst:
        return None
    return bst[block] * 125 + index // 8, 7 - index % 8


def is_flag_set(flags, bst, flag_id):
    loc = flag_location(bst, flag_id)
    return loc is not None and bool((flags[loc[0]] >> loc[1]) & 1)


def read_bnd4(d):
    assert d[:4] == b"BND4", "to nie jest kontener BND4"
    count = struct.unpack_from("<I", d, 0x0C)[0]
    entry_size = struct.unpack_from("<Q", d, 0x20)[0]
    entries = []
    for i in range(count):
        o = 0x40 + i * entry_size
        size = struct.unpack_from("<Q", d, o + 0x08)[0]
        off, name_off = struct.unpack_from("<II", d, o + 0x10)
        e = name_off
        while d[e:e + 2] != b"\0\0":
            e += 2
        name = d[name_off:e].decode("utf-16le")
        blob = d[off:off + size]
        md5_ok = hashlib.md5(blob[16:]).digest() == blob[:16]
        entries.append((name, off, size, md5_ok))
    return entries


def gaitem_end(s):
    ver = struct.unpack_from("<I", s, 0)[0]
    o = 0x20
    for _ in range(0x1400 if ver > 81 else 0x13FE):
        h = struct.unpack_from("<I", s, o)[0]
        o += 8
        kind = h & 0xF0000000
        if h and kind == 0x80000000:      # broń
            o += 13
        elif h and kind == 0x90000000:    # zbroja
            o += 8
    return o


# Pola o stałym rozmiarze między GaItem map a listą pocisków / listą regionów
# (kolejność wg dokumentacji er-save-manager, zweryfikowana na 7 postaciach).
BEFORE_PROJECTILES = (0x1B0 + 0xD0 + 0x58 + 0x1C + 0x58 + 0x58   # player_game_data, sp_effects, equip…
                      + 0x9010 + 0x74 + 0x8C + 0x18)             # inventory_held, spells, items, gestures
AFTER_PROJECTILES = 0x9C + 0xC + 0x12F + 0x6010 + 0x100          # armaments, physics, face, storage, gestures


def find_regions(s):
    """Lista odblokowanych regionów: u32 count + count * u32 (parsowanie pól po kolei)."""
    o = gaitem_end(s) + BEFORE_PROJECTILES
    projectiles = struct.unpack_from("<I", s, o)[0]          # acquired_projectiles: u32 count + count * 8
    o += 4 + projectiles * 8 + AFTER_PROJECTILES
    n = struct.unpack_from("<I", s, o)[0]
    if n > 5000:
        raise ValueError(f"podejrzana liczba regionów {n} (zmiana formatu?)")
    return o, list(struct.unpack_from(f"<{n}I", s, o + 4))


def slot_flags(s):
    reg_off, regs = find_regions(s)
    start = reg_off + 4 + 4 * len(regs) + FLAGS_AFTER_REGIONS
    flags = s[start:start + FLAGS_SIZE]
    # sanity check: po fladze terminator 0x00, potem u32 rozmiar małej listy
    term = s[start + FLAGS_SIZE]
    return flags, start, regs, term


def main(path, ct_csv=None):
    d = open(path, "rb").read()
    entries = read_bnd4(d)
    for name, off, size, ok in entries:
        print(f"{name:14} off=0x{off:08X} size=0x{size:06X} md5={'OK' if ok else 'ZŁE'}")
    prof_off = entries[PROFILE_ENTRY][1] + 16
    u = d[prof_off:]
    steam_id = struct.unpack_from("<Q", u, 4)[0]
    print("SteamID:", steam_id)
    active = list(u[PROFILE_ACTIVE:PROFILE_ACTIVE + SLOT_COUNT])

    ct = list(csv.DictReader(open(ct_csv, encoding="utf-8"))) if ct_csv else []

    for i in range(SLOT_COUNT):
        if not active[i]:
            continue
        b = PROFILE_SUMMARY + i * PROFILE_SUMMARY_SIZE
        name = u[b:b + 0x22].decode("utf-16le").split("\0")[0]
        level = struct.unpack_from("<I", u, b + 0x22)[0]
        s = d[FIRST_SLOT_OFFSET + i * SLOT_SIZE + 16:FIRST_SLOT_OFFSET + (i + 1) * SLOT_SIZE]
        ver = struct.unpack_from("<I", s, 0)[0]
        m = s[4:8]
        map_id = f"m{m[3]:02d}_{m[2]:02d}_{m[1]:02d}_{m[0]:02d}"
        flags, start, regs, term = slot_flags(s)
        secs = struct.unpack_from("<I", u, b + 0x26)[0]
        # preambuła tuż przed flagami (0x1A bajtów): deaths u32, chr_type i32, online u8,
        # chr_type_online u32, last_rested_grace u32, not_alone u8, countdown u32, random_lot u32
        deaths = struct.unpack_from("<I", s, start - 0x1A)[0]
        grace = struct.unpack_from("<I", s, start - 0x1A + 13)[0]
        # po flagach: terminator + 5 bloków (i32 size + dane), potem PlayerCoordinates
        o = start + FLAGS_SIZE + 1
        for _ in range(5):
            o += 4 + struct.unpack_from("<i", s, o)[0]
        x, y, z = struct.unpack_from("<3f", s, o)
        pm = s[o + 12:o + 16]
        pos_map = f"m{pm[3]:02d}_{pm[2]:02d}_{pm[1]:02d}_{pm[0]:02d}"
        print(f"\n[{i}] {name}  lvl {level}  ver {ver}  mapa {map_id}  regiony {len(regs)}"
              f"  flagi @0x{start:X} (terminator {term:#04x})")
        print(f"    czas gry {secs / 3600:.1f} h  śmierci {deaths}  ostatnia łaska {grace}"
              f"  pozycja ({x:.1f}, {y:.1f}, {z:.1f}) na {pos_map} (współrzędne lokalne kafla)")
        if ct:
            groups = {}
            for r in ct:
                g = (r["group"].replace('"', "").replace("[ Enable ]/", "")
                     .replace("[ World / Npc Flags ]/", "").split("/")[0])
                bit = (flags[int(r["byte_offset"], 16)] >> int(r["bit"])) & 1
                got, tot = groups.get(g, (0, 0))
                groups[g] = (got + bit, tot + 1)
            for g, (got, tot) in groups.items():
                print(f"    {g:45} {got}/{tot}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
