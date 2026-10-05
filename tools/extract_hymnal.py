"""Extract the "Himnario Corazón y Vida" PDF into a JSON lookup keyed by hymn number.

    uv run --with pypdf python tools/extract_hymnal.py <pdf> <out.json>
    uv run --with pypdf python tools/extract_hymnal.py <pdf> --check

PDF page N == hymn N. Pages after the last hymn are indexes (authors, topics,
alphabetical) and are skipped. Parsing mirrors parse_hymn/hymn_title in
~/.claude/skills/ppt/scripts/pptx_deck_builder.py, with two fixes:
  - CHORUS_RE needs a word boundary, so lyric lines starting "Corona..." /
    "Coros celestiales" are not taken as chorus markers.
  - Each "Coro" marker starts its own chorus block ("Coro último.", "Segundo
    coro-", verse-specific choruses) instead of being appended to one list.
Wording is never changed: lines are only stripped of surrounding whitespace.
"""
import json
import re
import sys

from pypdf import PdfReader

VERSE_RE = re.compile(r"^\s*(\d{1,2})(?!\d)[.\-]?\s*(\S.*\S|\S)\s*$")
CHORUS_RE = re.compile(r"^\s*(?:segundo\s+)?coro\b(?:\s+último)?[.,:;\-]*\s*(.*)$", re.IGNORECASE)
CREDIT_RE = re.compile(r"^\s*-\s*\S")  # "-Tr. X." / "- Escogido." credit line
PAGE_NUM_RE = re.compile(r"^\s*\d+\s*$")  # page number, meter line ("144")
# English key and/or Spanish solfege: "Key F. Fa.", "B flat. Si bemol.", "C. minor. Do menor.",
# "De Flat. Re bemol.", "Mi bemol." -- the key runs from the first match to end of line.
KEY_RE = re.compile(
    r"\bKey\b"
    r"|(?:\b(?:[A-Ga-g8]|De)\b\.?\s*)?\b(?i:flat|fiat|sharp|minor)\b"
    r"|\b(?:[A-G]|De)\.?,?\s+(?:Do|Re|Mi|Fa|Sol|La|Si)\b"
    r"|\b(?:Do|Re|Mi|Fa|Sol|La|Lo|Si)\.?\s+(?:bemol|menor|sostenido)\b"
)
SCRIPTURE_RE = re.compile(r"^\S+\.?\s+\d+:\d+")  # "Salmo 143:1." above an unnumbered song
GLUED_CREDIT_RE = re.compile(r"\s{4,}((?:-\s*)?(?:Tr\.\s*)?(?:[A-Z]\.\s*)+[A-Z][a-z].*)$")  # "...Jesús.      S. D. Athans."
NOTE_RE = re.compile(r"^\((?:nota|para el|repít|key)", re.IGNORECASE)  # "(Para el Coro: Key ...)"
GARBLE_RE = re.compile(r"-{3,}|\S\s{3,}\S")  # interleaved voice parts ("res---ca---tar")

PROPER_WORDS = {w.lower(): w for w in [
    "Dios", "Cristo", "Jesús", "Jesus", "Jesucristo", "Señor", "Jehová", "Espíritu",
    "Emmanuel", "Sion", "Sión",
    # added beyond the deck builder's list
    "Maestro", "Salvador", "Redentor", "Rey", "Emanuel", "Belén", "Jerusalén", "Galilea",
]}


def capitalize_first(line):
    for i, ch in enumerate(line):
        if ch.isalpha():
            return line[:i] + ch.upper() + line[i + 1:]
    return line


def is_caps(s):
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


def parse_page(number, raw_text):
    notes = []
    lines = [l.strip() for l in raw_text.splitlines()]
    lines = [l for l in lines if l]
    if not lines or lines[0] != str(number):
        notes.append(f"leading page number {lines[0] if lines else None!r} != {number}")
    lines = [l for l in lines if not PAGE_NUM_RE.match(l)]

    # Header: ALL-CAPS title (may wrap), then meta lines, until verse 1 / chorus.
    title_parts, meta, i = [], [], 0
    while i < len(lines):
        s = lines[i]
        m = VERSE_RE.match(s)
        if (m and m.group(1) == "1") or CHORUS_RE.match(s):
            break
        if is_caps(s) and not meta:
            title_parts.append(s)
        elif title_parts:
            meta.append(s)
        i += 1
    body = lines[i:]
    numbered = bool(body)
    if not numbered:
        # Single-stanza song: meta lines end at the key line; lyrics follow.
        key_idx = next((j for j, s in enumerate(meta) if KEY_RE.search(s)), -1)
        body = [s for s in meta[key_idx + 1:] if not SCRIPTURE_RE.match(s)]
        meta = meta[:key_idx + 1]
        notes.append("no numbered verses; body stored as one unnumbered stanza")

    tune = key = None
    for j, s in enumerate(meta[:2]):
        km = KEY_RE.search(s)
        if km:
            key = s[km.start():].strip()
            before = s[:km.start()].strip().rstrip(",").strip()
            tune = before or (meta[0] if j == 1 else None)
            break
    if tune is None and meta and key is None:
        tune = meta[0]

    title_raw = " ".join(title_parts) or None
    title = None
    if title_raw:
        words = [PROPER_WORDS.get(w, w) for w in title_raw.lower().split()]
        title = capitalize_first(" ".join(words))
    else:
        notes.append("no ALL-CAPS title found")

    # Body: numbered verses and chorus blocks, in print order.
    blocks, credits, target = [], [], None  # blocks: ("verse", n, lines) / ("chorus", None, lines)
    if not numbered:
        blocks.append(("verse", 1, []))
        target = blocks[0][2]
    for s in body:
        g = GLUED_CREDIT_RE.search(s)
        if g:  # OCR glue: credit printed on the same line as the last lyric
            credits.append(g.group(1))
            s = s[:g.start()]
        m, cm = VERSE_RE.match(s), CHORUS_RE.match(s)
        if numbered and m:
            blocks.append(("verse", int(m.group(1)), [m.group(2)]))
            target = blocks[-1][2]
        elif numbered and cm:
            blocks.append(("chorus", None, [cm.group(1)] if cm.group(1) else []))
            target = blocks[-1][2]
        elif CREDIT_RE.match(s):
            credits.append(s)
            target = credits  # unmarked lines after a credit continue it
        else:
            target.append(s)

    verses = [b[2] for b in blocks if b[0] == "verse"]
    choruses = [b[2] for b in blocks if b[0] == "chorus"]
    nums = [b[1] for b in blocks if b[0] == "verse"]
    if numbered and nums != list(range(1, len(nums) + 1)):
        notes.append(f"verse numbers not sequential: {nums}")
    if len(choruses) > 1:
        notes.append(f"{len(choruses)} distinct choruses; order uses chorus2.. after the verse they follow")
    if any(not b for b in verses + choruses):
        notes.append("empty verse or chorus block")
    if any(GARBLE_RE.search(l) for b in verses + choruses for l in b):
        notes.append("line with dashes/wide gaps: likely interleaved voice parts")
    if any(NOTE_RE.match(l) for b in verses + choruses for l in b):
        notes.append("printed performance note inside lyrics")
    if not verses or not any(verses):
        notes.append("no verses parsed; lyrics misplaced (e.g. in chorus), see raw_lines")

    # Natural sung order: after each verse, the chorus printed after it, else the latest one printed before.
    order, current, vi = [], None, 0
    for k, (kind, _, _) in enumerate(blocks):
        if kind != "verse":
            continue
        vi += 1
        order.append(f"v{vi}")
        nxt = blocks[k + 1] if k + 1 < len(blocks) else None
        if nxt and nxt[0] == "chorus":
            current = sum(1 for b in blocks[:k + 2] if b[0] == "chorus")
        if current:
            order.append("chorus" if current == 1 else f"chorus{current}")

    hymn = {
        "number": number,
        "title": title,
        "title_raw": title_raw,
        "tune": tune,
        "key": key,
        "verses": verses,
        "chorus": choruses[0] if choruses else None,
        "order": order,
        "credits": credits,
        "needs_review": bool(notes),
        "review_notes": notes,
    }
    if len(choruses) > 1:
        hymn["choruses"] = choruses
    if notes:
        hymn["raw_lines"] = lines  # page text minus number lines, for the reviewer
    return hymn


def is_index_page(raw_text):
    return sum(1 for l in raw_text.splitlines() if re.search(r"\s\d{1,3}\s*$", l) and not re.match(r"\s*\d", l)) > 5 \
        or "ÍNDICE" in raw_text or "Autores, compositores" in raw_text


def extract(pdf_path):
    pages = [p.extract_text() for p in PdfReader(pdf_path).pages]
    # Hymns run until the first index page; everything after is back matter.
    last = next((n for n, t in enumerate(pages, 1) if is_index_page(t)), len(pages) + 1) - 1
    return {
        "source": "Himnario Corazón y Vida",
        "hymns": {str(n): parse_page(n, pages[n - 1]) for n in range(1, last + 1)},
        "non_hymn_pages": list(range(last + 1, len(pages) + 1)),
    }


def check(data):
    h = data["hymns"]
    for n in ("64", "116", "132"):
        assert h[n]["verses"] and h[n]["chorus"], n
        assert not h[n]["needs_review"], (n, h[n]["review_notes"])
    assert h["64"]["title"] == "Quiero seguir en los pasos del Maestro"
    assert h["64"]["tune"] == "Stepping In the Light" and h["64"]["key"] == "De Flat. Re bemol."
    assert h["64"]["verses"][0][0] == "Quiero seguir en los pasos del Maestro;"
    assert h["64"]["order"][:3] == ["v1", "chorus", "v2"] and len(h["64"]["verses"]) == 4
    assert h["116"]["title_raw"] == "BIENAVENTURADOS LOS DE LIMPIO CORAZÓN"
    assert h["116"]["chorus"][0] == "¡Oh cantemos aleluya!"
    assert h["132"]["chorus"][0] == ":::Fe la victoria es:::"
    assert h["225"]["chorus"][1] == "coronadle Rey de reyes;"  # not a chorus marker
    assert h["44"]["order"][-1] == "chorus2"
    assert h["70"]["verses"][-1][-1] == "vida inmortal allá tendré con Jesús." and not h["70"]["needs_review"]
    assert h["402"]["verses"][-1][-1] == "a cumplir la grande comisión."
    assert len(h) == 412 and data["non_hymn_pages"][0] == 413, len(h)  # pages 413+ are indexes
    print(f"check ok: {len(h)} hymns")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    data = extract(sys.argv[1])
    if sys.argv[2] == "--check":
        check(data)
    else:
        check(data)
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"wrote {sys.argv[2]}")
