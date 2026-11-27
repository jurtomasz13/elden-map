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
        mtd = (m["material"] or {}).get("mtd", "")
        albs = textures_of(mtd)
        # costume shader (nomadic merchants c3200): the first albedo is a flat colour palette of the outfit variant,
        # the second a grey fabric pattern; the game multiplies them
        shader = next((s.split("\\")[-1].lower() for s in material_strings(mtd) if s.lower().endswith(".spx")), "")
        costume = len(albs) > 1 and shader.endswith("_costume.spx")
        # fur and shell-fur shaders (C[Fur]*.spx, C[c3200]_Fur, C[Shell]*): colour from the character's own texture,
        # strands (alpha and pattern) from the hair / shell-fur texture or, without one, the other albedo
        fur = len(albs) > 1 and ("fur" in shader or "shell" in shader)
        if fur:
            own = [a for a in albs if a.lower().startswith(chr_id)]
            color = own[0] if own else albs[0]
            strands = next((a for a in albs if re.search("hair|shellfur", a, re.I)), None) or next(a for a in albs if a != color)
            albs = [color, strands]
        files = [write_texture(alb, tex, out) for alb in albs[:2 if costume or fur else 1]]
        tex_file = files[0] if files else None
        nrm_file = write_texture(albedo_of(mtd, "_n.tif"), tex, out)
        meshes.append({"name": name, "tex": tex_file, **({"detail": files[1]} if costume and files[1] else {}),
                       **({"strands": files[1]} if fur and files[1] else {}),
                       **({"normal": nrm_file} if nrm_file else {}), "pos": [c for p in m["pos"] for c in p],
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


def export_parts(parts, out, skin=None, hair=None):
    """parts: lista (ścieżka partsbnd, zbiór ukrytych flag). Meshe '#NN#' z flagą NN ukrytą przez hełm są pomijane.
    Twarz/skóra: albedo z własnego TPF części, mnożone przez kolor skóry z save'a; włosy: kolor włosów (gra barwi je w shaderze)."""
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
            if "_body" in low or "sss" in low:
                continue                                   # reszta ciała (tułów, ręce) — portret to tylko głowa
            if "eyeao" in low or "hairline" in name.lower() or "_alpha" in low:
                continue                                   # nakładki półprzezroczyste (cień oczu, linia włosów) — bez shadera wyglądają jak płaty
            tex_name = None
            if kind == "skin" and f"{part.lower()}_a" in own:
                tex_name = f"{part}_a"
            elif kind == "gear":
                tex_name = albedo_of(mtd)
                if not tex_name and "hair" in low:          # futro/pióropusz hełmu bez albedo: maska z mapy normalnych, kolor neutralny
                    tex_name, kind = albedo_of(mtd, "_n.tif"), "fur"
            elif kind == "hair":
                tex_name = albedo_of(mtd, "_n.tif")       # maska włosów = kanał alfa mapy normalnych (AAT500_PCHair_n)
            dds = (own.get(tex_name.lower()) or find_texture(tex_name, {})) if tex_name else None
            tex_file = None
            if dds:
                tex_file = f"{tex_name}.dds"
                with open(os.path.join(out, tex_file), "wb") as f:
                    f.write(dds)
            n_name = albedo_of(mtd, "_n.tif") if kind == "gear" else None     # relief of helmets and armour
            n_dds = (own.get(n_name.lower()) or find_texture(n_name, {})) if n_name else None
            if n_dds:
                with open(os.path.join(out, f"{n_name}.dds"), "wb") as f:
                    f.write(n_dds)
            e = {"name": f"{part}:{name}", "tex": tex_file, **({"normal": f"{n_name}.dds"} if n_dds else {}), "pos": [c for p in m["pos"] for c in p],
                 "nrm": [round(c, 3) for n in (m["nrm"] or []) for c in n],
                 "uv": [round(c, 4) for u in (m["uv"] or []) for c in u], "tris": [i for t in m["tris"] for i in t]}
            if kind == "skin" and skin:
                e["tint" if tex_file else "color"] = [round(c / 255, 3) for c in skin]
            if kind == "fur" and tex_file:
                e["color"], e["alphaOnly"] = [0.55, 0.47, 0.36], True
            if kind == "hair" and hair:
                e["color"] = [round(c / 255, 3) for c in hair]
                e["alphaOnly"] = True                      # z tekstury tylko alfa (pasma), kolor z save'a
            meshes.append(e)
    with open(os.path.join(out, "model.json"), "w") as f:
        json.dump({"meshes": meshes}, f)
    return len(meshes), sum(1 for m in meshes if m["tex"])
