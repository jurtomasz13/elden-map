"""Odczyt plików z archiwów Elden Ring (BHD5/BDT) — tylko odczyt.

- spis plików: BHD5 (odszyfrowany kluczem RSA z eldenring.exe, cache w assets/cache)
- szyfrowanie zakresów: AES-128-ECB (compat: bcrypt.dll na Windows, pakiet cryptography na Linuxie)
- kompresja DCX/KRAK: Oodle (compat: DLL z folderu gry na Windows, pakiet kraken-decompressor na Linuxie)
"""
import os
import struct

import bhd
import compat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.path.join(ROOT, "assets", "cache")


def path_hash(path):
    """Hash ścieżki w Elden Ring: 64-bit, mnożnik 0x85, małe litery, '/' na początku."""
    p = path.lower().replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    h = 0
    for ch in p:
        h = (h * 0x85 + ord(ch)) & 0xFFFFFFFFFFFFFFFF
    return h


def undcx(data):
    """Rozpakowuje DCX (KRAK przez Oodle, DFLT przez zlib). Inne dane zwraca bez zmian."""
    if data[:4] != b"DCX\0":
        return data
    raw_size, comp_size = struct.unpack_from(">II", data, 0x1C)
    fmt = data[0x28:0x2C]
    start = struct.unpack_from(">I", data, 0x14)[0]
    comp = data[start:start + comp_size]
    if fmt == b"KRAK":
        return compat.kraken_decompress(comp, raw_size, bhd.GAME_DIR)
    if fmt == b"DFLT":
        import zlib
        return zlib.decompress(comp)
    if fmt == b"ZSTD":
        return compat.zstd_decompress(comp)
    raise ValueError(f"nieobsługiwany DCX {fmt}")


# ---------------- BHD5 ----------------
class Archive:
    def __init__(self, name, keys=None):
        self.name = name
        os.makedirs(CACHE, exist_ok=True)
        cache = os.path.join(CACHE, name + ".bhd5")
        if os.path.exists(cache):
            self.bhd = open(cache, "rb").read()
        else:
            self.bhd = bhd.decrypt_bhd(name, keys or bhd.exe_keys())
            open(cache, "wb").write(self.bhd)
        self.bdt_path = os.path.join(bhd.GAME_DIR, name + ".bdt")
        self.files = self._parse()

    def _parse(self):
        b = self.bhd
        assert b[:4] == b"BHD5"
        bucket_count, buckets_off = struct.unpack_from("<ii", b, 0x10)
        files = {}
        for i in range(bucket_count):
            count, off = struct.unpack_from("<ii", b, buckets_off + i * 8)
            for j in range(count):
                o = off + j * 40
                h, padded, unpadded, file_off, sha_off, aes_off = struct.unpack_from("<QiiqqQ", b, o)
                files[h] = (padded, unpadded, file_off, aes_off)
        return files

    def read(self, path_or_hash):
        h = path_or_hash if isinstance(path_or_hash, int) else path_hash(path_or_hash)
        padded, unpadded, off, aes_off = self.files[h]
        with open(self.bdt_path, "rb") as f:
            f.seek(off)
            data = bytearray(f.read(padded))
        if aes_off:
            key = self.bhd[aes_off:aes_off + 16]
            n = struct.unpack_from("<i", self.bhd, aes_off + 16)[0]
            for k in range(n):
                s, e = struct.unpack_from("<qq", self.bhd, aes_off + 20 + k * 16)
                if s == -1 or e <= s:
                    continue
                data[s:e] = compat.aes_ecb_decrypt(key, data[s:e])
        return bytes(data[:unpadded or padded])


_archives = {}


def find(path):
    """Szuka pliku po ścieżce we wszystkich archiwach. Zwraca (archiwum, dane) albo None."""
    h = path_hash(path)
    for name in bhd.ARCHIVES:
        if name not in _archives:
            _archives[name] = Archive(name)
        if h in _archives[name].files:
            return name, _archives[name].read(h)
    return None
