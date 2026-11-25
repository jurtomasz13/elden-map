"""EMEVD (Elden Ring) — skrypty zdarzeń: zdarzenia, instrukcje (bank, id, argumenty), parametry.

Nagłówek (64-bit, wersja 0xCD): 'EVD\\0', +0x10 liczba zdarzeń, +0x18 offset zdarzeń, +0x20 liczba instrukcji,
+0x28 offset instrukcji, +0x50 liczba parametrów, +0x58 offset parametrów, +0x78 offset argumentów.
Zdarzenie (0x30): i64 id, i64 liczba instrukcji, i64 offset (bajty od początku tablicy instrukcji),
                  i64 liczba parametrów, i64 offset parametrów, i32 restBehavior.
Instrukcja (0x20): i32 bank, i32 id, i64 długość argumentów, i64 offset argumentów (od bloku argumentów), i64 warstwa.
Parametr (0x20): i64 indeks instrukcji (w zdarzeniu), i64 bajt docelowy (w argumentach instrukcji),
                 i64 bajt źródłowy (w argumentach wywołania zdarzenia), i32 liczba bajtów.

Ważne instrukcje (banki EMEDF Elden Ring, sprawdzone na danych):
  2000[0]  InitializeEvent(slot, eventId, args...)        2000[6] InitializeCommonEvent(0, eventId, args...)
  2003[4]  AwardItemLot(lot)                              2003[36] AwardItemsIncludingClients(lot)
  2003[66] SetEventFlag(type, flag, state)
"""
import struct

import archive as A


def parse(d):
    assert d[:4] == b"EVD\0", d[:4]
    ev_n, ev_off, ins_n, ins_off = struct.unpack_from("<qqqq", d, 0x10)
    par_n, par_off = struct.unpack_from("<qq", d, 0x50)
    arg_off = struct.unpack_from("<q", d, 0x78)[0]
    events = {}
    for e in range(ev_n):
        eid, icount, ioff, pcount, poff, _rest = struct.unpack_from("<qqqqqi", d, ev_off + e * 0x30)
        instrs = []
        for k in range(icount):
            bank, iid, alen, aoff, _layer = struct.unpack_from("<iiqqq", d, ins_off + ioff + k * 0x20)
            instrs.append((bank, iid, d[arg_off + aoff:arg_off + aoff + alen]))
        params = [struct.unpack_from("<qqqi", d, par_off + poff + p * 0x20) for p in range(pcount)]
        events[eid] = {"instrs": instrs, "params": params}
    return events


def load(path):
    r = A.find(path)
    return parse(A.undcx(r[1])) if r else None


def ints(args):
    return list(struct.unpack_from(f"<{len(args) // 4}i", args)) if len(args) >= 4 else []
