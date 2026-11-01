"""Read Steam's local app types; no network or additional VDF dependency.

Appinfo versions 27/28 use inline keys; 29 uses a shared key-string table.
Only installed app records and their common/type value are inspected.
Unknown/new cache versions fall back to narrow system-tool name exclusions.
"""

import re
import struct
from io import BytesIO
from pathlib import Path


def _cstring(stream):
    value = bytearray()
    for _ in range(65536):
        char = stream.read(1)
        if not char:
            raise ValueError("Truncated VDF string")
        if char == b"\0":
            return value.decode("utf-8", errors="replace")
        value.extend(char)
    raise ValueError("Oversized VDF string")


def _common_type(payload, strings=None):
    stream = BytesIO(payload)
    stack = []
    while stream.tell() < len(payload):
        kind = stream.read(1)[0]
        if kind in (8, 11):
            if not stack:
                return None
            stack.pop()
            continue
        if strings is None:
            key = _cstring(stream)
        else:
            index = struct.unpack("<I", stream.read(4))[0]
            if index >= len(strings):
                raise ValueError("Invalid VDF key index")
            key = strings[index]
        if kind == 0:
            stack.append(key)
            if len(stack) > 64:
                raise ValueError("Excessive VDF nesting")
        elif kind == 1:
            value = _cstring(stream)
            if stack == ["appinfo", "common"] and key == "type":
                return value.casefold()
        elif kind in (2, 3, 4, 6):
            stream.seek(4, 1)
        elif kind in (7, 10):
            stream.seek(8, 1)
        else:
            raise ValueError("Unsupported VDF value")
    return None


def app_types(paths, wanted):
    result = {}
    for path in paths:
        try:
            path = Path(path)
            if path.stat().st_size > 128 * 1024 * 1024:
                continue
            data = path.read_bytes()
            magic = struct.unpack_from("<I", data)[0]
            if magic not in (0x07564427, 0x07564428, 0x07564429):
                continue
            strings = None
            offset = 8
            end = len(data)
            if magic == 0x07564429:
                end = struct.unpack_from("<Q", data, 8)[0]
                offset = 16
                if not 16 <= end < len(data) - 4:
                    continue
                count = struct.unpack_from("<I", data, end)[0]
                if count > 1_000_000:
                    continue
                strings = [
                    value.decode("utf-8", errors="replace")
                    for value in data[end + 4 :].split(b"\0", count)[:count]
                ]
            metadata_size = 40 if magic == 0x07564427 else 60
            while offset + 4 <= end:
                appid = struct.unpack_from("<I", data, offset)[0]
                if not appid:
                    break
                size = struct.unpack_from("<I", data, offset + 4)[0]
                next_offset = offset + 8 + size
                if size < metadata_size or next_offset > end:
                    break
                if appid in wanted and appid not in result:
                    try:
                        kind = _common_type(data[offset + 8 + metadata_size : next_offset], strings)
                    except (ValueError, struct.error, IndexError):
                        kind = None
                    if kind:
                        result[appid] = kind
                offset = next_offset
        except (OSError, ValueError, struct.error):
            continue
    return result


def is_game(name, kind=None):
    if kind is not None:
        return kind.casefold() in ("game", "demo")
    # Offline fallback when Steam has no readable metadata. Keep genuine game
    # names containing e.g. "Runtime" or "Proton" elsewhere in their titles.
    return not re.match(
        r"^(?:Steam Linux Runtime\b|Steamworks Common Redistributables$|Proton(?:\s|$)|SteamVR$|Lossless Scaling$|Steamworks SDK\b)",
        name,
        re.I,
    )
