"""Извлечение и замена строк в .class-файлах (Java, формат class v52+).

Зачем: часть описаний предметов в модах (Terramity и др.) зашита в код
(литералы в appendHoverText), а не в lang-файлы. Ресурспак их не может
перекрыть — нужен патч самого jar.

Как это работает:
  * строки лежат в constant pool как UTF8-записи (тег 1);
  * чтобы заменить строку на строку другой длины, нужно пересобрать
    constant pool с обновлёнными длинами — количество и порядок записей
    при этом НЕ меняются, поэтому индексы констант в коде остаются валидными;
  * всё остальное (код методов, атрибуты) копируется как есть.

Проверка: `javap -p -c <класс>` должен разбирать результат без ошибок.
"""

from __future__ import annotations

import struct
from pathlib import Path

# теги constant pool
TAG_UTF8 = 1
TAG_INTEGER = 3
TAG_FLOAT = 4
TAG_LONG = 5
TAG_DOUBLE = 6
TAG_CLASS = 7
TAG_STRING = 8
TAG_FIELDREF = 9
TAG_METHODREF = 10
TAG_INTERFACE_METHODREF = 11
TAG_NAME_AND_TYPE = 12
TAG_METHOD_HANDLE = 15
TAG_METHOD_TYPE = 16
TAG_DYNAMIC = 17
TAG_INVOKE_DYNAMIC = 18
TAG_MODULE = 19
TAG_PACKAGE = 20

# размеры фиксированных записей (в байтах, без учёта тега)
FIXED_SIZE = {
    TAG_INTEGER: 4, TAG_FLOAT: 4, TAG_LONG: 8, TAG_DOUBLE: 8,
    TAG_CLASS: 2, TAG_STRING: 2, TAG_FIELDREF: 4, TAG_METHODREF: 4,
    TAG_INTERFACE_METHODREF: 4, TAG_NAME_AND_TYPE: 4, TAG_METHOD_HANDLE: 3,
    TAG_METHOD_TYPE: 2, TAG_DYNAMIC: 4, TAG_INVOKE_DYNAMIC: 4,
    TAG_MODULE: 2, TAG_PACKAGE: 2,
}


class ClassFile:
    """Разбор/сборка class-файла с доступом к constant pool."""

    def __init__(self, data: bytes):
        self.data = data
        if data[:4] != b"\xca\xfe\xba\xbe":
            raise ValueError("не class-файл")
        self.minor, self.major = struct.unpack_from(">HH", data, 4)
        count = struct.unpack_from(">H", data, 8)[0]
        self.count = count
        self.entries: list[tuple[int, bytes]] = []   # (тег, payload)
        self.slots: list[int] = []                  # индексы длинных записей
        off = 10
        i = 1
        while i < count:
            tag = data[off]
            off += 1
            if tag == TAG_UTF8:
                ln = struct.unpack_from(">H", data, off)[0]
                off += 2
                payload = data[off:off + ln]
                off += ln
            else:
                size = FIXED_SIZE.get(tag)
                if size is None:
                    raise ValueError(f"неизвестный тег constant pool: {tag}")
                payload = data[off:off + size]
                off += size
            self.entries.append((tag, payload))
            if tag in (TAG_LONG, TAG_DOUBLE):
                self.slots.append(len(self.entries))
                self.entries.append((-1, b""))  # placeholder для второго слота
                i += 2
            else:
                i += 1
        self.body = data[off:]

    # ------------------------------------------------------------------
    def utf8_strings(self) -> list[str]:
        out = []
        for tag, payload in self.entries:
            if tag == TAG_UTF8:
                out.append(payload.decode("utf-8", errors="replace"))
        return out

    def set_utf8(self, old: str, new: str) -> int:
        """Заменяет строку в constant pool. Возвращает число замен."""
        changed = 0
        entries = []
        for tag, payload in self.entries:
            if tag == TAG_UTF8:
                cur = payload.decode("utf-8", errors="replace")
                if cur == old:
                    payload = new.encode("utf-8")
                    changed += 1
            entries.append((tag, payload))
        self.entries = entries
        return changed

    def rebuild(self) -> bytes:
        out = bytearray()
        out += b"\xca\xfe\xba\xbe"
        out += struct.pack(">HH", self.minor, self.major)
        out += struct.pack(">H", self.count)
        for tag, payload in self.entries:
            if tag == -1:
                continue
            out.append(tag)
            if tag == TAG_UTF8:
                out += struct.pack(">H", len(payload))
            out += payload
        out += self.body
        return bytes(out)


def patch_class(data: bytes, replacements: dict[str, str]) -> tuple[bytes, int]:
    """Заменяет строки в class-файле. replacements: {старое: новое}."""
    cf = ClassFile(data)
    total = 0
    for old, new in replacements.items():
        if old == new:
            continue
        total += cf.set_utf8(old, new)
    if not total:
        return data, 0
    return cf.rebuild(), total
