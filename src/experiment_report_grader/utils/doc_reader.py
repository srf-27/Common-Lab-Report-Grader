"""checked"""
"""老式 Word 97-2003（.doc）正文与内嵌图片提取，仅用标准库。

.doc 是 OLE2 复合文档：正文存在 WordDocument 流的文本片段里，
片段表（piece table）在 0Table/1Table 流中，记录每段的编码与位置。
图片原始字节存在 Data 流的图形结构里，按图片自身的格式长度切出。
"""

import struct

_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_FREESECT = (0xFFFFFFFE, 0xFFFFFFFF)


def read_doc(filepath):
    """返回 (正文文本, [(扩展名, 图片字节)])，不保留表格与排版。"""
    try:
        with open(filepath, "rb") as f:
            streams = _ole_streams(f.read())
        word = streams.get("WordDocument")
        if not word:
            raise ValueError("缺少 WordDocument 流")
        return _decode_pieces(word, streams), _find_images(streams)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"无法解析 .doc 结构：{e}") from e


def _find_images(streams):
    images = []
    seen = set()
    for name in ("Data", "WordDocument"):
        data = streams.get(name) or b""
        for signature, read_image in _IMAGE_FORMATS:
            pos = 0
            while True:
                hit = data.find(signature, pos)
                if hit < 0:
                    break
                pos = hit + 1
                image = read_image(data, hit)
                if image and image[1] not in seen:
                    seen.add(image[1])
                    images.append(image)
    return images


def _read_png(data, hit):
    end = data.find(b"IEND", hit)
    return ("png", data[hit:end + 8]) if end >= 0 else None


def _read_jpeg(data, hit):
    pos = hit + 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            return None
        marker = data[pos + 1]
        if marker == 0xDA:
            end = data.find(b"\xff\xd9", pos)
            return ("jpg", data[hit:end + 2]) if end >= 0 else None
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            pos += 2
        else:
            pos += 2 + int.from_bytes(data[pos + 2:pos + 4], "big")
    return None


def _read_emf(data, hit):
    start = hit - 40
    size = int.from_bytes(data[hit + 8:hit + 12], "little")
    return ("emf", data[start:start + size]) if start >= 0 and size > 88 else None


def _read_wmf(data, hit):
    size = 22 + int.from_bytes(data[hit + 28:hit + 32], "little") * 2
    return ("wmf", data[hit:hit + size]) if size > 22 else None


# 签名 -> 切图函数（EMF 的签名在头部偏移 40 处，故回退 40 字节取起点）
_IMAGE_FORMATS = (
    (b"\x89PNG\r\n\x1a\n", _read_png),
    (b"\xff\xd8\xff", _read_jpeg),
    (b" EMF", _read_emf),
    (b"\xd7\xcd\xc6\x9a", _read_wmf),
)


def _decode_pieces(word, streams):
    flags = struct.unpack_from("<H", word, 0x0A)[0]
    table = streams.get("1Table" if flags & 0x0200 else "0Table") or b""
    fc_clx, lcb_clx = struct.unpack_from("<II", word, 0x01A2)
    clx = table[fc_clx:fc_clx + lcb_clx]
    pos = 0
    while pos < len(clx) and clx[pos] == 0x01:
        pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
    if pos >= len(clx) or clx[pos] != 0x02:
        raise ValueError("缺少文本片段表")
    lcb = struct.unpack_from("<I", clx, pos + 1)[0]
    plc = clx[pos + 5:pos + 5 + lcb]
    pieces = (lcb - 4) // 12
    cps = struct.unpack_from("<%dI" % (pieces + 1), plc, 0)
    chunks = []
    for i in range(pieces):
        fc = struct.unpack_from("<I", plc, 4 * (pieces + 1) + 8 * i + 2)[0]
        length = cps[i + 1] - cps[i]
        if fc & 0x40000000:
            start = (fc & 0x3FFFFFFF) // 2
            chunks.append(_decode_ansi(word[start:start + length]))
        else:
            chunks.append(word[fc:fc + length * 2].decode("utf-16-le", "replace"))
    text = "".join(chunks).replace("\r", "\n")
    return "".join(c for c in text if c == "\n" or c >= " ")


def _decode_ansi(chunk):
    try:
        return chunk.decode("cp936")
    except UnicodeDecodeError:
        return chunk.decode("cp1252", "replace")


def _ole_streams(data):
    if data[:8] != _OLE_SIGNATURE:
        raise ValueError("不是 OLE2 复合文档")
    sector_size = 1 << struct.unpack_from("<H", data, 0x1E)[0]
    mini_size = 1 << struct.unpack_from("<H", data, 0x20)[0]
    num_fat = struct.unpack_from("<I", data, 0x2C)[0]
    dir_start = struct.unpack_from("<I", data, 0x30)[0]
    mini_cutoff = struct.unpack_from("<I", data, 0x38)[0]
    mini_fat_start = struct.unpack_from("<I", data, 0x3C)[0]
    difat_start = struct.unpack_from("<I", data, 0x44)[0]
    num_difat = struct.unpack_from("<I", data, 0x48)[0]
    difat = list(struct.unpack_from("<109I", data, 0x4C))
    while difat_start not in _FREESECT and num_difat:
        entries = struct.unpack("<%dI" % (sector_size // 4),
                                _sector(data, difat_start, sector_size))
        difat.extend(entries[:-1])
        difat_start, num_difat = entries[-1], num_difat - 1
    fat = []
    for sector in difat[:num_fat]:
        fat.extend(struct.unpack("<%dI" % (sector_size // 4),
                                 _sector(data, sector, sector_size)))

    def read(start, size, table, unit=None, blob=None):
        chain = []
        while start not in _FREESECT and len(chain) < 1 << 20:
            chain.append(start)
            start = table[start]
        if blob is None:
            buf = b"".join(_sector(data, s, sector_size) for s in chain)
        else:
            buf = b"".join(blob[unit * s:unit * (s + 1)] for s in chain)
        return buf if size is None else buf[:size]

    directory = read(dir_start, None, fat)
    entries = {}
    root = (0, 0)
    for i in range(len(directory) // 128):
        entry = directory[i * 128:(i + 1) * 128]
        name_length = struct.unpack_from("<H", entry, 0x40)[0]
        if name_length < 2:
            continue
        name = entry[:name_length - 2].decode("utf-16-le", "replace")
        start, size = struct.unpack_from("<II", entry, 0x74)
        if entry[0x42] == 5:
            root = (start, size)
        elif entry[0x42] == 2:
            entries[name] = (start, size)

    mini_fat_data = read(mini_fat_start, None, fat)
    mini_fat = list(struct.unpack("<%dI" % (len(mini_fat_data) // 4), mini_fat_data))
    mini_stream = read(root[0], root[1], fat)
    streams = {}
    for name, (start, size) in entries.items():
        if size >= mini_cutoff:
            streams[name] = read(start, size, fat)
        else:
            streams[name] = read(start, size, mini_fat, mini_size, mini_stream)
    return streams


def _sector(data, index, sector_size):
    return data[(index + 1) * sector_size:(index + 2) * sector_size]
