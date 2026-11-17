"""Підготовка завантажених файлів до розпізнавання.

Телефони віддають що завгодно: HEIC з iPhone, повернуті фото (EXIF), 12-мегапіксельні
JPEG, файли без розширення чи з типом application/octet-stream. Тому тип визначаємо за
вмістом (сигнатурою), а будь-яке зображення перекодовуємо в JPEG ≤ 2000 px.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

try:  # HEIC/HEIF (iPhone)
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # pragma: no cover — без бібліотеки HEIC просто не відкриється
    pass

MAX_SIDE = 2000


def sniff(data: bytes) -> str | None:
    """Тип за першими байтами: image | pdf | xlsx | xls | None (невідомо/текст)."""
    head = data[:16]
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG") or head[:6] in (b"GIF87a", b"GIF89a"):
        return "image"
    if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1", b"avif"):
        return "image"
    if head[:2] == b"BM" or head[:4] in (b"II*\x00", b"MM\x00*"):
        return "image"
    if head.startswith(b"PK\x03\x04"):
        return "xlsx"  # zip-контейнер; інші zip (docx) відсіє openpyxl
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    return None


def to_jpeg(data: bytes) -> bytes:
    """Будь-яке зображення → JPEG, повернуте за EXIF, не більше MAX_SIDE по довшій стороні."""
    try:
        im = Image.open(BytesIO(data))
        im = ImageOps.exif_transpose(im)
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("bad image") from e
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.getchannel("A"))
        im = bg
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()
