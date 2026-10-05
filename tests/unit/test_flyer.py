"""Tests for flyer text -> spec. Run: `python3 tests/test_flyer.py` (or pytest)."""
import datetime
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from worshipdeck import flyer as F  # noqa: E402

LIBRARY = {"al-estar-ante-ti": {"title_white": "Al estar", "title_cream": "Ante ti", "sections": []}}


def hymnal(d):
    path = Path(d) / "hymnal.json"
    path.write_text(json.dumps({"hymns": {
        "64": {"title": "Quiero seguir en los pasos del Maestro", "verses": [], "chorus": None},
        "83": {"title": "Jehová es mi pastor", "verses": [], "chorus": None},
    }}), encoding="utf-8")
    return path


def test_flyer_lines_become_ops_in_order():
    text = "\n".join([
        "IGLESIA AMIGOS", "Domingo 10:00 AM", "ALABANZAS",
        "Himno 64", "• Al estar ante Ti", "H. 83", "Jehova es mi pastor",
        "Salmos 42:1-2 & 63:1-3", "Cancion nueva sin letra",
    ])
    with tempfile.TemporaryDirectory() as d:
        items, pend = F.parse_flyer_text(text, hymnal(d), LIBRARY)
    assert items[:4] == [{"op": "hymn", "himno": 64}, {"op": "song", "key": "al-estar-ante-ti"},
                         {"op": "hymn", "himno": 83}, {"op": "hymn", "himno": 83}], items
    assert [(i["book"], i["range"]) for i in items[4:]] == [("Salmos", "42:1-2"), ("Salmos", "63:1-3")]
    assert pend == ["IGLESIA AMIGOS", "Domingo 10:00 AM", "ALABANZAS", "Cancion nueva sin letra"], pend


def test_unknown_hymn_number_is_not_a_hymn():
    with tempfile.TemporaryDirectory() as d:
        items, pend = F.parse_flyer_text("Himno 999", hymnal(d), {})
    assert items == [] and pend == ["Himno 999"]


def test_next_sunday_name():
    assert F.next_sunday_name(datetime.date(2026, 10, 5)) == "OCTUBRE 11.pptx"  # a Monday
    assert F.next_sunday_name(datetime.date(2026, 10, 11)) == "OCTUBRE 11.pptx"  # Sunday itself


def test_make_spec_adds_intro_sermon_and_passage():
    with tempfile.TemporaryDirectory() as d:
        spec = F.make_spec("Himno 64", "X.pptx", "Esperanza", passage="Salmos 1:1-3", hymnal=hymnal(d))
    ops = [i["op"] for i in spec["items"]]
    assert ops == ["clone_range", "hymn", "sermon", "scripture"], ops
    assert spec["items"][2]["reference"] == "Salmos 1:1-3"
    assert spec["items"][3]["chunks"][0][:2] == ["1", "Bienaventurado el varón que no anduvo en consejo de malos,"]
    assert not any("pegar texto" in w for w in F.warnings(spec))


def test_a_passage_rvr1960_lacks_is_left_to_fill_in():
    spec = F.make_spec("", "X.pptx", "Tema", passage="Salmos 151:1")
    assert spec["items"][-1]["chunks"] == [[F.SCRIPTURE_TODO]]
    assert any("pegar texto" in w for w in F.warnings(spec))


TSV = "\n".join([
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
    "4\t1\t1\t1\t1\t0\t10\t10\t200\t40\t-1\t",
    "5\t1\t1\t1\t1\t1\t10\t10\t90\t40\t95.1\tHimno",
    "5\t1\t1\t1\t1\t2\t110\t12\t40\t38\t31.0\t6?",
    "5\t1\t1\t1\t2\t1\t10\t70\t120\t40\t92.0\tHosanna",
])


def test_tsv_groups_words_into_lines_with_weakest_conf():
    lines = F.lines_from_tsv(TSV)
    assert lines == [{"text": "Himno 6?", "conf": 31, "box": (10, 10, 150, 50)},
                     {"text": "Hosanna", "conf": 92, "box": (10, 70, 130, 110)}], lines


def test_ask_fixes_drops_and_rechecks_doubtful_lines():
    recs = [{"text": "Himno 6?", "conf": 31, "box": (0, 0, 1, 1)},     # garbled number
            {"text": "IGLESIA AMIGOS", "conf": 95, "box": (0, 0, 1, 1)},  # noise
            {"text": "Al estar ante Ti", "conf": 96, "box": (0, 0, 1, 1)},
            {"text": "Cancion nueva", "conf": 90, "box": (0, 0, 1, 1)}]
    answers = {"Himno 6?": ["Himno 65", "Himno 64"], "IGLESIA AMIGOS": [None], "Cancion nueva": [""]}
    asked = []

    def ask(rec, line, found):
        asked.append(line)
        return answers[rec["text"]].pop(0)

    with tempfile.TemporaryDirectory() as d:
        items, pend = F.parse_flyer_text(recs, hymnal(d), LIBRARY, ask)
    # 65 isn't in the hymnal -> asked again; the matched line is never asked about
    assert asked == ["Himno 6?", "Himno 65", "IGLESIA AMIGOS", "Cancion nueva"], asked
    assert items == [{"op": "hymn", "himno": 64}, {"op": "song", "key": "al-estar-ante-ti"}], items
    assert [p["text"] for p in pend] == ["Cancion nueva"]  # kept as is -> still pending


def test_without_ask_shaky_matches_are_kept_and_listed():
    recs = [{"text": "Himno 64", "conf": 40, "box": (0, 0, 1, 1)}]
    with tempfile.TemporaryDirectory() as d:
        items, pend = F.parse_flyer_text(recs, hymnal(d), {})
    assert items == [{"op": "hymn", "himno": 64}]
    assert pend[0]["matched"] and pend[0]["conf"] == 40


def test_unread_bands_finds_ink_no_ocr_box_covers():
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as d:
        img = Path(d) / "f.png"
        im = Image.new("L", (400, 300), 40)
        ImageDraw.Draw(im).rectangle((50, 100, 250, 130), fill=200)  # a "line" of text
        im.save(img)
        bands = F.unread_bands(img, [])
        assert len(bands) == 1 and abs(bands[0][1] - 100) <= 2 and abs(bands[0][3] - 131) <= 2, bands
        assert F.unread_bands(img, [(50, 98, 250, 132)]) == []  # OCR read it -> nothing to ask


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
            n += 1
    print(f"\n{n} passed")
