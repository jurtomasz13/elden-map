"""Flagi postępu questów ze skryptów rozmów NPC (talk ESD), przy każdej fladze kwestie z tej samej rozmowy.

    python tools/extract/talk_quests.py 223            # TalkID postaci (NpcName 1<ID>00), wypis do konsoli

Rozmowa = grupa stanów w skrypcie. Dla każdej grupy: flagi ustawiane na 1 (polecenie 1/11 SetEventFlag),
flagi sprawdzane w warunkach, kwestie (TalkMsg) i opcje menu (EventTextForTalk), wzięte z argumentów poleceń.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import esd  # noqa: E402
import formats as F  # noqa: E402
import talk_flags as TF  # noqa: E402


def texts():
    """talk: TalkParam id → tekst kwestii (wiersz +0x04 = id w TalkMsg; kolejne wiersze id+1… to dalsze zdania),
    menu: id → opcja menu rozmowy (EventTextForTalk)."""
    import params as P
    r = A.find("/msg/polpl/menu_dlc02.msgbnd.dcx")
    msg, menu = {}, {}
    for _, n, d in F.bnd4(r[1]):
        b = n.split("\\")[-1]
        if b.startswith("TalkMsg") and "Female" not in b:
            msg.update({k: v for k, v in F.fmg(d).items() if v})
        elif b.startswith("EventTextForTalk"):
            menu.update({k: v for k, v in F.fmg(d).items() if v})
    rows = dict(P.rows(P.load_params()["TalkParam"])[0])
    talk = {}
    for rid, row in rows.items():
        mid = struct.unpack_from("<i", row, 4)[0]
        if mid in msg:
            parts, k = [msg[mid]], 1
            while rid + k in rows and k < 4:
                m2 = struct.unpack_from("<i", rows[rid + k], 4)[0]
                if m2 in msg:
                    parts.append(msg[m2])
                k += 1
            talk[rid] = " / ".join(p.replace(chr(10), " ") for p in parts)
    return talk, menu


def ints(x):
    out = []
    for v in x if isinstance(x, list) else [x]:
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            out.append(v)
        elif isinstance(v, list):
            out += ints(v)
        elif isinstance(v, tuple) and v[0] == "call":
            out += ints(v[2])
    return out


def groups(E):
    """indeks stanu → id grupy (rozmowy)"""
    st_of = {}
    for g in range(E.n["groups"]):
        gid, soff, cnt = E.q(E.groups_off + g * 0x20, 3)
        k0 = (esd.BASE + soff - E.states_off) // 0x48
        for k in range(k0, k0 + cnt):
            st_of[k] = gid
    return st_of


def conversations(talk_id, talk, menu):
    """Group id -> flags set to 1, flags checked in conditions, spoken line ids and menu option ids (all variants)."""
    res = {}
    for d in TF.scripts(talk_id).values():
        E = esd.Esd(d)
        gof = groups(E)
        for s, _, entry, conds in E.states():
            g = res.setdefault(gof.get(s), {"sets": set(), "checks": set(), "lines": [], "menu": []})
            for b, i, a in list(entry) + [c for _, pc in conds for c in pc]:
                if (b, i) == (1, 11) and len(a) == 2 and isinstance(a[0], int) and a[1] == 1:
                    g["sets"].add(a[0])
                for x in ints(a):
                    if x in talk and x not in g["lines"]:
                        g["lines"].append(x)
                    elif x in menu and x not in g["menu"]:
                        g["menu"].append(x)
            for ex, _ in conds:
                for _, args in esd.calls(ex):
                    g["checks"] |= {x for x in ints(args) if x >= 1000}
    return res


def analyse(talk_id, talk, menu):
    """Conversations that set flags: the flags with the lines and menu options of the same conversation."""
    return [{"group": gid, "sets": sorted(g["sets"]),
             "lines": [talk[x][:220] for x in g["lines"][:6]], "menu": [menu[x] for x in g["menu"][:4]]}
            for gid, g in conversations(talk_id, talk, menu).items() if g["sets"]]


def state_lines(talk_id, talk, menu, block):
    """NPC block offset (0..19) -> lines of conversations whose conditions check that flag (what the NPC says there)."""
    out = {}
    for g in conversations(talk_id, talk, menu).values():
        for f in g["checks"]:
            if block <= f < block + 20:
                lst = out.setdefault(f - block, [])
                lst += [talk[x][:150] for x in g["lines"] if talk[x][:150] not in lst][:5 - len(lst)]
    return out


if __name__ == "__main__":
    talk, menu = texts()
    for g in analyse(int(sys.argv[1]), talk, menu):
        print(f"\n[{g['group']}] ustawia {g['sets']}")
        for ln in g["menu"]:
            print("   menu:", ln)
        for ln in g["lines"]:
            print("   „" + ln.replace("\n", " ") + "”")
