"""Reina-Valera 1960 passages from data/rvr1960.json (tools/extract_bible.py).

passage_chunks("Salmos", "63:1-3") returns the scripture op's `chunks`: one list per
slide, each verse as its number, its lines, then a blank line between verses
-- the layout the operator uses (SEPTIEMBRE 6, slides 63-66).
"""
import json
import math
import re
import unicodedata
from functools import cache
from pathlib import Path

BIBLE = Path(__file__).resolve().parent.parent / "data" / "rvr1960.json"
SLIDE_LINES = 6     # Salmos 63:1-2 (4 + 2 lines) share a slide; adding verse 3 doesn't fit
CHARS_PER_LINE = 45  # ponytail: rough wrap estimate for the verse font; tune if prose spills
RANGE_RE = re.compile(r"^(\d+):(\d+)(?:-(\d+))?$")
ALIASES = {"salmo": "salmos", "cantar de los cantares": "cantares", "eclesiastico": "eclesiastes",
           "apocalipsis de juan": "apocalipsis", "hechos de los apostoles": "hechos"}


def norm(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"^(san|santo|s)\s+", "", " ".join(text.split()))  # "San Juan", "S. Mateo"
    return ALIASES.get(text, text)


@cache
def load(path=BIBLE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    by_name = {norm(b["name"]): code for code, b in data["books"].items()}
    return data["books"], by_name


def verses(book, rng, path=BIBLE):
    """[(number, [lines])] for 'Libro' + 'cap:v' or 'cap:v1-v2'."""
    books, by_name = load(path)
    code = by_name.get(norm(book))
    if code is None:
        raise KeyError(f"no conozco el libro {book!r}")
    m = RANGE_RE.match(rng.replace(" ", "").replace("–", "-"))
    if not m:
        raise KeyError(f"rango {rng!r}: usa cap:v o cap:v1-v2 (dentro de un capítulo)")
    chapter, first = m.group(1), int(m.group(2))
    last = int(m.group(3) or first)
    text = books[code]["chapters"].get(chapter)
    if text is None or first > last or str(first) not in text or str(last) not in text:
        raise KeyError(f"{book} {rng} no existe en RVR1960")
    return [(n, text[str(n)]) for n in range(first, last + 1) if str(n) in text]


def passage_chunks(book, rng, path=BIBLE):
    chunks, current, used = [], [], 0
    for n, lines in verses(book, rng, path):
        cost = sum(math.ceil(len(line) / CHARS_PER_LINE) for line in lines)
        if current and used + cost > SLIDE_LINES:
            chunks.append(current)
            current, used = [], 0
        current += ([""] if current else []) + [str(n), *lines]
        used += cost
    return [*chunks, current]
