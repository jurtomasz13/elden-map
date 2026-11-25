"""Klucze RSA z eldenring.exe i odszyfrowanie nagłówków BHD5 (tylko odczyt plików gry)."""
import base64
import os
import re

import compat

GAME_DIR = compat.find_game_dir()        # ER_GAME_DIR albo automatycznie z bibliotek Steama (Windows / Linux)
ARCHIVES = ["Data0", "Data1", "Data2", "Data3", "DLC"]


def _der_len(b, i):
    n = b[i]; i += 1
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(b[i:i + k], "big"); i += k
    return n, i


def _der_int(b, i):
    assert b[i] == 0x02
    n, i = _der_len(b, i + 1)
    return int.from_bytes(b[i:i + n], "big"), i + n


def parse_rsa_pubkey(pem_body):
    """PKCS#1 RSAPublicKey: SEQUENCE { INTEGER n, INTEGER e }."""
    der = base64.b64decode(b"".join(pem_body.split()))
    assert der[0] == 0x30
    _, i = _der_len(der, 1)
    n, i = _der_int(der, i)
    e, i = _der_int(der, i)
    return n, e


def exe_keys(game_dir=GAME_DIR):
    exe = open(os.path.join(game_dir, "eldenring.exe"), "rb").read()
    return [parse_rsa_pubkey(m.group(1)) for m in
            re.finditer(rb"-----BEGIN RSA PUBLIC KEY-----(.*?)-----END RSA PUBLIC KEY-----", exe, re.S)]


def rsa_decrypt(data, n, e):
    size = (n.bit_length() + 7) // 8
    out = bytearray()
    for off in range(0, len(data) - size + 1, size):
        m = pow(int.from_bytes(data[off:off + size], "big"), e, n)
        out += m.to_bytes(size, "big")[1:]          # bloki wyjściowe mają size-1 bajtów
    return bytes(out)


def decrypt_bhd(name, keys, game_dir=GAME_DIR):
    raw = open(os.path.join(game_dir, name + ".bhd"), "rb").read()
    for n, e in keys:
        size = (n.bit_length() + 7) // 8
        head = rsa_decrypt(raw[:size], n, e)
        if head.startswith(b"BHD5"):
            return rsa_decrypt(raw, n, e)
    raise ValueError(f"żaden klucz nie pasuje do {name}.bhd")
