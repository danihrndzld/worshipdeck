"""Compact the RVR1960 JSON from mrk214/bible-data-es-spa into data/rvr1960.json.

The source (23 MB) carries each chapter's HTML; only the verse lines are kept:
{"books": {"PSA": {"name": "Salmos", "chapters": {"42": {"1": [line, ...]}}}}}.
Poetry keeps its printed line breaks, the way the operator sets Salmos on screen.

  curl -sLO https://raw.githubusercontent.com/mrk214/bible-data-es-spa/main/data/es___spa___spa/RVR1960_vid_149.json
  uv run python tools/extract_bible.py RVR1960_vid_149.json data/rvr1960.json
"""
import json
import sys
from pathlib import Path

SOURCE = "https://github.com/mrk214/bible-data-es-spa/blob/main/data/es___spa___spa/RVR1960_vid_149.json"


def compact(src):
    books = {}
    for book in src["books"]:
        chapters = {}
        for ch in book["chapters"]:
            verses = {}
            for item in ch["items"]:
                if item["type"] != "verse":
                    continue
                for n in item["verse_numbers"][:1]:  # a verse split over items is appended
                    verses.setdefault(str(n), []).extend(line.strip() for line in item["lines"] if line.strip())
            if verses:
                chapters[ch["usfm"].split(".")[1]] = verses
        books[book["usfm"]] = {"name": book["human"], "chapters": chapters}
    return {"version": src["local_abbreviation"], "source": SOURCE,
            "copyright": src["copyright"]["text"], "books": books}


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    data = compact(json.loads(Path(src).read_text(encoding="utf-8")))
    verses = sum(len(v) for b in data["books"].values() for v in b["chapters"].values())
    assert len(data["books"]) == 66 and verses > 31000, (len(data["books"]), verses)
    assert data["books"]["JHN"]["chapters"]["3"]["16"][0].startswith("Porque de tal manera amó Dios al mundo")
    Path(out).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out}: 66 books, {verses} verses")
