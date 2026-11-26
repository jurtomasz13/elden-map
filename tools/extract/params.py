"""regulation.bin (parametry gry) i teksty (FMG), tylko do odczytu.

regulation.bin: AES-256-CBC (IV = pierwsze 16 bajtów), potem DCX (ZSTD) -> BND4 z plikami .param.
Klucz jest stały dla Elden Ring (ten sam, którego używają narzędzia społeczności, np. SoulsFormats);
poprawność weryfikujemy po nagłówku 'DCX' po odszyfrowaniu.
"""
import os
import struct

import archive as A
import bhd
import compat
import formats as F

REGULATION_KEY = bytes.fromhex("99BFFC366A6BC8C6F5827D093602D676C42892A01C207FB024D3AF4E493FEF99")


def _aes_cbc_decrypt(key, iv, data):
    return compat.aes_cbc_decrypt(key, iv, data)


def load_params():
    """{nazwa_parametru: bajty .param}."""
    raw = open(os.path.join(bhd.GAME_DIR, "regulation.bin"), "rb").read()
    dec = _aes_cbc_decrypt(REGULATION_KEY, raw[:16], raw[16:])
    assert dec[:4] == b"DCX\0", "zły klucz regulation.bin"
    return {name.split("\\")[-1].removesuffix(".param"): data for _, name, data in F.bnd4(dec)}


def rows(param):
    """PARAM (Elden Ring, 64-bit): -> lista (id, bajty_wiersza)."""
    count = struct.unpack_from("<H", param, 0x0A)[0]
    heads = [struct.unpack_from("<iiq", param, 0x40 + i * 24)[0::2] for i in range(count)]
    offs = sorted({o for _, o in heads})
    size = (offs[1] - offs[0]) if len(offs) > 1 else 0
    return [(rid, param[o:o + size]) for rid, o in heads], size


def load_texts(lang="polpl"):
    """{nazwa_fmg: {id: tekst}} z item.msgbnd + DLC."""
    out = {}
    for f in ("item", "item_dlc01", "item_dlc02"):
        r = A.find(f"/msg/{lang}/{f}.msgbnd.dcx")
        if not r:
            continue
        for _, name, data in F.bnd4(r[1]):
            key = name.split("\\")[-1].removesuffix(".fmg")
            out.setdefault(key, {}).update({k: v for k, v in F.fmg(data).items() if v})
    return out
