"""Pomiar opóźnienia: pamięć gry vs plik save.

Użycie:
    python live_watch.py <folder save'a> <eventflag_bst.txt> <ct_event_flags.csv> <plik logu>

- Plik save: jak save_watch.py (każdy zapis + zmienione flagi).
- Pamięć gry (TYLKO gdy nie działa EasyAntiCheat_EOS.exe): co 250 ms czyta blok flag
  z [[EventFlagMan]+0x28] i loguje zmiany z dokładnym czasem. Gdy ta sama flaga pojawi się
  potem w save, loguje opóźnienie „pamięć -> plik”.
- Przy działającym EAC skrypt NIE otwiera procesu gry (nawet do odczytu).
Wszystko tylko do odczytu: ReadProcessMemory + odczyt pliku.
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import er_save_probe as p  # noqa: E402
import save_watch as sw  # noqa: E402

MEM_POLL = 0.25
FILE_POLL = 0.1
GAME_EXE = "eldenring.exe"
EAC_EXE = "easyanticheat_eos.exe"
# wzorzec z SoulSplittera / „Flags Logger” w CT: mov r12, [rip+disp32] -> wskaźnik na EventFlagMan
EFM_AOB, EFM_DISP, EFM_NEXT = "44 89 7C 24 28 4C 8B 25 ?? ?? ?? ?? 4D 85 E4", 8, 12
WCM_AOB, WCM_DISP, WCM_NEXT = "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 0F 48 39 88", 3, 7
LOCAL_PLAYER = 0x10EF8
# PlayerIns: w grze 2.7.1.0 (CT) pozycja +0x6B0 / mapa +0x6C0; w 2.7.2.0 przesunięte o 0x10.
PLAYER_POS, PLAYER_MAP = 0x6C0, 0x6D0

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
TH32CS_SNAPPROCESS, TH32CS_SNAPMODULE, TH32CS_SNAPMODULE32 = 0x2, 0x8, 0x10
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION = 0x10, 0x400


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD),
                ("hModule", wt.HMODULE), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]


def processes():
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PROCESSENTRY32W()
    e.dwSize = ctypes.sizeof(e)
    out = {}
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        out[e.szExeFile.lower()] = e.th32ProcessID
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return out


def main_module(pid):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    e = MODULEENTRY32W()
    e.dwSize = ctypes.sizeof(e)
    try:
        if k32.Module32FirstW(snap, ctypes.byref(e)):
            while True:
                if e.szModule.lower() == GAME_EXE:
                    return e.modBaseAddr, e.modBaseSize
                if not k32.Module32NextW(snap, ctypes.byref(e)):
                    break
    finally:
        k32.CloseHandle(snap)
    return None


class Game:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess nie powiódł się (błąd {ctypes.get_last_error()})")
        mod = main_module(pid)
        if not mod:
            raise OSError("nie znaleziono modułu eldenring.exe")
        self.base, self.size = mod

    def read(self, addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) \
                or got.value != n:
            raise OSError(f"ReadProcessMemory 0x{addr:X} nie powiódł się")
        return buf.raw

    def q(self, addr):
        return struct.unpack("<Q", self.read(addr, 8))[0]

    def image(self):
        data = bytearray(self.size)
        step = 0x100000
        for off in range(0, self.size, step):
            n = min(step, self.size - off)
            try:
                data[off:off + n] = self.read(self.base + off, n)
            except OSError:
                pass
        return bytes(data)

    def close(self):
        k32.CloseHandle(self.h)


def aob_static(img, base, pattern, disp, nxt):
    rx = re.compile(b"".join(b"." if t.startswith("?") else re.escape(bytes([int(t, 16)]))
                             for t in pattern.split()), re.S)
    hits = [m.start() for m in rx.finditer(img)]
    if len(hits) != 1:
        raise OSError(f"wzorzec {pattern[:20]}… trafił {len(hits)} razy")
    h = hits[0]
    return base + h + nxt + struct.unpack_from("<i", img, h + disp)[0]


def main(folder, bst_path, ct_path, log_path):
    bst = p.load_bst(bst_path)
    inv = {pos: blk for blk, pos in bst.items()}
    names = sw.load_names(ct_path)
    log = open(log_path, "a", encoding="utf-8", buffering=1)

    def out(msg):
        line = f"[{sw.now()}] {msg}"
        print(line, flush=True)
        log.write(line + "\n")

    def flag_id(byte, bit):
        blk = inv.get(byte // 125)
        return blk * 1000 + (byte % 125) * 8 + (7 - bit) if blk is not None else None

    files = sw.FileWatcher(folder, inv, names, out)
    game = None
    efm_static = wcm_static = None
    mem_flags = None
    mem_seen = {}            # flag_id -> (czas w pamięci, wartość)
    mem_state = "?"
    next_mem = 0.0

    out("START live_watch (pamięć + plik)")
    while True:
        time.sleep(FILE_POLL)
        for fn, changes in files.poll():
            for fid, on in changes:
                seen = mem_seen.pop(fid, None)
                if seen and seen[1] == on:
                    out(f"      opóźnienie pamięć -> {fn}: {time.time() - seen[0]:.1f} s dla flagi {fid}")
        if time.time() < next_mem:
            continue
        next_mem = time.time() + MEM_POLL
        procs = processes()
        if EAC_EXE in procs:
            if game:
                game.close()
                game = None
            if mem_state != "eac":
                out("PAMIĘĆ: działa EasyAntiCheat, nie dotykam procesu gry (tylko plik save)")
                mem_state = "eac"
            continue
        if GAME_EXE not in procs:
            if game:
                game.close()
                game = None
            if mem_state != "nogame":
                out("PAMIĘĆ: gra nie działa, czekam na eldenring.exe")
                mem_state = "nogame"
            continue
        try:
            if not game:
                game = Game(procs[GAME_EXE])
                img = game.image()
                efm_static = aob_static(img, game.base, EFM_AOB, EFM_DISP, EFM_NEXT)
                wcm_static = aob_static(img, game.base, WCM_AOB, WCM_DISP, WCM_NEXT)
                del img
                mem_flags = None
                out(f"PAMIĘĆ: podłączono (pid {procs[GAME_EXE]}, baza 0x{game.base:X}, "
                    f"EventFlagMan @0x{efm_static:X}, WorldChrMan @0x{wcm_static:X})")
                mem_state = "ok"
            efm = game.q(efm_static)
            if not efm or not struct.unpack("<i", game.read(efm + 0x1C, 4))[0]:
                continue  # menu główne / ładowanie
            flags = game.read(game.q(efm + 0x28), p.FLAGS_SIZE)
            if mem_flags is not None and flags != mem_flags:
                t = time.time()
                diffs = []
                for c in range(0, len(flags), 4096):
                    if flags[c:c + 4096] == mem_flags[c:c + 4096]:
                        continue
                    for k in range(c, min(c + 4096, len(flags))):
                        x = flags[k] ^ mem_flags[k]
                        for bit in range(8):
                            if x >> bit & 1:
                                diffs.append((flag_id(k, bit), flags[k] >> bit & 1))
                try:
                    pl = game.q(game.q(game.q(wcm_static) + LOCAL_PLAYER))
                    x, y, z = struct.unpack("<3f", game.read(pl + PLAYER_POS, 12))
                    m = game.read(pl + PLAYER_MAP, 4)
                    pos = (f"pozycja ({x:.1f}, {y:.1f}, {z:.1f}) "
                           f"m{m[3]:02d}_{m[2]:02d}_{m[1]:02d}_{m[0]:02d}")
                except OSError:
                    pos = "pozycja nieznana"
                out(f"PAMIĘĆ: {len(diffs)} zmienionych flag, {pos}")
                for fid, on in diffs[:40]:
                    mem_seen[fid] = (t, on)
                    out(f"      {'+' if on else '-'} {fid}  {names.get(fid, '')}")
            mem_flags = flags
        except OSError as e:
            out(f"PAMIĘĆ: błąd ({e}), spróbuję ponownie")
            if game:
                game.close()
            game = None
            mem_state = "err"
            next_mem = time.time() + 5


if __name__ == "__main__":
    main(*sys.argv[1:5])
