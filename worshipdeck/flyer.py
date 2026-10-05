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

Lines OCR read poorly (low confidence) or that match nothing are put to a
person with a crop of that part of the flyer (see parse_flyer_text's `ask`).

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
BOOKS = ["genesis", "exodo", "levitico", "numeros", "deuteronomio", "josue", "jueces", "rut", "samuel", "reyes", "cronicas", "esdras", "nehemias", "ester", "job", "salmos", "salmo", "proverbios", "eclesiastes", "cantares", "isaias", "jeremias", "lamentaciones", "ezequiel", "daniel", "oseas", "joel", "amos", "abdias", "jonas", "miqueas", "nahum", "habacuc", "sofonias", "hageo", "zacarias", "malaquias", "mateo", "marcos", "lucas", "juan", "hechos", "romanos", "corintios", "galatas", "efesios", "filipenses", "colosenses", "tesalonicenses", "timoteo", "tito", "filemon", "hebreos", "santiago", "pedro", "judas", "apocalipsis"]
MONTHS = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
          "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
SCRIPTURE_TODO = "[pegar texto RV1960]"


MIN_CONF = 60  # tesseract word confidence (0-100); a line below this is asked about


def tesseract(image_path, lang, *extra):
    if not shutil.which("tesseract"):
        raise SystemExit("tesseract not found: brew install tesseract (plus spa.traineddata)")
    run = subprocess.run(["tesseract", str(image_path), "stdout", "-l", lang, *extra],
                         capture_output=True, text=True, check=False)
    if run.returncode != 0:
        raise SystemExit(f"tesseract failed: {run.stderr.strip()}")
    return run.stdout


def ocr(image_path, lang="spa"):
    return "\n".join(line["text"] for line in ocr_lines(image_path, lang))


def ocr_lines(image_path, lang="spa"):
    """[{"text", "conf", "box": (left, top, right, bottom)}] per printed line, from
    tesseract's TSV, top to bottom. conf is the line's weakest word, so one
    garbled number ("Himno 6?") marks the whole line. Bands of ink tesseract
    returned nothing for come back as {"text": "", "conf": 0} so they get asked
    about too, instead of silently vanishing."""
    lines = lines_from_tsv(tesseract(image_path, lang, "-c", "tessedit_create_tsv=1"))
    unread = [{"text": "", "conf": 0, "box": b} for b in unread_bands(image_path, [l["box"] for l in lines])]
    return sorted(lines + unread, key=lambda l: l["box"][1])


def unread_bands(image_path, boxes, diff=20, min_h=12, gap=8):
    """Horizontal bands with ink (pixels far from the background) that no OCR box covers."""
    # ponytail: row-profile heuristic on a flat background; a photo background makes
    # bands taller than a quarter of the image, which are skipped. Swap for a text
    # detector (EAST/CRAFT) if flyers move to busy photos.
    from PIL import Image, ImageStat
    with Image.open(image_path) as img:
        g = img.convert("L")
    w, h = g.size
    px = g.load()
    bg = ImageStat.Stat(g).median[0]
    rows = [sum(abs(px[x, y] - bg) > diff for x in range(0, w, 2)) > w // 400 for y in range(h)]
    bands, start, last = [], None, -gap
    for y, ink in enumerate(rows + [False] * gap):
        if ink:
            start = y if start is None or y - last > gap else start
            last = y
        elif start is not None and y - last > gap:
            bands.append((start, last + 1))
            start = None
    out = []
    for top, bottom in bands:
        if bottom - top < min_h or bottom - top > h // 4:
            continue
        covered = sum(max(0, min(bottom, b[3]) - max(top, b[1])) for b in boxes)
        if covered >= (bottom - top) / 2:
            continue
        cols = [x for x in range(0, w, 2) if any(abs(px[x, y] - bg) > diff for y in range(top, bottom, 2))]
        if cols:
            out.append((cols[0], top, cols[-1] + 2, bottom))
    return out


def lines_from_tsv(tsv):
    lines = {}
    rows = tsv.splitlines()
    header = rows[0].split("\t")
    for row in rows[1:]:
        r = dict(zip(header, row.split("\t"), strict=False))  # empty text field may be cut
        if r.get("level") != "5" or not r.get("text", "").strip():
            continue
        key = (r["page_num"], r["block_num"], r["par_num"], r["line_num"])
        left, top = int(r["left"]), int(r["top"])
        box = (left, top, left + int(r["width"]), top + int(r["height"]))
        line = lines.setdefault(key, {"words": [], "conf": 100.0, "box": box})
        line["words"].append(r["text"])
        line["conf"] = min(line["conf"], float(r["conf"]))
        b = line["box"]
        line["box"] = (min(b[0], box[0]), min(b[1], box[1]), max(b[2], box[2]), max(b[3], box[3]))
    return [{"text": " ".join(l["words"]), "conf": round(l["conf"]), "box": l["box"]}
            for l in lines.values()]


def crop_line(image_path, box, dest, pad=12):
    """Save the flyer region of one OCR line so a person can read what OCR couldn't."""
    from PIL import Image
    with Image.open(image_path) as img:
        l, t, r, b = box
        img.crop((max(l - pad, 0), max(t - pad, 0), min(r + pad, img.width), min(b + pad, img.height))).save(dest)
    return str(dest)


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


def clean(text):
    return text.strip(" \t-•*·|")


def classify(line, hymn_titles, hymn_numbers, song_titles):
    """Spec items for one flyer line, or [] when nothing matches."""
    m = HYMN_RE.search(line)
    if m:
        n = int(m.group(1) or m.group(2))
        if not hymn_numbers or n in hymn_numbers:
            return [{"op": "hymn", "himno": n}]
    refs = scripture_items(line)
    if refs:
        return refs
    key = best_match(line, song_titles)
    if key:
        return [{"op": "song", "key": key}]
    n = best_match(line, hymn_titles, cutoff=0.9)
    return [{"op": "hymn", "himno": n}] if n else []


def parse_flyer_text(lines, hymnal_path=DEFAULT_HYMNAL, library=None, ask=None):
    """(items, pendientes): spec items in flyer order, and the lines left unresolved.

    `lines` is raw text or ocr_lines() records. A line is doubtful when OCR
    confidence is under MIN_CONF or nothing matches it. With `ask`, each
    doubtful line is put to a person: ask(record, text, items) returns the
    corrected text (re-checked right away), "" to keep it as is, or None to
    drop it (church name, date, decoration). Unmatched lines and, without
    `ask`, shaky matches (kept in items) go to pendientes."""
    if isinstance(lines, str):
        lines = [{"text": t, "conf": 100} for t in lines.splitlines()]
    hymn_titles, hymn_numbers = load_hymn_titles(hymnal_path)
    song_titles = library_titles(library or {})
    items, pendientes = [], []
    for rec in lines:
        line, conf = clean(rec["text"]), rec.get("conf", 100)
        if conf and sum(c.isalpha() for c in line) < 3 and not HYMN_RE.search(line):
            continue
        found = classify(line, hymn_titles, hymn_numbers, song_titles)
        while ask and (conf < MIN_CONF or not found):
            answer = ask(rec, line, found)
            if answer is None:
                line, found = None, []
                break
            if not answer.strip():
                conf = 100  # a person looked at it: no longer doubtful, even if unmatched
                break
            line, conf = clean(answer), 100
            found = classify(line, hymn_titles, hymn_numbers, song_titles)
        if line is None:
            continue
        items.extend(found)
        if conf < MIN_CONF or not found:
            pendientes.append(line if "box" not in rec else {**rec, "text": line, "matched": bool(found)})
    return items, pendientes


def next_sunday_name(today=None):
    """'OCTUBRE 11.pptx' -- the church names each deck after its Sunday."""
    today = today or datetime.date.today()
    sunday = today + datetime.timedelta(days=(6 - today.weekday()) % 7)
    return f"{MONTHS[sunday.month - 1]} {sunday.day}.pptx"


def make_spec(lines, output=None, sermon_title=None, sermon_lead="El tema de hoy",
              passage=None, hymnal=None, library=None, ask=None):
    hymnal = hymnal or DEFAULT_HYMNAL
    lib_path = library or (str(DEFAULT_LIBRARY) if DEFAULT_LIBRARY.exists() else None)
    items, pendientes = parse_flyer_text(lines, hymnal, load_library(lib_path), ask)
    spec = {"output": output or next_sunday_name(),
            "items": [{"op": "clone_range", "start": 1, "end": 3}, *items]}
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
    for p in spec.get("_pendientes", []):
        if isinstance(p, str):
            out.append(f"sin match: {p!r} (si es una canción, agrégala con `worshipdeck song add`)")
        else:
            what = ("texto que el OCR no leyó" if not p["text"] else
                    "leído con baja confianza" if p["matched"] else "sin match")
            out.append(f"{what} ({p['conf']}%): {p['text']!r} -> mira {p.get('crop', 'la imagen')}")
    return out
