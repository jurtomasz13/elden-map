"""Player character: head portrait (face, hair in the save's colours + helmet) → assets/renders/char_<file>_<slot>.png
and the whole figure in the equipped armour → char_<file>_<slot>_full.png.

Użycie: python render_character.py [plik=sl2|co2] [slot]   (bez argumentów: wszystkie postacie)
Dane: FaceData z save'a (tylko odczyt), ekwipunek z backendu (http://127.0.0.1:8765), części z /parts/*.partsbnd.dcx.

FaceData (blok "FACE" w slocie, offsety od magii): +0x0C model twarzy (v → fg_a_01{(v%100)//10}{v%10}, jak w FaceParam), +0x10 model włosów (hr_a_NNNN),
+0xB3 kolor skóry RGB, +0xF6 kolor włosów RGB.
EquipParamProtector: +0xA4 u16 model (hd_/bd_/am_/lg_ + m/f + NNNN; also the "naked" slots 10000/100000/…),
+0x132+NN bajt = ukryj meshe '#NN#' (np. 60–65 = segmenty włosów).
"""
import json
import os
import struct
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import export_model as E  # noqa: E402
import params as P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
API = "http://127.0.0.1:8765"
OUT = os.path.join(A.ROOT, "assets", "renders")
SLOT0, SLOT_SIZE = 0x300, 0x280010


def api(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.load(r)


def face_data(save_path, slot):
    d = open(save_path, "rb").read()
    s = d[SLOT0 + slot * SLOT_SIZE: SLOT0 + slot * SLOT_SIZE + 0x280000]
    k = s.find(b"FACE")
    if k < 0:
        return None
    f = s[k:k + 0x120]
    face, hair = struct.unpack_from("<II", f, 0x0C)
    return {"face": face, "hair": hair, "skin": list(f[0xB3:0xB6]), "hair_rgb": list(f[0xF6:0xF9])}


def face_file(v):
    """Model twarzy → plik części: 0→fg_a_0100, 20→0120, 101→0101, 151→0151 (tak koduje FaceParam: X·10+Y, +100 wariant)."""
    p = f"/parts/fg_a_01{(v % 100) // 10}{v % 10}.partsbnd.dcx"
    return p if A.find(p) else "/parts/fg_a_0100.partsbnd.dcx"


_prot = None
_npc = None


def npc_look(chara_init):
    """Human character (c0000): CharaInitParam (+0x20/+0x24/+0x28/+0x2C helmet, chest, arms, legs, -1 = none;
    +0xA4 FaceParam row; +0xE4 sex, 0 = female) + FaceParam: +0x00 face model, +0x01 skin RGB, +0x3C hair model,
    +0x3D hair RGB."""
    global _npc
    if _npc is None:
        ps = P.load_params()
        _npc = (dict(P.rows(ps["CharaInitParam"])[0]), dict(P.rows(ps["FaceParam"])[0]))
    ci = _npc[0].get(chara_init)
    fp = ci and _npc[1].get(struct.unpack_from("<i", ci, 0xA4)[0])
    if not ci or not fp:
        return None
    return {"armour": dict(zip((slot for slot, _pre in ARMOUR), struct.unpack_from("<4i", ci, 0x20))),
            "sex": "m" if ci[0xE4] else "f", "face": fp[0], "skin": list(fp[1:4]), "hair": fp[0x3C], "hair_rgb": list(fp[0x3D:0x40])}


def render_npc(chara_init, png):
    """Portrait of a human character: the whole figure in its armour, framed like the other portraits (bust)."""
    look = npc_look(chara_init)
    if not look:
        return None
    parts, model = figure(look["face"], look["hair"], look["armour"], look["sex"], body=True)
    mdir = os.path.join(A.ROOT, "assets", "cache", "models", f"npc_{chara_init}")
    n, t = E.export_parts(parts, mdir, skin=look["skin"], hair=look["hair_rgb"], body=True)
    subprocess.run(["node", os.path.join(HERE, "render.mjs"), mdir, png, "256", "205", "bust"], check=True)
    print(f"  npc {chara_init}: twarz {look['face']} włosy {look['hair']} hełm {model} — meshe {n}, z teksturą {t}")
    return png




ARMOUR = (("head", "hd"), ("chest", "bd"), ("arms", "am"), ("legs", "lg"))     # equipment slot, part file prefix
NAKED = {"chest": 100000, "arms": 200000, "legs": 300000}    # EquipParamProtector rows of an empty slot (bare body)


def protector(pid):
    """(model, hidden mesh flags) of an EquipParamProtector row; (None, set()) without one."""
    global _prot
    if _prot is None:
        _prot = dict(P.rows(P.load_params()["EquipParamProtector"])[0])
    row = _prot.get(pid)
    if not row:
        return None, set()
    # +0x132+NN u8 invisibleFlag_SexVerNN (Paramdex): non-zero hides meshes '#NN#' (1 for both sexes; 2/3, six rows
    # in the whole game, for one sex only; treated as hidden)
    return struct.unpack_from("<H", row, 0xA4)[0], {i for i in range(96) if row[0x132 + i]}


def figure(face, hair, armour, sex, body):
    """Parts of a human figure: [(partsbnd path, hidden flags)] and the helmet model. Head portrait (body=False): face,
    hair and helmet, the helmet's hidden flags applied to face and hair. Whole figure: every armour piece too, and like
    in the game the hidden flags of all pieces apply to every part (a high collar hides the helmet's chainmail)."""
    ids = {slot: pid if (pid or 0) > 0 else NAKED.get(slot) for slot, pid in armour.items()}
    pieces = [(pre, *protector(ids.get(slot))) for slot, pre in ARMOUR if ids.get(slot) and (body or slot == "head")]
    hide = set().union(*(h for _pre, _m, h in pieces))
    own = hide if body else set()
    parts = [(face_file(face), hide), (f"/parts/hr_a_{hair:04d}.partsbnd.dcx", hide)]
    for pre, model, _h in pieces:
        if model:
            path = f"/parts/{pre}_{sex}_{model:04d}.partsbnd.dcx"
            parts.append((path if A.find(path) else f"/parts/{pre}_m_{model:04d}.partsbnd.dcx", own))
    return parts, next((m for pre, m, _h in pieces if pre == "hd"), None)


def render(file_key, slot, save_path, eq, body_type):
    fd = face_data(save_path, slot)
    if not fd:
        return None
    bt = body_type.get("name") if isinstance(body_type, dict) else body_type
    sex = "f" if str(bt).upper() == "B" else "m"
    armour = {k: ((eq or {}).get(k) or {}).get("id") for k, _pre in ARMOUR}
    for body, suffix in ((False, ""), (True, "_full")):
        parts, model = figure(fd["face"], fd["hair"], armour, sex, body)
        mdir = os.path.join(A.ROOT, "assets", "cache", "models", f"char_{file_key}_{slot}{suffix}")
        n, t = E.export_parts(parts, mdir, skin=fd["skin"], hair=fd["hair_rgb"], body=body)
        png = os.path.join(OUT, f"char_{file_key}_{slot}{suffix}.png")
        subprocess.run(["node", os.path.join(HERE, "render.mjs"), mdir, png, "320", "200", "full"], check=True)
        print(f"  {file_key}:{slot}{suffix} twarz {fd['face']} włosy {fd['hair']} hełm {model} — meshe {n}, z teksturą {t}")
    return png


def main(argv):
    chars = api("/api/characters")
    want = (argv[0], int(argv[1])) if len(argv) >= 2 else None
    for f in chars["files"]:
        for c in f["characters"]:
            if want and (f["file"], c["slot"]) != want:
                continue
            st = api(f"/api/state?file={f['file']}&slot={c['slot']}")
            render(f["file"], c["slot"], f["path"], st.get("equipment"), (st.get("character") or {}).get("body_type"))


if __name__ == "__main__":
    if sys.argv[1:] == ["--version"]:              # the backend puts it in the portrait signature (erbackend/portraits.py)
        print(E.renderer_version())
    else:
        main(sys.argv[1:])
