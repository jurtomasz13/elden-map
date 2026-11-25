"""Pomocnik dekompresji Oodle Kraken dla Linuxa: uruchamiany przez Wine w Pythonie dla Windows,
ładuje oo2core_6_win64.dll z folderu gry i dekompresuje dane przesyłane przez stdin/stdout.

Protokół (little-endian): żądanie = u32 długość danych, u32 rozmiar po dekompresji, dane;
odpowiedź = i32 liczba bajtów (-1 = błąd), potem dane. Koniec wejścia kończy proces.
Użycie (robi to compat.py):  wine python.exe oodle_helper.py Z:\\…\\oo2core_6_win64.dll
"""
import ctypes
import struct
import sys


def main():
    dll = ctypes.WinDLL(sys.argv[1])
    dec = dll.OodleLZ_Decompress
    dec.restype = ctypes.c_ssize_t
    dec.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_int, ctypes.c_int,
                    ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_ssize_t, ctypes.c_int]
    inp, out = sys.stdin.buffer, sys.stdout.buffer

    def read(n):
        buf = bytearray()
        while len(buf) < n:
            chunk = inp.read(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return bytes(buf)

    while True:
        head = read(8)
        if head is None:
            return
        clen, rlen = struct.unpack("<II", head)
        comp = read(clen)
        if comp is None:
            return
        dst = ctypes.create_string_buffer(rlen + 64)          # Oodle może pisać trochę za końcem bufora
        n = dec(comp, clen, dst, rlen, 1, 0, 0, None, 0, None, None, None, 0, 3)
        if n != rlen:
            out.write(struct.pack("<i", -1))
        else:
            out.write(struct.pack("<i", n))
            out.write(dst.raw[:n])
        out.flush()


if __name__ == "__main__":
    main()
