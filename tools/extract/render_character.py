"""Portret postaci gracza: głowa (twarz, włosy) w kolorach z save'a + założony hełm → assets/renders/char_<plik>_<slot>.png.

Użycie: python render_character.py [plik=sl2|co2] [slot]   (bez argumentów: wszystkie postacie)
Dane: FaceData z save'a (tylko odczyt), ekwipunek z backendu (http://127.0.0.1:8765), części z /parts/*.partsbnd.dcx.

FaceData (blok "FACE" w slocie, offsety od magii): +0x0C model twarzy (v → fg_a_01{(v%100)//10}{v%10}, jak w FaceParam), +0x10 model włosów (hr_a_NNNN),
+0xB3 kolor skóry RGB, +0xF6 kolor włosów RGB.
EquipParamProtector: +0xA4 u16 model (hd_m_NNNN), +0x136+NN bajt = ukryj meshe '#NN#' (np. 60–65 = segmenty włosów).
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
    """Postać ludzka (c0000): CharaInitParam (+0x20 hełm, +0x24 zbroja…, +0xA4 wiersz FaceParam) + FaceParam:
    +0x00 model twarzy, +0x01 skóra RGB, +0x3C model włosów, +0x3D włosy RGB."""
    global _npc
    if _npc is None:
        ps = P.load_params()
        _npc = (dict(P.rows(ps["CharaInitParam"])[0]), dict(P.rows(ps["FaceParam"])[0]))
    ci = _npc[0].get(chara_init)
    fp = ci and _npc[1].get(struct.unpack_from("<i", ci, 0xA4)[0])
    if not ci or not fp:
        return None
    return {"head": struct.unpack_from("<i", ci, 0x20)[0], "face": fp[0], "skin": list(fp[1:4]),
            "hair": fp[0x3C], "hair_rgb": list(fp[0x3D:0x40])}


def render_npc(chara_init, png):
    look = npc_look(chara_init)
    if not look:
        return None
    model, hide = helmet(look["head"]) if look["head"] > 0 else (None, set())
    parts = [(face_file(look["face"]), hide), (f"/parts/hr_a_{look['hair']:04d}.partsbnd.dcx", hide)]
    if model:
        parts.append((f"/parts/hd_m_{model:04d}.partsbnd.dcx", set()))
    mdir = os.path.join(A.ROOT, "assets", "cache", "models", f"npc_{chara_init}")
    n, t = E.export_parts(parts, mdir, skin=look["skin"], hair=look["hair_rgb"])
    subprocess.run(["node", os.path.join(HERE, "render.mjs"), mdir, png, "256", "200", "full"], check=True)
    print(f"  npc {chara_init}: twarz {look['face']} włosy {look['hair']} hełm {model} — meshe {n}, z teksturą {t}")
    return png




def helmet(head_id):
    global _prot
    if _prot is None:
        _prot = dict(P.rows(P.load_params()["EquipParamProtector"])[0])
    row = _prot.get(head_id)
    if not row:
        return None, set()
    model = struct.unpack_from("<H", row, 0xA4)[0]
    hide = {i for i in range(96) if row[0x136 + i]}
    return model, hide


def render(file_key, slot, save_path, eq, body_type):
    fd = face_data(save_path, slot)
    if not fd:
        return None
    head = (eq or {}).get("head") or {}
    model, hide = helmet(head.get("id")) if head.get("id") else (None, set())
    bt = body_type.get("name") if isinstance(body_type, dict) else body_type
    sex = "f" if str(bt).upper() == "B" else "m"
    parts = [(face_file(fd["face"]), hide), (f"/parts/hr_a_{fd['hair']:04d}.partsbnd.dcx", hide)]
    if model:
        hp = f"/parts/hd_{sex}_{model:04d}.partsbnd.dcx"
        parts.append((hp if A.find(hp) else f"/parts/hd_m_{model:04d}.partsbnd.dcx", set()))
    mdir = os.path.join(A.ROOT, "assets", "cache", "models", f"char_{file_key}_{slot}")
    n, t = E.export_parts(parts, mdir, skin=fd["skin"], hair=fd["hair_rgb"])
    png = os.path.join(OUT, f"char_{file_key}_{slot}.png")
    subprocess.run(["node", os.path.join(HERE, "render.mjs"), mdir, png, "320", "200", "full"], check=True)
    print(f"  {file_key}:{slot} twarz {fd['face']} włosy {fd['hair']} hełm {model} (ukryte flagi {len(hide)}) — meshe {n}, z teksturą {t}")
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
    main(sys.argv[1:])
