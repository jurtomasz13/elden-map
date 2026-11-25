"""Warstwa zgodności Windows / Linux dla narzędzi ekstrakcji (tylko odczyt plików gry).

- folder gry: zmienna ER_GAME_DIR albo automatycznie z bibliotek Steama (libraryfolders.vdf: Windows, Linux, Flatpak)
- AES (zakresy w archiwach BDT: ECB, regulation.bin: CBC): Windows CNG (bcrypt.dll) albo pakiet `cryptography`
- Oodle Kraken (DCX/KRAK): oo2core_6_win64.dll z folderu gry (Windows), natywna biblioteka Oodle wskazana w ER_OODLE_LIB
  (Linux: liboo2corelinux64.so), a w ostateczności pakiet `kraken-decompressor` (ooz)
- ZSTD (DCX/ZSTD): `compression.zstd` (Python 3.14+) albo pakiet `zstandard`
"""
import ctypes
import os
import re
import sys

IS_WIN = sys.platform == "win32"
APP_ID = "1245620"                      # Elden Ring w Steamie


# ---------------- folder gry ----------------
def steam_roots():
    """Katalogi instalacji Steama na tym systemie (mogą nie istnieć)."""
    home = os.path.expanduser("~")
    if IS_WIN:
        return [os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Steam"),
                os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Steam")]
    return [os.path.join(home, ".steam", "steam"), os.path.join(home, ".local", "share", "Steam"),
            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
            os.path.join(home, "snap", "steam", "common", ".local", "share", "Steam")]


def steam_libraries():
    """Wszystkie biblioteki Steama (z libraryfolders.vdf), bez duplikatów."""
    libs = []
    for root in steam_roots():
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            txt = open(vdf, encoding="utf-8", errors="replace").read()
            libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', txt)]
        libs.append(root)
    seen, out = set(), []
    for lib in libs:
        key = os.path.normcase(os.path.realpath(lib))
        if key not in seen and os.path.isdir(lib):
            seen.add(key)
            out.append(lib)
    return out


def find_game_dir():
    env = os.environ.get("ER_GAME_DIR")
    if env:
        return env
    for lib in steam_libraries():
        d = os.path.join(lib, "steamapps", "common", "ELDEN RING", "Game")
        if os.path.exists(os.path.join(d, "eldenring.exe")):
            return d
    return r"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game"   # domyślnie (komunikat błędu pokaże ścieżkę)


def proton_save_roots():
    """Linux/Proton: …/steamapps/compatdata/1245620/pfx/drive_c/users/steamuser/AppData/Roaming/EldenRing."""
    return [os.path.join(lib, "steamapps", "compatdata", APP_ID, "pfx", "drive_c", "users", "steamuser",
                         "AppData", "Roaming", "EldenRing") for lib in steam_libraries()]


# ---------------- AES ----------------
def _bcrypt_decrypt(mode, key, data, iv=None):
    import ctypes.wintypes as wt
    bc = ctypes.WinDLL("bcrypt")
    alg, hk = ctypes.c_void_p(), ctypes.c_void_p()
    assert bc.BCryptOpenAlgorithmProvider(ctypes.byref(alg), "AES", None, 0) == 0
    m = ctypes.create_unicode_buffer("ChainingMode" + mode)
    assert bc.BCryptSetProperty(alg, "ChainingMode", m, ctypes.sizeof(m), 0) == 0
    assert bc.BCryptGenerateSymmetricKey(alg, ctypes.byref(hk), None, 0, key, len(key), 0) == 0
    out, res = ctypes.create_string_buffer(len(data)), wt.ULONG()
    ivb = ctypes.create_string_buffer(bytes(iv), 16) if iv else None
    st = bc.BCryptDecrypt(hk, ctypes.create_string_buffer(bytes(data), len(data)), len(data), None,
                          ivb, 16 if iv else 0, out, len(data), ctypes.byref(res), 0)
    bc.BCryptDestroyKey(hk)
    bc.BCryptCloseAlgorithmProvider(alg, 0)
    assert st == 0, f"BCryptDecrypt {st & 0xFFFFFFFF:#x}"
    return out.raw[:res.value]


def _crypto_decrypt(mode, key, data, iv=None):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        return _py_aes_decrypt(mode, bytes(key), bytes(data), bytes(iv) if iv else None)   # bez zależności, wolniej
    m = modes.ECB() if mode == "ECB" else modes.CBC(bytes(iv))
    d = Cipher(algorithms.AES(bytes(key)), m).decryptor()
    return d.update(bytes(data)) + d.finalize()


# ---- AES w czystym Pythonie (tylko odszyfrowanie; zapas, gdy brak pakietu cryptography) ----
def _aes_tables():
    sbox, inv, p, q = [0] * 256, [0] * 256, 1, 1
    while True:                                              # S-box z odwrotności w GF(2^8) i przekształcenia afinicznego
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        q ^= q << 1; q ^= q << 2; q ^= q << 4; q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ ((q << 1) | (q >> 7)) & 0xFF ^ ((q << 2) | (q >> 6)) & 0xFF ^ ((q << 3) | (q >> 5)) & 0xFF ^ ((q << 4) | (q >> 4)) & 0xFF
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    for i, v in enumerate(sbox):
        inv[v] = i

    def mul(a, b):
        r = 0
        while b:
            if b & 1:
                r ^= a
            a = ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1
            b >>= 1
        return r
    # tablice odwrotnej rundy: InvSubBytes + InvMixColumns w jednym kroku (słowa 32-bit)
    td = [[0] * 256 for _ in range(4)]
    for x in range(256):
        s = inv[x]
        w = (mul(s, 14) << 24) | (mul(s, 9) << 16) | (mul(s, 13) << 8) | mul(s, 11)
        for k in range(4):
            td[k][x] = ((w >> (8 * k)) | (w << (32 - 8 * k))) & 0xFFFFFFFF
    imix = [[0] * 256 for _ in range(4)]                     # InvMixColumns dla kluczy rund (bez S-boxa)
    for x in range(256):
        w = (mul(x, 14) << 24) | (mul(x, 9) << 16) | (mul(x, 13) << 8) | mul(x, 11)
        for k in range(4):
            imix[k][x] = ((w >> (8 * k)) | (w << (32 - 8 * k))) & 0xFFFFFFFF
    return sbox, inv, td, imix


_AES_T = None


def _aes_dec_keys(key):
    sbox, _inv, _td, imix = _AES_T
    nk = len(key) // 4
    nr = nk + 6
    w = [int.from_bytes(key[4 * i:4 * i + 4], "big") for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = w[i - 1]
        if i % nk == 0:
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t = (sbox[t >> 24] << 24) | (sbox[(t >> 16) & 0xFF] << 16) | (sbox[(t >> 8) & 0xFF] << 8) | sbox[t & 0xFF]
            t ^= rcon << 24
            rcon = ((rcon << 1) ^ 0x1B) & 0xFF if rcon & 0x80 else rcon << 1
        elif nk > 6 and i % nk == 4:
            t = (sbox[t >> 24] << 24) | (sbox[(t >> 16) & 0xFF] << 16) | (sbox[(t >> 8) & 0xFF] << 8) | sbox[t & 0xFF]
        w.append(w[i - nk] ^ t)
    rk = [w[4 * r:4 * r + 4] for r in range(nr + 1)][::-1]  # klucze w kolejności odszyfrowania
    for r in range(1, nr):                                   # rundy środkowe: klucz po InvMixColumns
        rk[r] = [imix[0][v >> 24] ^ imix[1][(v >> 16) & 0xFF] ^ imix[2][(v >> 8) & 0xFF] ^ imix[3][v & 0xFF] for v in rk[r]]
    return rk, nr


def _py_aes_decrypt(mode, key, data, iv=None):
    global _AES_T
    if _AES_T is None:
        _AES_T = _aes_tables()
    _sbox, inv, td, _imix = _AES_T
    t0, t1, t2, t3 = td
    rk, nr = _aes_dec_keys(key)
    out = bytearray(len(data))
    prev = iv
    for off in range(0, len(data) - len(data) % 16, 16):
        blk = data[off:off + 16]
        s0, s1, s2, s3 = (int.from_bytes(blk[i:i + 4], "big") ^ rk[0][i // 4] for i in (0, 4, 8, 12))
        for r in range(1, nr):
            k = rk[r]
            s0, s1, s2, s3 = (t0[s0 >> 24] ^ t1[(s3 >> 16) & 0xFF] ^ t2[(s2 >> 8) & 0xFF] ^ t3[s1 & 0xFF] ^ k[0],
                              t0[s1 >> 24] ^ t1[(s0 >> 16) & 0xFF] ^ t2[(s3 >> 8) & 0xFF] ^ t3[s2 & 0xFF] ^ k[1],
                              t0[s2 >> 24] ^ t1[(s1 >> 16) & 0xFF] ^ t2[(s0 >> 8) & 0xFF] ^ t3[s3 & 0xFF] ^ k[2],
                              t0[s3 >> 24] ^ t1[(s2 >> 16) & 0xFF] ^ t2[(s1 >> 8) & 0xFF] ^ t3[s0 & 0xFF] ^ k[3])
        k = rk[nr]
        res = bytearray(16)
        for c, (a, b, cc, d) in enumerate(((s0, s3, s2, s1), (s1, s0, s3, s2), (s2, s1, s0, s3), (s3, s2, s1, s0))):
            v = ((inv[a >> 24] << 24) | (inv[(b >> 16) & 0xFF] << 16) | (inv[(cc >> 8) & 0xFF] << 8) | inv[d & 0xFF]) ^ k[c]
            res[4 * c:4 * c + 4] = v.to_bytes(4, "big")
        if mode == "CBC":
            res = bytes(x ^ y for x, y in zip(res, prev))
            prev = blk
        out[off:off + 16] = res
    out[len(data) - len(data) % 16:] = data[len(data) - len(data) % 16:]
    return bytes(out)


def aes_ecb_decrypt(key, data):
    return _bcrypt_decrypt("ECB", key, data) if IS_WIN else _crypto_decrypt("ECB", key, data)


def aes_cbc_decrypt(key, iv, data):
    return _bcrypt_decrypt("CBC", key, data, iv) if IS_WIN else _crypto_decrypt("CBC", key, data, iv)


# ---------------- Oodle Kraken ----------------
_oodle = None


def kraken_decompress(comp, raw_size, game_dir):
    """DCX/KRAK. Windows: DLL z folderu gry; wszędzie indziej (lub gdy DLL brak): pakiet kraken-decompressor."""
    global _oodle
    dll = os.path.join(game_dir, "oo2core_6_win64.dll")
    lib = os.environ.get("ER_OODLE_LIB")                  # np. liboo2corelinux64.so (to samo API co DLL z gry)
    if lib or (IS_WIN and os.path.exists(dll)):
        if _oodle is None:
            _oodle = ctypes.CDLL(lib) if lib else ctypes.WinDLL(dll)
            _oodle.OodleLZ_Decompress.restype = ctypes.c_ssize_t
            _oodle.OodleLZ_Decompress.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_ssize_t,
                                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t,
                                                  ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_int]
        out = ctypes.create_string_buffer(raw_size)
        n = _oodle.OodleLZ_Decompress(comp, len(comp), out, raw_size, 1, 0, 0, None, 0, None, None, None, 0, 3)
        assert n == raw_size, f"Oodle zwrócił {n}, oczekiwano {raw_size}"
        return out.raw
    if os.path.exists(dll) or os.environ.get("ER_OODLE_HELPER_PY"):
        return _helper_decompress(comp, raw_size, dll)      # Linux: DLL z gry przez Wine (ten sam dekoder co gra)
    try:
        from kraken_decompressor import decompress
    except ImportError as e:
        raise RuntimeError("Brak dekompresora Oodle Kraken: nie ma oo2core_6_win64.dll w folderze gry "
                           f"({game_dir}) — ustaw ER_GAME_DIR albo ER_OODLE_LIB") from e
    out = decompress(bytes(comp), raw_size)
    assert len(out) == raw_size, f"kraken-decompressor zwrócił {len(out)} B, oczekiwano {raw_size}"
    return bytes(out)


# ---------------- Oodle przez Wine (Linux) ----------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WINPY_URL = "https://www.python.org/ftp/python/3.14.3/python-3.14.3-embed-amd64.zip"
WINPY_SHA256 = "ad4961a479dedbeb7c7d113253f8db1b1935586b73c27488712beec4f2c894e6"
_helper = None


def _to_wine(path):
    """Ścieżka Linuksa → ścieżka widziana w Wine (dysk Z: = /)."""
    return "Z:" + os.path.abspath(path).replace("/", "\\")


def win_python():
    """python.exe dla Windows do uruchomienia w Wine: ER_WIN_PYTHON, paczka (runtime/winpython) albo pobrany raz z python.org."""
    for p in (os.environ.get("ER_WIN_PYTHON"), os.path.join(ROOT, "..", "runtime", "winpython", "python.exe"),
              os.path.join(ROOT, "runtime", "winpython", "python.exe"),
              os.path.join(ROOT, "assets", "cache", "winpython", "python.exe")):
        if p and os.path.exists(p):
            return p
    import hashlib
    import io
    import urllib.request
    import zipfile
    dest = os.path.join(ROOT, "assets", "cache", "winpython")
    print(f"Pobieram Pythona dla Windows (do uruchomienia Oodle w Wine): {WINPY_URL}", file=sys.stderr, flush=True)
    data = urllib.request.urlopen(urllib.request.Request(WINPY_URL, headers={"User-Agent": "elden-map-setup"}), timeout=300).read()
    if hashlib.sha256(data).hexdigest() != WINPY_SHA256:
        raise RuntimeError("Zła suma kontrolna pobranego Pythona dla Windows")
    os.makedirs(dest, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(data)).extractall(dest)
    return os.path.join(dest, "python.exe")


def _helper_decompress(comp, raw_size, dll):
    global _helper
    import shutil
    import struct
    import subprocess
    if _helper is None or _helper.poll() is not None:
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oodle_helper.py")
        if os.environ.get("ER_OODLE_HELPER_PY"):            # test / własny Python dla Windows bez Wine
            cmd = [os.environ["ER_OODLE_HELPER_PY"], helper, dll]
        else:
            wine = shutil.which("wine") or shutil.which("wine64")
            if not wine:
                raise RuntimeError("Do rozpakowania archiwów gry na Linuxie potrzebne jest Wine "
                                   "(np. CachyOS/Arch: sudo pacman -S wine; Ubuntu: sudo apt install wine) "
                                   "— albo ER_OODLE_LIB z natywną biblioteką Oodle")
            cmd = [wine, win_python(), _to_wine(helper), _to_wine(dll)]
        env = {**os.environ, "WINEDEBUG": "-all",
               "WINEDLLOVERRIDES": "mscoree=;mshtml=",       # bez okien z pytaniem o Wine Mono / Gecko
               # osobny prefiks Wine aplikacji (nie ruszamy ~/.wine ani prefiksów Protona)
               "WINEPREFIX": os.environ.get("ER_WINEPREFIX") or os.path.join(
                   os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "elden-map", "wine")}
        os.makedirs(os.path.dirname(env["WINEPREFIX"]), exist_ok=True)    # sam prefiks utworzy Wine
        print("Uruchamiam Oodle z gry przez Wine (pierwszy raz Wine przygotowuje prefiks — chwilę to trwa)…",
              file=sys.stderr, flush=True)
        _helper = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
    p = _helper
    p.stdin.write(struct.pack("<II", len(comp), raw_size) + bytes(comp))
    p.stdin.flush()
    head = p.stdout.read(4)
    if len(head) < 4:
        raise RuntimeError("Pomocnik Oodle (Wine) zakończył się — sprawdź, czy `wine --version` działa")
    n = struct.unpack("<i", head)[0]
    if n != raw_size:
        raise RuntimeError(f"Oodle (Wine) zwrócił {n}, oczekiwano {raw_size}")
    out = bytearray()
    while len(out) < n:
        chunk = p.stdout.read(n - len(out))
        if not chunk:
            raise RuntimeError("Pomocnik Oodle (Wine) przerwał przesyłanie danych")
        out += chunk
    return bytes(out)


# ---------------- ZSTD ----------------
def zstd_decompress(comp):
    try:
        from compression import zstd            # Python 3.14+
        return zstd.decompress(comp)
    except ImportError:
        try:
            import zstandard
        except ImportError as e:
            raise RuntimeError("Brak ZSTD — użyj Pythona 3.14+ albo: pip install zstandard") from e
        return zstandard.ZstdDecompressor().decompress(comp, max_output_size=1 << 31)
