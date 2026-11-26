"""EMEVD (Elden Ring), skrypty zdarzeń: zdarzenia, instrukcje (bank, id, argumenty), parametry.

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


def callers(scripts):
    """(scope, event id) -> [(caller scope, caller event id, instruction index, call args after the event id)].

    `scripts` maps a scope (map id or "common", "common_func") to parsed events; 2000[0] starts an event of the same
    script, 2000[6] one of common_func."""
    out = {}
    for scope, events in scripts.items():
        for eid, ev in events.items():
            for k, (bank, iid, a) in enumerate(ev["instrs"]):
                if bank == 2000 and iid in (0, 6) and len(a) >= 8:
                    target = struct.unpack_from("<I", a, 4)[0]
                    out.setdefault(("common_func" if iid == 6 else scope, target), []).append((scope, eid, k, a[8:]))
    return out


def instances(scripts, calls, scope, eid, depth=0):
    """[(scope that starts it, argument bytes)] for every place an event is started; a caller's own parameters are
    filled from its callers in turn (up to 5 levels). An event without parameters has one instance with no args."""
    if not scripts[scope][eid]["params"]:
        return [(scope, b"")]
    out = []
    for cscope, ceid, k, args in calls.get((scope, eid), []):
        own = [p for p in scripts[cscope][ceid]["params"] if p[0] == k]
        if not own:
            out.append((cscope, args))
        elif depth < 5:
            for gscope, gargs in instances(scripts, calls, cscope, ceid, depth + 1):
                out.append((cscope if cscope.startswith("m") else gscope, resolve(bytes(8) + args, own, k, gargs)[8:]))
    return out


def resolve(args, params, k, call):
    """Arguments of instruction k with its parameters copied from the bytes the event was started with."""
    a = bytearray(args)
    for pi, tgt, src, n in params:
        if pi == k:
            a[tgt:tgt + n] = call[src:src + n]
    return bytes(a)
