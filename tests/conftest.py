"""Shared fixtures. Tests are grouped by Testing Trophy level (see tests/README.md):
unit/ (pure functions), integration/ (real data and tools), e2e/ (the CLI as a user runs it)."""
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[1]
REAL_TEMPLATE = REPO / "reference" / "style-template.pptx"
REAL_HYMNAL = REPO / "data" / "hymnal.json"
REAL_HYMNAL_PDF = REPO / "reference" / "hymnal.pdf"
FLYER = REPO / "examples" / "flyer.example.png"

needs_tesseract = pytest.mark.skipif(
    not shutil.which("tesseract"), reason="tesseract not installed")
needs_soffice = pytest.mark.skipif(
    not shutil.which("soffice"), reason="LibreOffice (soffice) not installed")


def pytest_collection_modifyitems(items):
    for item in items:
        level = Path(item.fspath).parent.name
        if level in ("integration", "e2e"):
            item.add_marker(getattr(pytest.mark, level))


@pytest.fixture(scope="session")
def library():
    from worshipdeck.builder import DEFAULT_LIBRARY_DIR, load_library
    return load_library(None, DEFAULT_LIBRARY_DIR)


def draw_flyer(path, lines, blurred=()):
    """A flat-background flyer like the church's: one text line per entry.
    Lines in `blurred` are drawn faint and blurred so OCR can't read them."""
    font = ImageFont.load_default(size=56)
    img = Image.new("RGB", (1080, 140 + 140 * len(lines)), (32, 48, 70))
    for i, text in enumerate(lines):
        y = 60 + 140 * i
        if text in blurred:
            band = Image.new("RGB", (900, 110), (32, 48, 70))
            ImageDraw.Draw(band).text((0, 10), text, fill=(110, 115, 120), font=font)
            img.paste(band.filter(ImageFilter.GaussianBlur(9)), (80, y))
        else:
            ImageDraw.Draw(img).text((80, y), text, fill=(245, 235, 210), font=font)
    img.save(path)
    return path
