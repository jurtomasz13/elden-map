"""Mapowanie ID flagi zdarzenia -> (bajt, bit) w bloku flag oraz diff dwóch bloków.

Tabela `eventflag_bst.txt` (ClayAmore/ER-Save-Lib, commit 664ff9e8) ma linie `blok,pozycja`:
flaga `F` leży w bloku `F // 1000`, indeks w bloku `F % 1000`; blok ma 125 bajtów (1000 bitów),
a jego początek to `pozycja * 125`. Bity liczone od najstarszego (bit 7 = indeks 0).
Zweryfikowane w docs/04-otwarte-pytania.md. Repo źródłowe nie ma licencji: plik czytamy
lokalnie z docs/data, nie kopiujemy go do backend/.
"""
from __future__ import annotations

import os

BLOCK_BYTES = 125
FLAGS_PER_BLOCK = 1000

DEFAULT_BST = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "data", "er-save-lib", "eventflag_bst.txt"))


class FlagMap:
    def __init__(self, block_to_pos: dict[int, int]):
        self.block_to_pos = block_to_pos
        self.pos_to_block = {p: b for b, p in block_to_pos.items()}

    @classmethod
    def load(cls, path: str = DEFAULT_BST) -> "FlagMap":
        mapping = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    b, p = line.split(",")
                    mapping[int(b)] = int(p)
        return cls(mapping)

    def location(self, flag_id: int) -> tuple[int, int] | None:
        """ID flagi -> (bajt w bloku flag, numer bitu od najmłodszego) albo None, gdy blok nieznany."""
        if flag_id < 0:
            return None
        block, index = divmod(flag_id, FLAGS_PER_BLOCK)
        pos = self.block_to_pos.get(block)
        if pos is None:
            return None
        return pos * BLOCK_BYTES + index // 8, 7 - index % 8

    def known(self, flag_id: int) -> bool:
        return self.location(flag_id) is not None

    def get(self, flags: bytes, flag_id: int) -> bool | None:
        """Stan flagi: True/False, albo None gdy ID jest spoza tabeli."""
        loc = self.location(flag_id)
        if loc is None or loc[0] >= len(flags):
            return None
        return bool((flags[loc[0]] >> loc[1]) & 1)

    def flag_id_at(self, byte_offset: int, bit: int) -> int | None:
        block = self.pos_to_block.get(byte_offset // BLOCK_BYTES)
        if block is None:
            return None
        return block * FLAGS_PER_BLOCK + (byte_offset % BLOCK_BYTES) * 8 + (7 - bit)

    def diff(self, old: bytes, new: bytes, chunk: int = 4096) -> list[tuple[int | None, bool, int, int]]:
        """Zmienione bity: lista (flag_id|None, nowa_wartość, bajt, bit), posortowana po ID."""
        out = []
        n = min(len(old), len(new))
        for c in range(0, n, chunk):
            if old[c:c + chunk] == new[c:c + chunk]:
                continue
            for k in range(c, min(c + chunk, n)):
                x = old[k] ^ new[k]
                if not x:
                    continue
                for bit in range(8):
                    if x >> bit & 1:
                        out.append((self.flag_id_at(k, bit), bool(new[k] >> bit & 1), k, bit))
        out.sort(key=lambda t: (t[0] is None, t[0] or 0, t[2], t[3]))
        return out
