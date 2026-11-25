"""Kontenery FromSoftware: BND4, BXF4 (BHF4 + BDT), TPF, FMG. Tylko odczyt."""
import struct

from archive import undcx


def _rev8(b):
    return int(f"{b:08b}"[::-1], 2)


def _entry_layouts(fmt, header_size):
    """Format bitów bindera bywa zapisany w odwróconej kolejności — zwraca warianty pasujące do rozmiaru wpisu."""
    out = []
    for f in (fmt, _rev8(fmt)):
        ids, names = bool(f & 0x02), bool(f & 0x04 or f & 0x08)
        long_off, comp = bool(f & 0x10), bool(f & 0x20)
        size = 16 + (8 if comp else 0) + (8 if long_off else 4) + (4 if ids else 0) + (4 if names else 0)
        if size == header_size and (ids, names, long_off, comp) not in out:
            out.append((ids, names, long_off, comp))
    if not out:
        raise ValueError(f"nieznany format bindera {fmt:#x} / {header_size:#x}")
    return out


def _read_entries(hdr, count, entries_off, header_size, fmt, unicode, data_len=None):
    layouts = _entry_layouts(fmt, header_size)
    for layout in layouts:
        ents = _read_entries_with(hdr, count, entries_off, header_size, layout, unicode)
        if data_len is None or all(0 <= off and off + size <= data_len for _, _, off, size, _ in ents):
            return ents
    raise ValueError("żaden wariant formatu bindera nie daje poprawnych offsetów")


def _read_entries_with(hdr, count, entries_off, header_size, layout, unicode):
    ids, names, long_off, comp = layout
    out = []
    for i in range(count):
        o = entries_off + i * header_size
        flags = hdr[o]
        size = struct.unpack_from("<q", hdr, o + 8)[0]
        p = o + 16
        usize = size
        if comp:
            usize = struct.unpack_from("<q", hdr, p)[0]; p += 8
        if long_off:
            off = struct.unpack_from("<q", hdr, p)[0]; p += 8
        else:
            off = struct.unpack_from("<I", hdr, p)[0]; p += 4
        fid = None
        if ids:
            fid = struct.unpack_from("<i", hdr, p)[0]; p += 4
        name = None
        if names:
            no = struct.unpack_from("<I", hdr, p)[0]
            if unicode:
                e = no
                while hdr[e:e + 2] != b"\0\0":
                    e += 2
                name = hdr[no:e].decode("utf-16le")
            else:
                name = hdr[no:hdr.index(b"\0", no)].decode("shift_jis", "replace")
        out.append((fid, name, off, size, flags))
    return out


def bnd4(data):
    """BND4 -> lista (id, nazwa, dane)."""
    data = undcx(data)
    assert data[:4] == b"BND4", data[:4]
    count = struct.unpack_from("<i", data, 0x0C)[0]
    header_size = struct.unpack_from("<q", data, 0x20)[0]
    unicode, fmt = data[0x30], data[0x31]
    ents = _read_entries(data, count, 0x40, header_size, fmt, unicode, len(data))
    return [(fid, name, undcx(data[off:off + size])) for fid, name, off, size, _ in ents]


def bxf4_entries(bhd, bdt_len):
    """Sam spis BXF4: lista (id, nazwa, offset, rozmiar, flagi)."""
    assert bhd[:4] == b"BHF4", bhd[:4]
    count = struct.unpack_from("<i", bhd, 0x0C)[0]
    header_size = struct.unpack_from("<q", bhd, 0x20)[0]
    return _read_entries(bhd, count, 0x40, header_size, bhd[0x31], bhd[0x30], bdt_len)


def bxf4(bhd, bdt):
    """BXF4 (nagłówek .xxxbhd + dane .xxxbdt) -> lista (id, nazwa, dane)."""
    ents = bxf4_entries(bhd, len(bdt))
    return [(fid, name, undcx(bdt[off:off + size])) for fid, name, off, size, _ in ents]


def tpf(data):
    """TPF (PC) -> lista (nazwa, dds_bytes, format)."""
    data = undcx(data)
    assert data[:4] == b"TPF\0", data[:4]
    count = struct.unpack_from("<i", data, 8)[0]
    encoding = data[0x0E]
    out = []
    for i in range(count):
        o = 0x10 + i * 0x14
        off, size, fmt, _typ, _mips, flags1, name_off = struct.unpack_from("<IiBBBBI", data, o)
        if encoding == 1:
            e = name_off
            while data[e:e + 2] != b"\0\0":
                e += 2
            name = data[name_off:e].decode("utf-16le")
        else:
            name = data[name_off:data.index(b"\0", name_off)].decode("shift_jis", "replace")
        out.append((name, undcx(data[off:off + size]), fmt))
    return out


def fmg(data):
    """FMG (wersja 2, Elden Ring) -> {id: tekst}."""
    group_count, string_count = struct.unpack_from("<ii", data, 0x0C)
    str_offsets = struct.unpack_from("<q", data, 0x18)[0]
    out = {}
    for g in range(group_count):
        first_index, first_id, last_id = struct.unpack_from("<iii", data, 0x28 + g * 16)
        for k in range(last_id - first_id + 1):
            so = struct.unpack_from("<q", data, str_offsets + (first_index + k) * 8)[0]
            if so <= 0:
                continue
            e = so
            while data[e:e + 2] != b"\0\0":
                e += 2
            out[first_id + k] = data[so:e].decode("utf-16le")
    return out
