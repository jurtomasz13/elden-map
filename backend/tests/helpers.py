"""Pomocnicze funkcje testów: kopie save'ów w katalogu tymczasowym, symulacja zapisu gry.

Testy NIGDY nie piszą do folderu save'ów gry: źródło jest tylko czytane (shutil.copy2),
a każda modyfikacja dotyczy kopii w tempfile.mkdtemp(). `assert_not_game_dir` pilnuje tego.
Źródło save'ów: zmienna środowiskowa ER_SAVE_DIR albo automatycznie %APPDATA%/EldenRing/<SteamID>.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile

BACKEND = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from erbackend.savefile import FILE_KINDS, SaveFile  # noqa: E402
from erbackend.service import find_save_dir, save_roots  # noqa: E402

GAME_ROOTS = [os.path.normcase(os.path.abspath(r)) for r in save_roots()]   # Windows i Linux/Proton


def source_save_dir() -> str | None:
    d = os.environ.get("ER_SAVE_DIR") or find_save_dir()
    if d and any(os.path.exists(os.path.join(d, fn)) for fn in FILE_KINDS.values()):
        return d
    return None


def assert_not_game_dir(path: str):
    p = os.path.normcase(os.path.abspath(path))
    if any(p == r or p.startswith(r + os.sep) for r in GAME_ROOTS):
        raise AssertionError(f"test próbuje pisać do folderu save'ów gry: {path}")
    src = source_save_dir()
    if src and os.path.normcase(os.path.abspath(src)) in (p, os.path.dirname(p)):
        raise AssertionError(f"test próbuje pisać do folderu źródłowego: {path}")


def copy_saves(dest: str | None = None) -> str:
    """Kopiuje ER0000.sl2/.co2 do nowego katalogu tymczasowego i zwraca jego ścieżkę."""
    src = source_save_dir()
    if src is None:
        raise FileNotFoundError("brak save'ów do testów (ustaw ER_SAVE_DIR)")
    dest = dest or tempfile.mkdtemp(prefix="er-backend-test-")
    assert_not_game_dir(dest)
    for fn in FILE_KINDS.values():
        p = os.path.join(src, fn)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(dest, fn))
    return dest


def patched_bytes(path: str, slot: int, flag_values: dict[int, bool], flagmap) -> bytes:
    """Zwraca zawartość pliku z ustawionymi flagami w danym slocie i przeliczonym MD5 wpisu."""
    sf = SaveFile.read(path)
    s = sf.slot(slot)
    entry = sf.entries[slot]
    data = bytearray(sf.data)
    base = entry.offset + 16 + s.flags_offset
    for fid, val in flag_values.items():
        byte, bit = flagmap.location(fid)
        if val:
            data[base + byte] |= 1 << bit
        else:
            data[base + byte] &= ~(1 << bit) & 0xFF
    body = bytes(data[entry.offset + 16:entry.offset + entry.size])
    data[entry.offset:entry.offset + 16] = hashlib.md5(body).digest()
    return bytes(data)


def replace_atomically(path: str, content: bytes):
    """Symulacja zapisu gry: zapis do pliku tymczasowego obok + os.replace (atomowa podmiana)."""
    assert_not_game_dir(path)
    tmp = path + ".tmp-write"
    with open(tmp, "wb") as f:
        f.write(content)
    os.replace(tmp, path)
