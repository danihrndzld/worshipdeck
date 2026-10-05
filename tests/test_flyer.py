"""Tests for flyer text -> spec. Run: `python3 tests/test_flyer.py` (or pytest)."""
import datetime
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
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
    assert any("RV1960" in w for w in F.warnings(spec))


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
            n += 1
    print(f"\n{n} passed")
