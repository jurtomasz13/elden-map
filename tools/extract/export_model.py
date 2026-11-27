"""Eksport modelu postaci (chrbnd: FLVER + tekstury z texbnd + materiały MATBIN) do formatu dla renderera.

Użycie: python export_model.py c4340 [c4750 ...]
Wynik: assets/cache/models/<chr>/model.json + tekstury DDS (albedo) obok.
"""
import hashlib
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import flver  # noqa: E402
import formats as F  # noqa: E402

_matbins = None
# files that decide how a portrait looks; a change in any of them means every portrait is rendered again
RENDER_FILES = ("export_model.py", "render.mjs", "render_character.py", "flver.py", "dds.mjs")


def renderer_version():
    """Short hash of the rendering code (RENDER_FILES), stored next to portraits to know when they are stale."""
    h = hashlib.md5()
    for f in RENDER_FILES:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f), "rb") as fh:
            h.update(fh.read().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def matbins():
    global _matbins
    if _matbins is None:
        _matbins = {}
        for f in ("allmaterial", "allmaterial_dlc01", "allmaterial_dlc02"):
            r = A.find(f"/material/{f}.matbinbnd.dcx")
            if r:
                for _, n, d in F.bnd4(r[1]):
                    _matbins[n.split("\\")[-1].lower()] = d
    return _matbins


def material_strings(mtd_path):
    """Texts of the material's MATBIN in order (texture paths, shader .spx); [] when the material is unknown."""
    key = re.sub(r"\.(mtd|matxml)$", ".matbin", mtd_path.split("\\")[-1], flags=re.I).lower()
    d = matbins().get(key)
    return [m.group().decode("utf-16le") for m in re.finditer(rb"(?:[\x20-\x7e]\x00){6,}", d)] if d else []


def textures_of(mtd_path, suffix="_a.tif"):
    """Texture names of the material ending with `suffix` (default albedo *_a.tif), in MATBIN order."""
    return [s.split("\\")[-1][:-4] for s in material_strings(mtd_path) if s.lower().endswith(suffix)]


def albedo_of(mtd_path, suffix="_a.tif"):
    """First texture of the material ending with `suffix` (default albedo *_a.tif), or None."""
    return next(iter(textures_of(mtd_path, suffix)), None)


def chr_textures(chr_id):
    """Tekstury z texbnd postaci (najpierw wysoka rozdzielczość), klucz = nazwa bez sufiksu _l."""
    tex = {}
    for suf in ("_h", "_l"):
        t = A.find(f"/chr/{chr_id}{suf}.texbnd.dcx")
        if t:
            for _, _n, tpf in F.bnd4(t[1]):
                for name, dds, _fmt in F.tpf(tpf):
                    tex.setdefault(re.sub(r"_l$", "", name).lower(), dds)
            break
    return tex


_common = None


def common_textures():
    """Wspólne tekstury postaci (AAT..., wspólne ciało) z /parts i /chr/common*."""
    global _common
    if _common is None:
        _common = {}
        for path in ("/parts/common_body.tpf.dcx", "/chr/common_body.tpf.dcx", "/chr/common.tpf.dcx",
                     "/parts/common_body.tpfbnd.dcx"):
            r = A.find(path)
            if r:
                try:
                    for name, dds, _fmt in F.tpf(r[1]):
                        _common.setdefault(name.lower(), dds)
                except Exception:
                    for _, _n, tpf in F.bnd4(r[1]):
                        for name, dds, _fmt in F.tpf(tpf):
                            _common.setdefault(name.lower(), dds)
    return _common


def find_texture(name, own):
    """Albedo z własnego texbnd, z texbnd postaci-wzorca (prefiks cXXXX) albo ze wspólnych tekstur."""
    k = name.lower()
    if k in own:
        return own[k]
    m = re.match(r"(c\d{4})_", k)
    if m:
        other = _chr_cache.setdefault(m.group(1), chr_textures(m.group(1)))
        if k in other:
            return other[k]
    return common_textures().get(k)


_chr_cache = {}


def write_texture(name, own, out):
    """Copy texture `name` (own texbnd, model template or common) as <out>/<name>.dds; file name or None."""
    dds = find_texture(name, own) if name else None
    if not dds:
        return None
    with open(os.path.join(out, f"{name}.dds"), "wb") as f:
        f.write(dds)
    return f"{name}.dds"


# ---------- pose: models are stored in their bind pose (humanoids in a T- or A-pose); the arms are lowered for portraits ----------
ARM_DOWN = math.radians(78)        # angle of the lowered upper arm below the horizontal


def _rot_matrix(axis, a):
    """Row-vector rotation (v' = v @ M) about X, Y or Z, as System.Numerics builds it (FLVER bone transforms)."""
    c, s = math.cos(a), math.sin(a)
    return {"x": ((1, 0, 0), (0, c, s), (0, -s, c)), "y": ((c, 0, -s), (0, 1, 0), (s, 0, c)), "z": ((c, s, 0), (-s, c, 0), (0, 0, 1))}[axis]


def _mat(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _vec(v, m):
    return tuple(sum(v[k] * m[k][j] for k in range(3)) for j in range(3))


def joints(bones):
    """Model-space position of every bone's joint in the bind pose. FLVER local transform (row vectors):
    scale, rotate X, rotate Z, rotate Y, translate; world = local · parent."""
    world = [None] * len(bones)

    def solve(i):
        if world[i] is None:
            b = bones[i]
            rx, ry, rz = b["r"]
            m = _mat(_mat(_mat(((b["s"][0], 0, 0), (0, b["s"][1], 0), (0, 0, b["s"][2])), _rot_matrix("x", rx)), _rot_matrix("z", rz)), _rot_matrix("y", ry))
            if b["parent"] < 0:
                world[i] = (m, tuple(b["t"]))
            else:
                pm, pp = solve(b["parent"])
                world[i] = (_mat(m, pm), tuple(x + y for x, y in zip(_vec(b["t"], pm), pp)))
        return world[i]
    return [solve(i)[1] for i in range(len(bones))]


def _rodrigues(v, k, a):
    """v rotated by angle a about unit axis k."""
    c, s = math.cos(a), math.sin(a)
    kv = k[0] * v[0] + k[1] * v[1] + k[2] * v[2]
    cr = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
    return tuple(v[i] * c + cr[i] * s + k[i] * kv * (1 - c) for i in range(3))


def arm_turns(bones, others=()):
    """Lowering of raised arms (T- or A-pose) for a portrait: {bone name: (pivot, axis, angle)} for every bone under
    L_/R_UpperArm, turning about the shoulder joint so the upper arm points ARM_DOWN below the horizontal. Empty for
    arms already hanging about that low and for skeletons without these bones. `others`: skeletons of the other parts
    of the same figure; a part lists some bones without their parent (the chest part has finger bones at the root,
    the gauntlets have them under the hand), so the hierarchy is joined by bone name."""
    names = {b["name"]: i for i, b in enumerate(bones)}
    parent = {}
    for skel in (bones, *others):
        for b in skel:
            if b["parent"] >= 0:
                parent.setdefault(b["name"], skel[b["parent"]]["name"])
    pos = joints(bones)
    turn = {}
    for side in "LR":
        s, e = names.get(f"{side}_UpperArm"), names.get(f"{side}_Forearm")
        if s is None or e is None:
            continue
        d = tuple(b - a for a, b in zip(pos[s], pos[e]))
        n, h = math.sqrt(sum(x * x for x in d)), math.hypot(d[0], d[2])
        if not n or not h or math.asin(max(-1, min(1, -d[1] / n))) > ARM_DOWN - math.radians(8):
            continue
        out = (d[0] / h, d[2] / h)                 # horizontal direction of the arm
        d = tuple(x / n for x in d)
        target = (out[0] * math.cos(ARM_DOWN), -math.sin(ARM_DOWN), out[1] * math.cos(ARM_DOWN))
        axis = (d[1] * target[2] - d[2] * target[1], d[2] * target[0] - d[0] * target[2], d[0] * target[1] - d[1] * target[0])
        k = math.sqrt(sum(x * x for x in axis))
        if not k:
            continue
        axis, angle = tuple(x / k for x in axis), math.acos(max(-1, min(1, sum(a * b for a, b in zip(d, target)))))
        upper = bones[s]["name"]
        for name in {b["name"] for skel in (bones, *others) for b in skel}:
            j = name
            while j is not None and j != upper:
                j = parent.get(j)
            if j == upper:
                turn[name] = (pos[s], axis, angle)
    return turn


def apply_turns(meshes, bones, turn):
    """Move vertices by the bone turns (arm_turns) weighted by their bone weights (linear blend skinning); bones are
    matched by name, so a part holding only hand bones (gauntlets) follows the arm of the body's skeleton."""
    turn = {i: turn[b["name"]] for i, b in enumerate(bones) if b["name"] in turn}
    if not turn:
        return
    for m in meshes:
        if not m.get("bi") or not m.get("bw"):
            continue
        for v, (bi, bw) in enumerate(zip(m["bi"], m["bw"])):
            if not any(w and b in turn for b, w in zip(bi, bw)):
                continue
            total, p, nr = sum(bw) or 1, [0, 0, 0], [0, 0, 0]
            for b, w in zip(bi, bw):
                if not w:
                    continue
                q, nq = m["pos"][v], m["nrm"][v] if m["nrm"] else None
                if b in turn:
                    pivot, axis, angle = turn[b]
                    q = tuple(x + c for x, c in zip(_rodrigues(tuple(x - c for x, c in zip(q, pivot)), axis, angle), pivot))
                    nq = _rodrigues(nq, axis, angle) if nq else None
                for i in range(3):
                    p[i] += q[i] * w / total
                    if nq:
                        nr[i] += nq[i] * w / total
            m["pos"][v] = tuple(p)
            if m["nrm"]:
                ln = math.sqrt(sum(x * x for x in nr)) or 1
                m["nrm"][v] = tuple(x / ln for x in nr)


def material_layers(mtd, own_prefix):
    """Textures a mesh of material `mtd` is drawn with: {"tex", "detail", "strands", "normal"} (None = absent).
    Costume shader (nomadic merchants c3200): the first albedo is a flat colour palette of the outfit variant, the
    second a grey fabric pattern (`detail`); the game multiplies them. Fur and shell-fur shaders (C[Fur]*.spx,
    C[c3200]_Fur, C[Shell]*): colour from the owner's own texture (name starting with `own_prefix`: chr id or part
    name), `strands` (alpha and pattern) from the hair / shell-fur texture or, without one, the other albedo."""
    albs = textures_of(mtd)
    shader = next((s.split("\\")[-1].lower() for s in material_strings(mtd) if s.lower().endswith(".spx")), "")
    out = {"tex": albs[0] if albs else None, "detail": None, "strands": None, "normal": albedo_of(mtd, "_n.tif")}
    if len(albs) > 1 and shader.endswith("_costume.spx"):
        out["detail"] = albs[1]
    elif len(set(albs)) > 1 and ("fur" in shader or "shell" in shader):
        own = [a for a in albs if a.lower().startswith(own_prefix.lower())]
        out["tex"] = own[0] if own else albs[0]
        out["strands"] = (next((a for a in albs if re.search("hair|shellfur", a, re.I)), None)
                          or next(a for a in albs if a != out["tex"]))
    return out


def export(chr_id, out_root, mask=None):
    """Meshes '#NN#' are model variants: shown when bit NN of the character's display mask is set (NpcParam,
    extract_world.display_mask); without a mask only '#00#'. Output: <out_root>/<chr>[_<mask hex>]/."""
    r = A.find(f"/chr/{chr_id}.chrbnd.dcx")
    if not r:
        raise FileNotFoundError(chr_id)
    fl = next(d for _, n, d in F.bnd4(r[1]) if n.lower().endswith(".flver"))
    model = flver.parse(fl)
    apply_turns(model["meshes"], model["bones"], arm_turns(model["bones"]))
    tex = chr_textures(chr_id)
    out = os.path.join(out_root, chr_id if mask is None else f"{chr_id}_{mask:x}")
    os.makedirs(out, exist_ok=True)
    meshes = []
    for i, m in enumerate(model["meshes"]):
        name = (m["material"] or {}).get("name", "")
        flag = _mesh_flag(name)
        if flag is not None and name.startswith("#") and (flag != 0 if mask is None else not mask >> flag & 1):
            continue
        if "_arts_" in name.lower():               # attack effect geometry (Malenia's 19 m flower, c5840's tongue)
            continue
        files = {k: write_texture(v, tex, out) for k, v in material_layers((m["material"] or {}).get("mtd", ""), chr_id).items()}
        meshes.append({"name": name, "tex": files["tex"], **{k: files[k] for k in ("detail", "strands", "normal") if files[k]},
                       "pos": [c for p in m["pos"] for c in p],
                       "nrm": [round(c, 3) for n in (m["nrm"] or []) for c in n],
                       "uv": [round(c, 4) for u in (m["uv"] or []) for c in u], "tris": [i for t in m["tris"] for i in t]})
    with open(os.path.join(out, "model.json"), "w") as f:
        json.dump({"chr": chr_id, "meshes": meshes}, f)
    return len(meshes), sum(1 for m in meshes if m["tex"])


if __name__ == "__main__":
    root = os.path.join(A.ROOT, "assets", "cache", "models")
    for c in sys.argv[1:]:
        n, t = export(c, root)
        print(c, "meshe", n, "z teksturą", t)


# ---------- części postaci gracza (głowa: twarz, włosy, hełm) ----------
def _mesh_flag(name):
    """Numer flagi ukrycia z nazwy mesha: '#64#HR' -> 64, '#03#' -> 3, '60#_al' -> 60."""
    m = re.match(r"#?(\d{1,2})#", name or "")
    return int(m.group(1)) if m else None


def export_parts(parts, out, skin=None, hair=None, body=False):
    """parts: list of (partsbnd path, hidden flags). Meshes '#NN#' whose flag NN is hidden (by the equipped armour,
    EquipParamProtector) are left out. Face and skin: albedo from the part's own TPF times the skin colour from the
    save; hair: hair colour (the game tints it in the shader); armour: material_layers (fabric pattern, fur strands,
    normal map). body=False is a head portrait: skin meshes of the rest of the body are left out."""
    os.makedirs(out, exist_ok=True)
    loaded = []
    for path, hide in parts:
        r = A.find(path)
        if not r:
            continue
        own, fl = {}, None
        for _, n, d in F.bnd4(r[1]):
            if n.lower().endswith(".tpf"):
                for name, dds, _fmt in F.tpf(d):
                    own[name.lower()] = dds
            elif n.lower().endswith(".flver"):
                fl = d
        if fl:
            loaded.append((os.path.basename(path).split(".")[0].upper(), hide, own, flver.parse(fl)))
    # the arm pose comes from the fullest skeleton (the chest part); gauntlets carry only hand bones
    skeletons = [model["bones"] for *_x, model in loaded]
    turns = max((arm_turns(sk, skeletons) for sk in skeletons), key=len, default={})
    meshes = []
    for part, hide, own, model in loaded:
        apply_turns(model["meshes"], model["bones"], turns)
        for m in model["meshes"]:
            mat = m["material"] or {}
            name, mtd = mat.get("name", ""), mat.get("mtd", "")
            if _mesh_flag(name) in hide:
                continue
            low = mtd.lower()
            kind = "hair" if part.startswith("HR_") and "hair" in low else "skin" if ("_face" in low or "sss" in low or "_body" in low) else "gear"
            if not body and ("_body" in low or "sss" in low):
                continue                                   # the rest of the body (torso, arms): a portrait is the head
            if "eyeao" in low or "hairline" in name.lower() or "_alpha" in low:
                continue                                   # translucent overlays (eye shadow, hairline) look like flaps without the shader
            lay = {"tex": None}
            if kind == "skin":
                lay["tex"] = f"{part}_a" if f"{part.lower()}_a" in own else None
            elif kind == "hair":
                lay["tex"] = albedo_of(mtd, "_n.tif")      # hair mask = alpha of the normal map (AAT500_PCHair_n)
            else:
                lay = material_layers(mtd, part)
                if not lay["tex"] and "hair" in low:       # helmet fur / plume without an albedo: mask from the normal map
                    lay, kind = {"tex": albedo_of(mtd, "_n.tif")}, "fur"
            files = {k: write_texture(v, own, out) for k, v in lay.items()}
            e = {"name": f"{part}:{name}", "tex": files["tex"], **{k: f for k, f in files.items() if k != "tex" and f},
                 "pos": [c for p in m["pos"] for c in p], "nrm": [round(c, 3) for n in (m["nrm"] or []) for c in n],
                 "uv": [round(c, 4) for u in (m["uv"] or []) for c in u], "tris": [i for t in m["tris"] for i in t]}
            if kind == "skin" and skin:
                e["tint" if files["tex"] else "color"] = [round(c / 255, 3) for c in skin]
            if kind == "fur" and files["tex"]:
                e["color"], e["alphaOnly"] = [0.55, 0.47, 0.36], True
            if kind == "hair" and hair:
                e["color"] = [round(c / 255, 3) for c in hair]
                e["alphaOnly"] = True                      # only the alpha (strands) from the texture, colour from the save
            meshes.append(e)
    with open(os.path.join(out, "model.json"), "w") as f:
        json.dump({"meshes": meshes}, f)
    return len(meshes), sum(1 for m in meshes if m["tex"])
