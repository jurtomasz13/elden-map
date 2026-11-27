"""Parser pliku save Elden Ring (`ER0000.sl2` / `ER0000.co2`) — TYLKO ODCZYT.

Format opisany w docs/03-format-save.md (zweryfikowany na save'ach użytkownika).
Plik czytamy w całości do pamięci (jeden `read()`), sprawdzamy MD5 wszystkich wpisów BND4,
a gdy się nie zgadzają (gra właśnie zapisuje) — ponawiamy. Nigdy nie piszemy do pliku.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import struct
import time
from dataclasses import dataclass, field

from . import equipment, inventory

SLOT_COUNT = 10
FIRST_SLOT_OFFSET = 0x300
SLOT_SIZE = 0x280010            # 0x10 MD5 + 0x280000 danych
PROFILE_ENTRY = 10              # USER_DATA010
PROFILE_STEAM_ID = 0x04
PROFILE_LAST_SLOT = 0x1334      # u32: slot ostatnio wczytany ("Kontynuuj") — patrz docs/07
PROFILE_ACTIVE = 0x1954         # bool[10]
PROFILE_SUMMARY = 0x195E        # 10 × 0x24C
PROFILE_SUMMARY_SIZE = 0x24C
FLAGS_SIZE = 0x1BF99F
FLAGS_AFTER_REGIONS = 0x1CA5E   # koniec listy regionów -> początek bloku flag
PREAMBLE = 0x1A                 # preambuła przed flagami (śmierci, ostatnia łaska, ...)
COORDS_SIZE = 0x3D
HORSE_SIZE = 0x28                # RideGameData za listą regionów
BLOODSTAIN_SIZE = 0x44

# Pola o stałym rozmiarze między GaItem map a listą pocisków / listą regionów
# (kolejność wg dokumentacji er-save-manager, zweryfikowana na 7 postaciach).
BEFORE_PROJECTILES = (0x1B0 + 0xD0 + 0x58 + 0x1C + 0x58 + 0x58
                      + 0x9010 + 0x74 + 0x8C + 0x18)
AFTER_PROJECTILES = 0x9C + 0xC + 0x12F + 0x6010 + 0x100
# inventory_held (0x9010): za player_game_data, sp_effects, equip_index, arm_style, item_id, gaitem_handle
INVENTORY_HELD = 0x1B0 + 0xD0 + 0x58 + 0x1C + 0x58 + 0x58                 # = 0x3A4 od końca GaItem
STORAGE_AFTER_PROJECTILES = 0x9C + 0xC + 0x12F                             # storage_box (0x6010)

FILE_KINDS = {"sl2": "ER0000.sl2", "co2": "ER0000.co2"}


class SaveError(Exception):
    """Plik nie jest poprawnym save'em (lub jest w trakcie zapisu)."""


class SaveBusy(SaveError):
    """MD5 się nie zgadza / plik ucięty — najpewniej gra właśnie zapisuje."""


def map_id_str(b: bytes) -> str:
    """4 bajty [DD, CC, BB, AA] -> 'mAA_BB_CC_DD'."""
    return f"m{b[3]:02d}_{b[2]:02d}_{b[1]:02d}_{b[0]:02d}"


@dataclass
class Entry:
    name: str
    offset: int
    size: int
    md5: bytes          # 16 B zapisane na początku wpisu
    md5_ok: bool


def read_bnd4(d: bytes) -> list[Entry]:
    if d[:4] != b"BND4":
        raise SaveError("to nie jest kontener BND4")
    count = struct.unpack_from("<I", d, 0x0C)[0]
    entry_size = struct.unpack_from("<Q", d, 0x20)[0]
    if not 0 < count <= 64 or entry_size < 0x18:
        raise SaveError(f"dziwny nagłówek BND4 (count={count})")
    entries = []
    for i in range(count):
        o = 0x40 + i * entry_size
        size = struct.unpack_from("<Q", d, o + 0x08)[0]
        off, name_off = struct.unpack_from("<II", d, o + 0x10)
        e = name_off
        while d[e:e + 2] != b"\0\0" and e < len(d):
            e += 2
        name = d[name_off:e].decode("utf-16le", "replace")
        if off + size > len(d):
            raise SaveBusy(f"wpis {name} wychodzi poza plik (plik ucięty?)")
        blob = d[off:off + size]
        entries.append(Entry(name, off, size, bytes(blob[:16]), hashlib.md5(blob[16:]).digest() == blob[:16]))
    return entries


def _gaitem_scan(s: bytes) -> tuple[int, dict[int, int], dict[int, int]]:
    """GaItem map: zwraca (koniec, handle -> item_id, handle broni -> handle jej popiołu wojny)."""
    ver = struct.unpack_from("<I", s, 0)[0]
    o = 0x20
    items: dict[int, int] = {}
    weapon_ash: dict[int, int] = {}
    for _ in range(0x1400 if ver > 81 else 0x13FE):
        h, item_id = struct.unpack_from("<II", s, o)
        o += 8
        kind = h & 0xF0000000
        if h and kind == 0x80000000:      # broń: i32 ?, i32 ?, u32 handle popiołu, u8 ?
            ash = struct.unpack_from("<I", s, o + 8)[0]
            if ash not in (0, 0xFFFFFFFF):
                weapon_ash[h] = ash
            o += 13
        elif h and kind == 0x90000000:    # zbroja
            o += 8
        if h and h != 0xFFFFFFFF:
            items[h] = item_id
    return o, items, weapon_ash


def _gaitem_end(s: bytes) -> int:
    return _gaitem_scan(s)[0]


@dataclass
class Slot:
    """Sparsowany slot postaci (dane po 16 B MD5)."""
    index: int
    md5: str
    version: int
    map_id: str
    regions: list[int]
    flags_offset: int
    flags: bytes = field(repr=False)
    deaths: int
    last_grace: int
    position: dict
    bloodstain: dict | None = None
    inventory: dict | None = field(default=None, repr=False)
    equipment: dict | None = field(default=None, repr=False)
    stats: dict | None = None

    @classmethod
    def parse(cls, index: int, s: bytes, md5: str) -> "Slot":
        try:
            version = struct.unpack_from("<I", s, 0)[0]
            map_id = map_id_str(s[4:8])
            ga_end, gaitems, weapon_ash = _gaitem_scan(s)
            o = ga_end + BEFORE_PROJECTILES
            projectiles = struct.unpack_from("<I", s, o)[0]
            if projectiles > 10000:
                raise SaveError(f"slot {index}: podejrzana liczba pocisków {projectiles}")
            o += 4 + projectiles * 8
            equip = equipment.parse(s, ga_end, o, gaitems, weapon_ash)
            stats = parse_stats(s, ga_end)
            storage_off = o + STORAGE_AFTER_PROJECTILES
            o += AFTER_PROJECTILES
            held = inventory.read_list(s, ga_end + INVENTORY_HELD, inventory.HELD_COMMON, inventory.HELD_KEY)
            stored = inventory.read_list(s, storage_off, inventory.STORAGE_COMMON, inventory.STORAGE_KEY)
            inv = inventory.build(held, stored, gaitems, weapon_ash)
            n = struct.unpack_from("<I", s, o)[0]
            if n > 5000:
                raise SaveError(f"slot {index}: podejrzana liczba regionów {n} (zmiana formatu?)")
            regions = list(struct.unpack_from(f"<{n}I", s, o + 4))
            bloodstain = parse_bloodstain(s, o + 4 + 4 * n + HORSE_SIZE + 1)
            start = o + 4 + 4 * n + FLAGS_AFTER_REGIONS
            flags = bytes(s[start:start + FLAGS_SIZE])
            if len(flags) != FLAGS_SIZE:
                raise SaveError(f"slot {index}: blok flag poza slotem")
            # preambuła: deaths u32, chr_type i32, online u8, chr_type_online u32,
            # last_rested_grace u32, not_alone u8, countdown u32, random_lot u32
            p = start - PREAMBLE
            deaths = struct.unpack_from("<I", s, p)[0]
            last_grace = struct.unpack_from("<I", s, p + 13)[0]
            # po flagach: terminator 0x00 + 5 bloków (i32 size + dane), potem PlayerCoordinates
            c = start + FLAGS_SIZE
            if s[c] != 0:
                raise SaveError(f"slot {index}: brak terminatora za blokiem flag")
            c += 1
            for _ in range(5):
                size = struct.unpack_from("<i", s, c)[0]
                if not 0 <= size < len(s):
                    raise SaveError(f"slot {index}: zły rozmiar listy za flagami ({size})")
                c += 4 + size
            x, y, z = struct.unpack_from("<3f", s, c)
            pos_map = map_id_str(s[c + 12:c + 16])
        except struct.error as e:
            raise SaveError(f"slot {index}: {e}") from e
        return cls(index=index, md5=md5, version=version, map_id=map_id, regions=regions,
                   flags_offset=start, flags=flags, deaths=deaths, last_grace=last_grace,
                   position=position_dict(pos_map, x, y, z), bloodstain=bloodstain, inventory=inv,
                   equipment=equip, stats=stats)


ATTRS = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")


def parse_stats(s: bytes, ga_end: int) -> dict:
    """PlayerGameData zaraz za mapą GaItem: +0x08 HP (bieżące, max, bazowe max), +0x14 PF, +0x24 wytrzymałość,
    +0x34 8 × u32 atrybuty (Witalność…Tajemność), +0x60 poziom. Suma atrybutów − 79 = poziom (sprawdzone na 7 postaciach).
    +0xF4 u8 poziom błogosławieństwa Ostrodrzewa (0–20), +0xF5 u8 błogosławieństwa prochów czcigodnych (0–10), układ wg
    elden-ring-save-manager (docs „save file structure”), sprawdzone na 7 postaciach (bez DLC 0, z DLC 9/5 i 19/9).
    +0xF9/+0xFA u8 butelki szkarłatne / modre (suma 4 na starcie, 14 z kompletem złotych nasion), +0xBD u8 kamienie
    pamięci (0–8), +0xBE u8 dodatkowe sloty talizmanów (0–3); sprawdzone na tych samych 7 postaciach."""
    hp = struct.unpack_from("<3I", s, ga_end + 0x08)
    fp = struct.unpack_from("<3I", s, ga_end + 0x14)
    sp = struct.unpack_from("<3I", s, ga_end + 0x24)
    attrs = dict(zip(ATTRS, struct.unpack_from("<8I", s, ga_end + 0x34)))
    level = struct.unpack_from("<I", s, ga_end + 0x60)[0]
    ok = sum(attrs.values()) - 79 == level and all(0 < v <= 99 for v in attrs.values())
    return {"attributes": attrs if ok else None, "level": level,
            "hp": {"current": hp[0], "max": hp[1], "base_max": hp[2]},
            "fp": {"current": fp[0], "max": fp[1], "base_max": fp[2]},
            "stamina": {"current": sp[0], "max": sp[1], "base_max": sp[2]},
            "scadutree_blessing": s[ga_end + 0xF4], "revered_spirit_ash_blessing": s[ga_end + 0xF5],
            "flasks": {"crimson": s[ga_end + 0xF9], "cerulean": s[ga_end + 0xFA]},
            "memory_stones": s[ga_end + 0xBD], "talisman_slots_added": s[ga_end + 0xBE]}


def parse_bloodstain(s: bytes, o: int) -> dict | None:
    """Plama krwi (0x44 B za koniem 0x28 B i 1 bajtem 'has_bloodstain', który na save'ach zawsze = 1).

    Układ ustalony na 7 postaciach (2026-11-23): +0x00 float[3] XYZ (lokalne, jak PlayerCoordinates),
    +0x0C float[4] obrót, +0x30 i32 ?, +0x34 i32 runy (-1 = brak run / odzyskane),
    +0x38 MapID [DD,CC,BB,AA] (0xFFFFFFFF = brak plamy, np. postać bez śmierci).
    """
    raw = s[o:o + BLOODSTAIN_SIZE]
    if len(raw) < BLOODSTAIN_SIZE or raw[0x38:0x3C] == b"\xff\xff\xff\xff":
        return None
    x, y, z = struct.unpack_from("<3f", raw, 0)
    runes = struct.unpack_from("<i", raw, 0x34)[0]
    out = position_dict(map_id_str(raw[0x38:0x3C]), x, y, z)
    out["runes"] = runes if runes >= 0 else None
    return out


def position_dict(map_id: str, x: float, y: float, z: float) -> dict:
    pos = {"map_id": map_id, "x": round(x, 3), "y": round(y, 3), "z": round(z, 3), "global": None}
    parts = map_id[1:].split("_")
    # Świat otwarty (m60 Ziemie Pomiędzy, m61 DLC): pozycja lokalna względem kafla mAA_XX_ZZ_00.
    # Wzór: globalna = kafel*256 + 128 + lokalna — ten sam, którym tools/extract liczy px/py mapy strony
    # (zgodność 0 rozbieżności na 225 łaskach i 3379 skarbach — tests/test_worldmap.py), więc verified = True.
    if len(parts) == 4 and parts[0] in ("60", "61") and parts[3] == "00":
        tx, tz = int(parts[1]), int(parts[2])
        pos["global"] = {"x": round(tx * 256 + 128 + x, 3), "z": round(tz * 256 + 128 + z, 3),
                         "verified": True}
    return pos


@dataclass
class Character:
    slot: int
    name: str
    level: int
    playtime_s: int
    runes_memory: int
    map_id: str
    place_name_id: int
    md5: str
    profile: dict = field(default_factory=dict)      # body_type, archetype, starting_gift


class SaveFile:
    """Cały plik save wczytany do pamięci. Sloty parsowane leniwie."""

    def __init__(self, path: str, data: bytes, mtime_ns: int):
        self.path = path
        self.data = data
        self.mtime_ns = mtime_ns
        self.entries = read_bnd4(data)
        bad = [e.name for e in self.entries if not e.md5_ok]
        if bad:
            raise SaveBusy(f"niezgodne MD5: {', '.join(bad)}")
        if len(self.entries) <= PROFILE_ENTRY:
            raise SaveError("brak wpisu profilu USER_DATA010")
        prof = self.entries[PROFILE_ENTRY]
        self.profile = data[prof.offset + 16:prof.offset + prof.size]
        self.steam_id = struct.unpack_from("<Q", self.profile, PROFILE_STEAM_ID)[0]
        last = struct.unpack_from("<I", self.profile, PROFILE_LAST_SLOT)[0]
        self.active_slots = [i for i in range(SLOT_COUNT) if self.profile[PROFILE_ACTIVE + i]]
        self.last_slot = last if last in self.active_slots else (self.active_slots[0] if self.active_slots else None)
        self._slots: dict[int, Slot] = {}

    # --- wczytywanie -------------------------------------------------------------------------
    @classmethod
    def read(cls, path: str, retries: int = 15, delay: float = 0.2) -> "SaveFile":
        """Czyta plik (kopia w pamięci) i weryfikuje MD5; ponawia, gdy plik jest w trakcie zapisu."""
        last_err: Exception | None = None
        for attempt in range(max(1, retries)):
            try:
                st1 = os.stat(path)
                with open(path, "rb") as f:
                    data = f.read()
                st2 = os.stat(path)
                if st1.st_mtime_ns != st2.st_mtime_ns or len(data) != st2.st_size:
                    raise SaveBusy("plik zmienił się w trakcie odczytu")
                return cls(path, data, st2.st_mtime_ns)
            except (SaveBusy, PermissionError, OSError) as e:
                if isinstance(e, FileNotFoundError) and attempt >= 2:
                    raise
                last_err = e
                time.sleep(delay)
        raise SaveBusy(f"nie udało się odczytać spójnego pliku: {last_err}")

    # --- dane --------------------------------------------------------------------------------
    @property
    def kind(self) -> str:
        ext = os.path.splitext(self.path)[1].lower().lstrip(".")
        return ext if ext in FILE_KINDS else ext or "?"

    @property
    def written_at(self) -> str:
        return dt.datetime.fromtimestamp(self.mtime_ns / 1e9).astimezone().isoformat(timespec="milliseconds")

    def slot_md5(self, i: int) -> str:
        return self.entries[i].md5.hex()

    def character(self, i: int) -> Character:
        b = PROFILE_SUMMARY + i * PROFILE_SUMMARY_SIZE
        u = self.profile
        name = u[b:b + 0x22].decode("utf-16le", "replace").split("\0")[0]
        level, secs, runes, = struct.unpack_from("<III", u, b + 0x22)
        return Character(slot=i, name=name, level=level, playtime_s=secs, runes_memory=runes,
                         map_id=map_id_str(u[b + 0x2E:b + 0x32]),
                         place_name_id=struct.unpack_from("<I", u, b + 0x32)[0], md5=self.slot_md5(i),
                         profile=equipment.profile_fields(u, b))

    def characters(self) -> list[Character]:
        return [self.character(i) for i in self.active_slots]

    def slot(self, i: int) -> Slot:
        if i not in self.active_slots:
            raise KeyError(f"slot {i} jest pusty")
        if i not in self._slots:
            e = self.entries[i]
            self._slots[i] = Slot.parse(i, self.data[e.offset + 16:e.offset + e.size], e.md5.hex())
        return self._slots[i]
