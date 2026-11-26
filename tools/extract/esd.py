"""Parser skryptów rozmów (talk ESD, „fsSL”, format 64-bit), tylko do odczytu.

Układ (przesunięcia względem początku danych 0x6C, tabele jedna po drugiej):
  nagłówek 0x48 | grupy stanów N×0x20 {id, stany_off, liczba, …} | stany N×0x48 {id, warunki_off, n, wejście_off, n,
  wyjście_off, n, w_trakcie_off, n} | warunki N×0x38 {cel_off, polecenia_off, n, podwarunki_off, n, wyrażenie_off, dł}
  | polecenia N×0x18 {i32 bank, i32 id, argumenty_off, n} | argumenty N×0x10 {wyrażenie_off, dł} | …
Liczności z nagłówka pliku (+0x28 grupy, +0x30 stany, +0x38 warunki, +0x40 polecenia, +0x48 argumenty).

Wyrażenia (bajtkod): 0x00–0x7F liczba (b−64), 0x80 f32, 0x81 f64, 0x82 i32, 0x84–0x8A wywołanie funkcji z 0–6
argumentami (identyfikator funkcji jest pod argumentami na stosie), 0xA1 koniec, 0xA5 tekst UTF-16;
pozostałe bajty to operatory, tu zachowujemy je jako znaczniki.
"""
import struct

BASE = 0x6C


class Esd:
    def __init__(self, d):
        assert d[:4] == b"fsSL", "obsługiwany tylko format 64-bit"
        self.d = d
        h = struct.unpack_from("<27i", d, 4)
        n_groups, n_states, n_conds, n_cmds, n_args = h[9], h[11], h[13], h[15], h[17]
        off = BASE + 0x48
        self.groups_off = off; off += n_groups * 0x20
        self.states_off = off; off += n_states * 0x48
        self.conds_off = off; off += n_conds * 0x38
        self.cmds_off = off; off += n_cmds * 0x18
        self.args_off = off
        self.n = dict(groups=n_groups, states=n_states, conds=n_conds, cmds=n_cmds, args=n_args)

    def q(self, o, n=1):
        return struct.unpack_from(f"<{n}q", self.d, o)

    def expr(self, off, ln):
        """Wyrażenie jako lista: liczby i wywołania ('call', fid, [argumenty])."""
        b = self.d[BASE + off: BASE + off + ln]
        st, i = [], 0
        while i < len(b):
            c = b[i]; i += 1
            if c < 0x80:
                st.append(c - 64)
            elif c == 0x80:
                st.append(struct.unpack_from("<f", b, i)[0]); i += 4
            elif c == 0x81:
                st.append(struct.unpack_from("<d", b, i)[0]); i += 8
            elif c == 0x82:
                st.append(struct.unpack_from("<i", b, i)[0]); i += 4
            elif 0x84 <= c <= 0x8A:
                n = c - 0x84
                args = st[len(st) - n:] if n else []
                del st[len(st) - n:]
                fid = st.pop() if st else None
                st.append(("call", fid, args))
            elif c == 0xA1:
                break
            elif c == 0xA5:
                j = i
                while j + 1 < len(b) and b[j:j + 2] != b"\0\0":
                    j += 2
                st.append(b[i:j].decode("utf-16le", "replace")); i = j + 2
            else:
                st.append(("op", c))
        return st

    def command(self, k):
        o = self.cmds_off + k * 0x18
        bank, cid = struct.unpack_from("<ii", self.d, o)
        aoff, an = self.q(o + 8, 2)
        args = []
        for a in range(an):
            eo, el = self.q(BASE + aoff + a * 0x10, 2)
            ex = self.expr(eo, el)
            args.append(ex[0] if len(ex) == 1 else ex)
        return bank, cid, args

    def commands_at(self, off, n):
        if n <= 0:
            return []
        k0 = (BASE + off - self.cmds_off) // 0x18
        return [self.command(k0 + i) for i in range(n)]

    def states(self):
        """[(indeks, id, [polecenia wejścia], [(wyrażenie warunku, [polecenia po spełnieniu])])]"""
        out = []
        for s in range(self.n["states"]):
            o = self.states_off + s * 0x48
            sid, coff, cn, eoff, en, xoff, xn, woff, wn = self.q(o, 9)
            conds = []
            for c in range(cn):
                po = struct.unpack_from("<q", self.d, BASE + coff + c * 8)[0]          # tablica wskaźników na warunki
                tgt, pc_off, pc_n, sc_off, sc_n, ev_off, ev_len = self.q(BASE + po, 7)
                conds.append((self.expr(ev_off, ev_len), self.commands_at(pc_off, pc_n)))
            out.append((s, sid, self.commands_at(eoff, en), conds))
        return out


def calls(x):
    """Wszystkie wywołania funkcji (fid, argumenty) w wyrażeniu (rekurencyjnie)."""
    out = []
    for v in x if isinstance(x, list) else [x]:
        if isinstance(v, tuple) and v[0] == "call":
            out.append((v[1], v[2]))
            for a in v[2]:
                out += calls(a)
    return out
