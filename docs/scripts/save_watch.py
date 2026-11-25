"""Pomiar: kiedy Elden Ring zapisuje save i co się w nim zmienia.

Użycie:
    python save_watch.py <folder save'a> <eventflag_bst.txt> <ct_event_flags.csv> <plik logu>

Co ~100 ms sprawdza (os.stat) pliki ER0000.sl2 / ER0000.co2 w folderze. Po zmianie czeka chwilę
(debounce), czyta plik (tylko odczyt), sprawdza sumy MD5 i porównuje blok flag każdej postaci
z poprzednim odczytem. Loguje: czas zapisu, odstęp od poprzedniego, zmienione flagi (ID + opis
z tabeli CE, jeśli znany), zmianę liczby śmierci i pozycji.
Klasa FileWatcher jest też używana przez live_watch.py.
"""
import csv
import datetime as dt
import hashlib
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import er_save_probe as p  # noqa: E402

POLL = 0.1
DEBOUNCE = 0.3
FILES = ("ER0000.sl2", "ER0000.co2")
MAX_LOGGED_FLAGS = 40


def now():
    return dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def load_names(ct_path):
    names = {}
    with open(ct_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            g = r["group"].replace('"', "").split("/")[-1]
            names[int(r["flag_id"])] = f"{g}: {r['description']}".strip(": ")
    return names


def snapshot(path):
    """{slot: (imię, flagi, śmierci, (pozycja, mapa), md5)} albo None, gdy plik jest w trakcie zapisu."""
    with open(path, "rb") as f:
        d = f.read()
    entries = p.read_bnd4(d)
    if not all(ok for _, _, _, ok in entries):
        return None
    u = d[entries[p.PROFILE_ENTRY][1] + 16:]
    out = {}
    for i in range(p.SLOT_COUNT):
        if not u[p.PROFILE_ACTIVE + i]:
            continue
        b = p.PROFILE_SUMMARY + i * p.PROFILE_SUMMARY_SIZE
        name = u[b:b + 0x22].decode("utf-16le").split("\0")[0]
        s = d[p.FIRST_SLOT_OFFSET + i * p.SLOT_SIZE + 16:p.FIRST_SLOT_OFFSET + (i + 1) * p.SLOT_SIZE]
        flags, start, _, _ = p.slot_flags(s)
        deaths = struct.unpack_from("<I", s, start - 0x1A)[0]
        o = start + p.FLAGS_SIZE + 1
        for _ in range(5):
            o += 4 + struct.unpack_from("<i", s, o)[0]
        pos = struct.unpack_from("<3f", s, o)
        m = s[o + 12:o + 16]
        out[i] = (name, flags, deaths, (pos, f"m{m[3]:02d}_{m[2]:02d}_{m[1]:02d}_{m[0]:02d}"),
                  hashlib.md5(s).hexdigest())
    return out


class FileWatcher:
    def __init__(self, folder, inv, names, out):
        self.folder, self.inv, self.names, self.out = folder, inv, names, out
        self.state, self.last_mtime, self.last_write = {}, {}, {}
        for fn in FILES:
            path = os.path.join(folder, fn)
            if os.path.exists(path):
                self.last_mtime[fn] = os.stat(path).st_mtime_ns
                self.state[fn] = snapshot(path)
        out(f"PLIK: obserwuję {folder} ({', '.join(self.last_mtime)})")

    def poll(self):
        """Zwraca listę (plik, [(flag_id, nowa_wartość), ...]) dla plików zapisanych od ostatniego razu."""
        result = []
        for fn in FILES:
            path = os.path.join(self.folder, fn)
            try:
                mt = os.stat(path).st_mtime_ns
            except FileNotFoundError:
                continue
            if mt == self.last_mtime.get(fn):
                continue
            detected = time.time()
            time.sleep(DEBOUNCE)
            snap = None
            for _ in range(20):
                try:
                    snap = snapshot(path)
                except (OSError, ValueError, struct.error):
                    snap = None
                if snap:
                    break
                time.sleep(0.2)
            self.last_mtime[fn] = os.stat(path).st_mtime_ns
            if not snap:
                self.out(f"PLIK {fn}: zmiana, ale nie udało się odczytać spójnego pliku")
                continue
            gap = detected - self.last_write[fn] if fn in self.last_write else None
            self.last_write[fn] = detected
            prev = self.state.get(fn) or {}
            changed = [i for i in snap if i not in prev or snap[i][4] != prev[i][4]]
            self.out(f"PLIK: ZAPIS {fn}" + (f" (+{gap:.1f} s od poprzedniego)" if gap else "")
                     + f", zmienione sloty: {changed or 'brak'}")
            all_diffs = []
            for i in changed:
                if i not in prev:
                    continue
                name, flags, deaths, (pos, pmap), _ = snap[i]
                _, oflags, odeaths, (opos, _), _ = prev[i]
                diffs = []
                for c in range(0, len(flags), 4096):
                    if flags[c:c + 4096] == oflags[c:c + 4096]:
                        continue
                    for k in range(c, min(c + 4096, len(flags))):
                        x = flags[k] ^ oflags[k]
                        for bit in range(8):
                            if x >> bit & 1:
                                blk = self.inv.get(k // 125)
                                fid = blk * 1000 + (k % 125) * 8 + (7 - bit) if blk is not None else None
                                diffs.append((fid, flags[k] >> bit & 1))
                moved = sum((a - b) ** 2 for a, b in zip(pos, opos)) ** 0.5
                self.out(f"  [{i}] {name}: {len(diffs)} zmienionych flag, śmierci {odeaths}->{deaths}, "
                         f"pozycja ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) {pmap}, przesunięcie {moved:.1f}")
                for fid, on in diffs[:MAX_LOGGED_FLAGS]:
                    self.out(f"      {'+' if on else '-'} {fid}  {self.names.get(fid, '')}")
                if len(diffs) > MAX_LOGGED_FLAGS:
                    self.out(f"      ... i {len(diffs) - MAX_LOGGED_FLAGS} więcej")
                all_diffs += diffs
            self.state[fn] = snap
            result.append((fn, all_diffs))
        return result


def main(folder, bst_path, ct_path, log_path):
    bst = p.load_bst(bst_path)
    inv = {pos: blk for blk, pos in bst.items()}
    log = open(log_path, "a", encoding="utf-8", buffering=1)

    def out(msg):
        line = f"[{now()}] {msg}"
        print(line, flush=True)
        log.write(line + "\n")

    w = FileWatcher(folder, inv, load_names(ct_path), out)
    while True:
        time.sleep(POLL)
        w.poll()


if __name__ == "__main__":
    main(*sys.argv[1:5])
