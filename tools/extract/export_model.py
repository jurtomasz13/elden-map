"""Eksport modelu postaci (chrbnd: FLVER + tekstury z texbnd + materiały MATBIN) do formatu dla renderera.

Użycie: python export_model.py c4340 [c4750 ...]
Wynik: assets/cache/models/<chr>/model.json + tekstury DDS (albedo) obok.
"""
import hashlib
import json
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
    tex = chr_textures(chr_id)
    out = os.path.join(out_root, chr_id if mask is None else f"{chr_id}_{mask:x}")
    os.makedirs(out, exist_ok=True)
    meshes = []
    for i, m in enumerate(model["meshes"]):
        name = (m["material"] or {}).get("name", "")
        flag = _mesh_flag(name)
        if flag is not None and name.startswith("#") and (flag != 0 if mask is None else not mask >> flag & 1):
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
    meshes = []
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
        if not fl:
            continue
        part = os.path.basename(path).split(".")[0].upper()
        for m in flver.parse(fl)["meshes"]:
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
