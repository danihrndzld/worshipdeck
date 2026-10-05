"""Flyer image -> build spec.

The week's flyer lists the alabanzas (hymn numbers and song titles), sometimes
the prédica. OCR gives raw text; parse_flyer_text() turns each line into a
build-spec item:

  "Himno 64", "H. 64", "#64"       -> hymn op (number looked up in the hymnal)
  "Salmos 42:1-2"                  -> scripture op (RV1960 text left to fill in)
  a title in the song library      -> song op by key
  a hymn title without its number  -> hymn op
  anything else                    -> "_pendientes" (church name, date, noise,
                                      or a song still missing from the library)

The OCR step is swappable: the CLI shells out to tesseract, and a web front end
can run tesseract.js in the browser and post the text to the same parser.
"""
import datetime
import difflib
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from worshipdeck.builder import DEFAULT_HYMNAL, DEFAULT_LIBRARY, load_library

HYMN_RE = re.compile(r"\b(?:himno|h\.?)\s*(?:n[o°º.]*\s*)?#?\s*(\d{1,3})\b|^\s*#\s*(\d{1,3})\b", re.IGNORECASE)
REF_RE = re.compile(r"^\s*((?:[1-3]\s*)?[A-Za-zÁÉÍÓÚÜÑáéíóúüñ. ]+?)\s+(\d{1,3}\s*:\s*\d{1,3}(?:\s*[-–]\s*\d{1,3})?)")
MORE_REF_RE = re.compile(r"(\d{1,3}\s*:\s*\d{1,3}(?:\s*[-–]\s*\d{1,3})?)")
BOOKS = """genesis exodo levitico numeros deuteronomio josue jueces rut samuel reyes cronicas
esdras nehemias ester job salmos salmo proverbios eclesiastes cantares isaias jeremias lamentaciones
ezequiel daniel oseas joel amos abdias jonas miqueas nahum habacuc sofonias hageo zacarias malaquias
mateo marcos lucas juan hechos romanos corintios galatas efesios filipenses colosenses
tesalonicenses timoteo tito filemon hebreos santiago pedro judas apocalipsis""".split()
MONTHS = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
          "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
SCRIPTURE_TODO = "[pegar texto RV1960]"


def ocr(image_path, lang="spa"):
    if not shutil.which("tesseract"):
        raise SystemExit("tesseract not found: brew install tesseract (plus spa.traineddata)")
    run = subprocess.run(["tesseract", str(image_path), "stdout", "-l", lang],
                         capture_output=True, text=True)
    if run.returncode != 0:
        raise SystemExit(f"tesseract failed: {run.stderr.strip()}")
    return run.stdout


def norm(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text).split())


def load_hymn_titles(hymnal_path):
    """{normalized title: number} from data/hymnal.json (empty for a PDF hymnal)."""
    if not str(hymnal_path).endswith(".json") or not Path(hymnal_path).exists():
        return {}, set()
    hymns = json.loads(Path(hymnal_path).read_text(encoding="utf-8"))["hymns"]
    return {norm(h["title"]): int(n) for n, h in hymns.items() if h.get("title")}, {int(n) for n in hymns}


def library_titles(library):
    titles = {}
    for key, e in library.items():
        title = e.get("title") or " ".join(filter(None, [e.get("title_white"), e.get("title_cream")]))
        titles[norm(title)] = key
        titles[norm(key.replace("-", " "))] = key
    return titles


def best_match(line, titles, cutoff=0.8):
    n = norm(line)
    if not n:
        return None
    if n in titles:
        return titles[n]
    hit = difflib.get_close_matches(n, titles, n=1, cutoff=cutoff)
    return titles[hit[0]] if hit else None


def scripture_items(line):
    """'Salmos 42:1-2 & 63:1-3' -> two scripture ops for the same book."""
    m = REF_RE.match(line)
    if not m:
        return []
    book = " ".join(m.group(1).split()).strip(" .")
    if not any(w in BOOKS for w in norm(book).split()):  # "Domingo 10:00" is not a passage
        return []
    ranges = MORE_REF_RE.findall(line[m.start(2):])
    return [{"op": "scripture", "book": book, "range": re.sub(r"\s+", "", r).replace("–", "-"),
             "chunks": [[SCRIPTURE_TODO]]} for r in ranges]


def parse_flyer_text(text, hymnal_path=DEFAULT_HYMNAL, library=None):
    """(items, pendientes): spec items in flyer order, and the lines nothing matched."""
    hymn_titles, hymn_numbers = load_hymn_titles(hymnal_path)
    song_titles = library_titles(library or {})
    items, pendientes = [], []
    for raw in text.splitlines():
        line = raw.strip(" \t-•*·|")
        if sum(c.isalpha() for c in line) < 3 and not HYMN_RE.search(line):
            continue
        m = HYMN_RE.search(line)
        if m:
            n = int(m.group(1) or m.group(2))
            if not hymn_numbers or n in hymn_numbers:
                items.append({"op": "hymn", "himno": n})
                continue
        refs = scripture_items(line)
        if refs:
            items.extend(refs)
            continue
        key = best_match(line, song_titles)
        if key:
            items.append({"op": "song", "key": key})
            continue
        n = best_match(line, hymn_titles, cutoff=0.9)
        if n:
            items.append({"op": "hymn", "himno": n})
            continue
        pendientes.append(line)
    return items, pendientes


def next_sunday_name(today=None):
    """'OCTUBRE 11.pptx' -- the church names each deck after its Sunday."""
    today = today or datetime.date.today()
    sunday = today + datetime.timedelta(days=(6 - today.weekday()) % 7)
    return f"{MONTHS[sunday.month - 1]} {sunday.day}.pptx"


def make_spec(text, output=None, sermon_title=None, sermon_lead="El tema de hoy",
              passage=None, hymnal=None, library=None):
    hymnal = hymnal or DEFAULT_HYMNAL
    lib_path = library or (str(DEFAULT_LIBRARY) if DEFAULT_LIBRARY.exists() else None)
    items, pendientes = parse_flyer_text(text, hymnal, load_library(lib_path))
    spec = {"output": output or next_sunday_name(),
            "items": [{"op": "clone_range", "start": 1, "end": 3}] + items}
    if hymnal != DEFAULT_HYMNAL:
        spec["hymnal"] = str(hymnal)
    if library:
        spec["library"] = library
    if sermon_title:
        spec["items"].append({"op": "sermon", "lead": sermon_lead, "title": sermon_title,
                              "reference": passage or ""})
    if passage:
        refs = scripture_items(passage)
        if not refs:
            raise SystemExit(f"Can't read the passage {passage!r}; use 'Libro 1:2-3'")
        spec["items"].extend(refs)
    if pendientes:
        spec["_pendientes"] = pendientes
    return spec


def warnings(spec):
    out = []
    if not any(i["op"] == "sermon" for i in spec["items"]):
        out.append("sin prédica: pasa --sermon-title y --passage (el flyer casi nunca la trae)")
    if any(c == [SCRIPTURE_TODO] for i in spec["items"] if i["op"] == "scripture" for c in i["chunks"]):
        out.append(f"hay pasajes con {SCRIPTURE_TODO}: pega el texto RV1960 en el spec antes de `build`")
    for line in spec.get("_pendientes", []):
        out.append(f"sin match: {line!r} (si es una canción, agrégala con `worshipdeck song add`)")
    return out
