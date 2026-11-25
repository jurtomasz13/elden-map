"""FLVER2 (Elden Ring, wersja 0x2001A) — modele 3D: meshe, wierzchołki (pozycja, normalna, UV), ściany, materiały.

Układ (zgodny z SoulsFormats FLVER2):
  nagłówek 0x80: +0x0C offset danych, +0x14 liczby: dummy, materiały, kości, meshe, bufory wierzchołków,
                 +0x48 rozmiar indeksu (0 = per faceset), +0x49 unicode, +0x50 facesety, +0x54 layouty, +0x58 tekstury
  potem tablice: dummy (0x40), materiały (0x20), kości (0x80), meshe (0x30), facesety (0x20),
                 bufory wierzchołków (0x20), layouty (0x10), tekstury (0x20)
"""
import struct

SEM_POS, SEM_NORMAL, SEM_UV = 0, 3, 5
# typ -> rozmiar w bajtach
TYPE_SIZE = {0x01: 8, 0x02: 12, 0x03: 16, 0x10: 4, 0x11: 4, 0x12: 4, 0x13: 4, 0x15: 4, 0x16: 8, 0x18: 8, 0x1A: 8, 0x2E: 4, 0x2F: 4, 0xF0: 4}


def _str(d, off, unicode):
    if off <= 0:
        return ""
    if unicode:
        e = off
        while d[e:e + 2] != b"\0\0":
            e += 2
        return d[off:e].decode("utf-16le", "replace")
    return d[off:d.index(b"\0", off)].decode("shift_jis", "replace")


def parse(d):
    assert d[:6] == b"FLVER\0", d[:6]
    data_off = struct.unpack_from("<i", d, 0x0C)[0]
    n_dummy, n_mat, n_bone, n_mesh, n_vb = struct.unpack_from("<5i", d, 0x14)
    idx_size_hdr, unicode = d[0x48], d[0x49]
    n_fs, n_lay, n_tex = struct.unpack_from("<3i", d, 0x50)
    o = 0x80 + n_dummy * 0x40
    mats_off = o; o += n_mat * 0x20
    o += n_bone * 0x80
    mesh_off = o; o += n_mesh * 0x30
    fs_off = o; o += n_fs * 0x20
    vb_off = o; o += n_vb * 0x20
    lay_off = o; o += n_lay * 0x10
    tex_off = o

    textures = []
    for i in range(n_tex):
        path_o, type_o = struct.unpack_from("<ii", d, tex_off + i * 0x20)
        textures.append((_str(d, path_o, unicode), _str(d, type_o, unicode)))
    materials = []
    for i in range(n_mat):
        name_o, mtd_o, tcount, tindex = struct.unpack_from("<4i", d, mats_off + i * 0x20)
        materials.append({"name": _str(d, name_o, unicode), "mtd": _str(d, mtd_o, unicode),
                          "textures": textures[tindex:tindex + tcount]})
    layouts = []
    for i in range(n_lay):
        count, _, _, moff = struct.unpack_from("<4i", d, lay_off + i * 0x10)
        layouts.append([struct.unpack_from("<5i", d, moff + k * 0x14) for k in range(count)])
    vbufs = []
    for i in range(n_vb):
        buf_idx, lay_idx, vsize, vcount, _, _, blen, boff = struct.unpack_from("<8i", d, vb_off + i * 0x20)
        vbufs.append((lay_idx, vsize, vcount, data_off + boff))
    facesets = []
    for i in range(n_fs):
        flags, strip, cull, _u1, _u2, icount, ioff = struct.unpack_from("<IBBBBii", d, fs_off + i * 0x20)
        isize = idx_size_hdr or struct.unpack_from("<i", d, fs_off + i * 0x20 + 0x14)[0] or 16
        if not idx_size_hdr:
            isize = struct.unpack_from("<i", d, fs_off + i * 0x20 + 0x1C)[0] or 16
        facesets.append((flags, strip, icount, data_off + ioff, isize))

    meshes = []
    for i in range(n_mesh):
        mo = mesh_off + i * 0x30
        _dyn, mat_idx = d[mo], struct.unpack_from("<i", d, mo + 4)[0]
        fs_count, fs_idx_off, vb_count, vb_idx_off = struct.unpack_from("<4i", d, mo + 0x20)
        fs_ids = struct.unpack_from(f"<{fs_count}i", d, fs_idx_off)
        vb_ids = struct.unpack_from(f"<{vb_count}i", d, vb_idx_off)
        pos, nrm, uv = None, None, None
        for vb in vb_ids:
            lay_idx, vsize, vcount, boff = vbufs[vb]
            for _unk, soff, typ, sem, idx in layouts[lay_idx]:
                if sem == SEM_POS and typ in (0x02, 0x03) and pos is None:
                    pos = [struct.unpack_from("<3f", d, boff + v * vsize + soff) for v in range(vcount)]
                elif sem == SEM_NORMAL and nrm is None and typ in (0x10, 0x11, 0x13, 0x2F):
                    nrm = [tuple((b - 127) / 127 for b in d[boff + v * vsize + soff:boff + v * vsize + soff + 3]) for v in range(vcount)]
                elif sem == SEM_NORMAL and nrm is None and typ == 0x1A:
                    nrm = [tuple(x / 32767 for x in struct.unpack_from("<3h", d, boff + v * vsize + soff)) for v in range(vcount)]
                elif sem == SEM_UV and uv is None and idx == 0 and typ in (0x15, 0x16):
                    uv = [tuple(x / 2048 for x in struct.unpack_from("<2h", d, boff + v * vsize + soff)) for v in range(vcount)]
                elif sem == SEM_UV and uv is None and idx == 0 and typ == 0x01:
                    uv = [struct.unpack_from("<2f", d, boff + v * vsize + soff) for v in range(vcount)]
        # najdokładniejszy faceset (bez flag LOD / motion blur)
        best = None
        for fid in fs_ids:
            flags, strip, icount, ioff, isize = facesets[fid]
            if flags & 0x83000000:
                continue
            best = (strip, icount, ioff, isize)
            break
        if pos is None or best is None:
            continue
        strip, icount, ioff, isize = best
        fmt = "<%dH" % icount if isize == 16 else "<%dI" % icount
        idx = list(struct.unpack_from(fmt, d, ioff))
        tris = []
        if strip:
            flip = False
            for k in range(len(idx) - 2):
                a, b, c = idx[k:k + 3]
                if 0xFFFF in (a, b, c) or a == b or b == c or a == c:
                    flip = False if 0xFFFF in (a, b, c) else flip
                    continue
                tris.append((a, c, b) if flip else (a, b, c))
                flip = not flip
        else:
            tris = [tuple(idx[k:k + 3]) for k in range(0, len(idx) - 2, 3)]
        meshes.append({"material": materials[mat_idx] if 0 <= mat_idx < len(materials) else None,
                       "pos": pos, "nrm": nrm, "uv": uv, "tris": tris})
    return {"meshes": meshes, "materials": materials}
