"""Shrink the images inside a template .pptx so built decks fit Vercel's 4.5 MB response limit.

Every image in ppt/media/ is scaled down to MAX_WIDTH (projectors show 1920 px), JPEGs are
re-encoded at QUALITY, PNGs stay PNG (the logo keeps its transparency). Formats, file names
and every other part of the package are copied byte for byte, so the slides don't change.

  uv run python tools/compress_template.py reference/style-template.pptx
"""
import io
import sys
import zipfile
from pathlib import Path

from PIL import Image

MAX_WIDTH = 2048
QUALITY = 82


def shrink(data, name):
    img = Image.open(io.BytesIO(data))
    fmt = img.format
    if img.width > MAX_WIDTH:
        img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS)
    out = io.BytesIO()
    if fmt == "JPEG":
        img.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    else:
        img.save(out, fmt, optimize=True)
    return out.getvalue() if out.tell() < len(data) else data  # never grow a file


def compress(path):
    path = Path(path)
    src = zipfile.ZipFile(path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename.startswith("ppt/media/") and info.filename.lower().endswith((".jpeg", ".jpg", ".png")):
                data = shrink(data, info.filename)
            dst.writestr(info, data, compress_type=info.compress_type)
    before = path.stat().st_size
    path.write_bytes(buf.getvalue())
    return before, path.stat().st_size


if __name__ == "__main__":
    for p in sys.argv[1:]:
        before, after = compress(p)
        print(f"{p}: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB")
