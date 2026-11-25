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
    except ImportError as e:
        raise RuntimeError("Brak pakietu 'cryptography' — zainstaluj: pip install -r requirements.txt") from e
    m = modes.ECB() if mode == "ECB" else modes.CBC(bytes(iv))
    d = Cipher(algorithms.AES(bytes(key)), m).decryptor()
    return d.update(bytes(data)) + d.finalize()


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
    try:
        from kraken_decompressor import decompress
    except ImportError as e:
        raise RuntimeError("Brak dekompresora Oodle Kraken — zainstaluj: pip install -r requirements.txt "
                           "(pakiet kraken-decompressor)") from e
    out = decompress(bytes(comp), raw_size)
    assert len(out) == raw_size, f"kraken-decompressor zwrócił {len(out)} B, oczekiwano {raw_size}"
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
