"""Ukryte statystyki przedmiotów: liczby z SpEffectParam przypiętego do talizmanu, zbroi i broni.

Wynik: assets/data/item_effects.json: {"talisman:1000": [{"k": "maxHp", "label": "Maks. PŻ", "v": "+6%", "cond": null}, ...]}

Powiązania (przesunięcia w wierszach, układ pól z publicznych definicji parametrów, tu tylko liczby):
  EquipParamAccessory  +0x04 refId, +0x4C..+0x58 residentSpEffectId1–4
  EquipParamProtector  +0x28 / +0x2C / +0x30 residentSpEffectId 1–3
  EquipParamWeapon     +0x50 / +0x54 / +0x58 residentSpEffectId (efekt, gdy broń jest w ręce)
SpEffectParam: efekty pochodne (+0x124 replace, +0x128 cycleOccurrence, +0x12C atkOccurrence, +0x174 accumuOverFire)
oznaczamy jako warunkowe; +0x04 conditionHp > 0 = „przy PŻ ≤ X%”.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import params as P  # noqa: E402

DATA = os.path.join(A.ROOT, "assets", "data")
ELEM = ["fizyczne", "magiczne", "od ognia", "od błyskawic", "święte"]
# zadawane obrażenia: przeciw wrogom (atkEnemyDmgCorrectRate_*), mnożniki ataku (…AttackRate, …AttackPowerRate)
OUT = [(0x2A0, 0x38, 0x48), (0x2A4, 0x3C, 0x4C), (0x2A8, 0x40, 0x50), (0x2AC, 0x44, 0x54), (0x2B0, 0x1DC, 0x1E0)]
# otrzymywane obrażenia: od wrogów (defEnemyDmgCorrectRate_*) i …DamageCutRate
IN = [(0x274, 0x28), (0x278, 0x2C), (0x27C, 0x30), (0x280, 0x34), (0x284, 0x1D0)]
PHYS_SUB = [("cięte", (0x210, 0x220), 0x1C), ("obuchowe", (0x214, 0x224), 0x20), ("kłute", (0x218, 0x228), 0x24)]
RATES = [
    ("maxHp", 0x10, False, "Maks. PŻ"), ("maxFp", 0x14, False, "Maks. PS"), ("maxSt", 0x18, False, "Maks. energia"),
    ("defPhys", 0x68, False, "Obrona fizyczna"), ("defMagic", 0x6C, False, "Obrona magiczna"),
    ("defFire", 0x70, False, "Obrona przed ogniem"), ("defLight", 0x74, False, "Obrona przed błyskawicami"),
    ("defHoly", 0x1D4, False, "Obrona święta"),
    ("poise", 0x1B4, True, "Otrzymywane obrażenia równowagi"),
    ("runes", 0xF4, False, "Runy z pokonanych wrogów"), ("weight", 0xE4, False, "Udźwig"),
    ("stCost", 0x1F4, True, "Zużycie energii"), ("artsCost", 0x2E4, True, "Koszt PS popiołów wojny"),
    ("sorcCost", 0x2E8, True, "Koszt PS czarów"), ("incCost", 0x2F0, True, "Koszt PS inkantacji"),
    ("flaskHp", (0x2F4, 0x304), False, "Leczenie Flaszki Szkarłatnych Łez"),
    ("flaskFp", (0x2FC, 0x308), False, "PS z Flaszki Błękitnych Łez"),
    ("fall", 0xDC, True, "Obrażenia od upadku"),
]
ATTRS = ["Witalność", "Umysł", "Wytrzymałość", None, "Siła", "Zręczność", "Inteligencja", "Wiara", "Tajemność"]   # +0x31E..
RES = [("resPoison", 0x1FC, "Odporność na truciznę"), ("resRot", 0x200, "Odporność na szkarłatną zgniliznę"),
       ("resBleed", 0x204, "Odporność na krwotok"), ("resDeath", 0x208, "Odporność na śmierć"),
       ("resFrost", 0x20C, "Odporność na mróz"), ("resSleep", 0x348, "Odporność na sen"), ("resMad", 0x34C, "Odporność na szaleństwo")]
# rodzaj ataku, którego dotyczy premia (+0x13A, +0x13B, +0x328 magicSubCategoryChange) — z talizmanów o znanym działaniu
SUBCAT = {100: "ataki ładowane", 101: "ataki z wierzchowca", 102: "ataki z wyskoku", 103: "kontry po bloku",
          104: "ostatni cios serii ataków", 105: "strzały i bełty", 113: "strzały i bełty", 118: "strzały i bełty",
          106: "ryki i zionięcia", 116: "ryki i zionięcia", 108: "rzucane garnki", 109: "flakony perfum",
          110: "ładowane czary i inkantacje", 111: "popioły wojny", 112: "popioły wojny"}
STATE = {111: "trafienia krytyczne", 197: "kontrataki", 71: "określone szkoły czarów i inkantacji", 241: "ataki ładowane"}
# warunek wyzwolenia (+0x2B8 invocationConditionsStateChange1)
INVOKE = {379: "gdy w pobliżu wystąpi krwotok", 380: "gdy w pobliżu wystąpi trucizna lub zgnilizna",
          480: "gdy w pobliżu wystąpi sen", 495: "gdy w pobliżu wystąpi szaleństwo"}
CHILD = (0x124, 0x128, 0x12C, 0x174)
LINKS = {"talisman": ("EquipParamAccessory", (0x4C, 0x50, 0x54, 0x58), 0x04),
         "armor": ("EquipParamProtector", (0x28, 0x2C, 0x30), None),
         "weapon": ("EquipParamWeapon", (0x50, 0x54, 0x58), None)}


def f32(r, o): return struct.unpack_from("<f", r, o)[0]
def i32(r, o): return struct.unpack_from("<i", r, o)[0]


def pct(d):
    s = "+" if d > 0 else "−"
    v = abs(d) * 100
    return f"{s}{v:.0f}%" if abs(v - round(v)) < .05 else f"{s}{v:.1f}%"


def mult(r, offs):
    v = 1.0
    for o in (offs if isinstance(offs, tuple) else (offs,)):
        x = f32(r, o)
        if x not in (0.0, 1.0):
            v *= x
    return v


def attack_cond(r):
    """Rodzaj ataku, którego dotyczy premia do obrażeń (None = wszystkie)."""
    subs = [c for c in (r[0x13A], r[0x13B], r[0x328]) if c]
    if subs:
        names = []
        for c in subs:
            n = SUBCAT.get(c)
            if n and n not in names:
                names.append(n)
        return "tylko " + ", ".join(names) if names else "tylko określone ataki (zob. opis)"
    st = r[0x156]
    if st in STATE:
        return "tylko " + STATE[st]
    return None


def effect_lines(r):
    out = []

    def add(key, label, v, good, cond=None):
        ln = {"k": key, "label": label, "v": v, "good": good}
        if cond:
            ln["cond"] = cond
        out.append(ln)

    def elements(prefix, label, vals, bad_when_up, cond=None):
        if all(abs(v - 1) < 1e-4 for v in vals):
            return None
        if all(abs(v - vals[0]) < 1e-4 for v in vals):          # jednakowo dla wszystkich typów
            add(prefix + "All", f"{label} (wszystkie typy)", pct(vals[0] - 1), (vals[0] > 1) != bad_when_up, cond)
            return vals[0]
        for i, v in enumerate(vals):
            if abs(v - 1) >= 1e-4:
                add(prefix + str(i), f"{label} {ELEM[i]}", pct(v - 1), (v > 1) != bad_when_up, cond)
        return None

    cond = attack_cond(r)
    outs = [mult(r, t) for t in OUT]
    elements("atk", "Obrażenia", outs, False, cond)
    allin = elements("cut", "Otrzymywane obrażenia", [mult(r, t) for t in IN], True)
    for name, atk, cut in PHYS_SUB:
        v = mult(r, atk)
        if abs(v - 1) >= 1e-4 and abs(v - outs[0]) >= 1e-4:           # równe „fizycznym” — bez powtórzeń
            add("atk" + name, f"Obrażenia {name}", pct(v - 1), v > 1, cond)
        v = mult(r, cut)
        if abs(v - 1) >= 1e-4 and not (allin and abs(v - allin) < 1e-4):
            add("cut" + name, f"Otrzymywane obrażenia {name}", pct(v - 1), v < 1)
    for key, off, bad_up, label in RATES:
        v = mult(r, off)
        if abs(v - 1) >= 1e-4:
            add(key, label, pct(v - 1), (v > 1) != bad_up)
    for i, name in enumerate(ATTRS):
        n = struct.unpack_from("<b", r, 0x31E + i)[0]
        if name and n:
            add("attr" + str(i), name, f"{n:+d}", n > 0)
    for key, off, label in RES:
        n = i32(r, off)
        if n:
            add(key, label, f"{n:+d}", n > 0)
    drop = f32(r, 0x1F8)
    if drop:
        add("discovery", "Odkrywanie przedmiotów", f"{drop * 100:+.0f}", drop > 0)
    rec = i32(r, 0xB8)
    if rec:
        add("stRegen", "Regeneracja energii", f"{rec:+d}/s", rec > 0)
    iv = f32(r, 0x0C)
    if iv > 0:
        hp, hpr, fp = i32(r, 0xA0), f32(r, 0x9C), i32(r, 0xA8)
        if hp < 0:
            add("hpRegen", "Regeneracja PŻ", f"+{-hp} co {iv:g} s", True)
        if hpr < 0:
            add("hpRegenPct", "Regeneracja PŻ", f"+{-hpr:g}% maks. co {iv:g} s", True)
        if fp < 0:
            add("fpRegen", "Regeneracja PS", f"+{-fp} co {iv:g} s", True)
    return out


def main():
    ps = P.load_params()
    sp = dict(P.rows(ps["SpEffectParam"])[0])
    items = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
    result = {}
    for cat, (pname, offs, ref) in LINKS.items():
        rows = dict(P.rows(ps[pname])[0])
        for it in items:
            if it.get("category") != cat or it["id"] not in rows:
                continue
            r = rows[it["id"]]
            ids = [i32(r, o) for o in offs]
            if ref is not None and not any(i > 0 for i in ids):
                ids = [i32(r, ref)]
            seen, lines = set(), []

            def visit(e, depth, cond):
                if e <= 0 or e in seen or e not in sp or depth > 2:
                    return
                seen.add(e)
                row = sp[e]
                c = cond
                hp = f32(row, 0x04)
                if 0 < hp < 100:
                    c = f"przy PŻ ≤ {hp:g}%"
                hpmin = f32(row, 0x1F0)                              # conditionHpRate: działa od tego % PŻ wzwyż
                if hpmin >= 100:
                    c = "przy pełnym PŻ"
                elif hpmin > 0:
                    c = f"przy PŻ ≥ {hpmin:g}%"
                inv = struct.unpack_from("<h", row, 0x2B8)[0]
                if inv > 0:
                    c = INVOKE.get(inv, "warunkowo")
                for ln in effect_lines(row):
                    if c:
                        ln["cond"] = c + ("; " + ln["cond"] if ln.get("cond") else "")
                    if not any(x["k"] == ln["k"] and x["v"] == ln["v"] and x.get("cond") == ln.get("cond") for x in lines):
                        lines.append(ln)
                for o in CHILD:
                    visit(i32(row, o), depth + 1, c or "warunkowo")

            for e in ids:
                visit(e, 0, None)
            if lines:
                result[f"{cat}:{it['id']}"] = lines
    with open(os.path.join(DATA, "item_effects.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    by = {}
    for k in result:
        by[k.split(":")[0]] = by.get(k.split(":")[0], 0) + 1
    print("ukryte statystyki:", by)


if __name__ == "__main__":
    main()
