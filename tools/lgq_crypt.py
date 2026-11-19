"""Расшифровка/шифрование FTB Quests файлов сборки Linggango (формат LGQ1:).

Алгоритм восстановлен из com.misanthropy.linggango.linggango_tweaks.questguard.QuestCrypt
(мод linggango_tweaks). Ключи выведены из констант мода, поэтому расшифровка и
повторная упаковка полностью совместимы с оригиналом.
"""
import base64
import hashlib
import hmac
import struct
from pathlib import Path

SEED = (1281839467, 564654861, -1640531527, 2135587861)
MAGIC = "LGQ1:"


def _seed_bytes() -> bytes:
    out = bytearray()
    for value in SEED:
        out += struct.pack(">i", value if value < 2**31 else value - 2**32)
    return bytes(out)


KEY = hashlib.sha256(_seed_bytes()).digest()
MAC_KEY = hashlib.sha256(KEY + b"mac").digest()


def _keystream(nonce: bytes, length: int) -> bytes:
    out = bytearray()
    buf = bytearray(nonce) + b"\x00\x00\x00\x00"
    counter = 0
    while len(out) < length:
        buf[len(nonce):len(nonce) + 4] = struct.pack(">I", counter)
        block = hmac.new(KEY, bytes(buf), hashlib.sha256).digest()
        take = min(len(block), length - len(out))
        out += block[:take]
        counter += 1
    return bytes(out)


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def is_encrypted(text: str) -> bool:
    return text.lstrip().startswith(MAGIC)


def decrypt(text: str) -> str:
    """Возвращает расшифрованное содержимое файла квеста."""
    payload = base64.b64decode(text.strip()[len(MAGIC):].strip())
    if len(payload) < 28:
        raise ValueError("payload too short")
    nonce = payload[:12]
    ciphertext = payload[12:-16]
    tag = payload[-16:]
    expected = hmac.new(MAC_KEY, nonce + ciphertext, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(expected, tag):
        raise ValueError("HMAC mismatch: другой ключ или файл повреждён")
    return _xor(ciphertext, _keystream(nonce, len(ciphertext))).decode("utf-8")


def encrypt(text: str) -> str:
    """Шифрует содержимое файла квеста обратно в формат LGQ1:."""
    plaintext = text.encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = _xor(plaintext, _keystream(nonce, len(plaintext)))
    tag = hmac.new(MAC_KEY, nonce + ciphertext, hashlib.sha256).digest()[:16]
    return MAGIC + base64.b64encode(nonce + ciphertext + tag).decode("ascii")


import os  # noqa: E402  (используется в encrypt)


def decrypt_file(path: Path) -> str:
    return decrypt(path.read_text(encoding="utf-8"))


def encrypt_file(path: Path, text: str) -> None:
    path.write_text(encrypt(text), encoding="utf-8")
