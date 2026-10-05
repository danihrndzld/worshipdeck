"""Flyer text -> spec items against the REAL hymnal.json and song library.

Technique: equivalence partitioning over the kinds of line a flyer carries, with
boundary values where a partition is ordered (hymn number 0/1/412/413, the 0.8
fuzzy-match cutoff for library titles).
"""
import pytest
from conftest import REAL_HYMNAL

from worshipdeck import flyer as F

HYMN, SONG, PASSAGE, PENDING, SKIPPED = "hymn", "song", "scripture", "pending", "skipped"

CASES = [
    # partition: hymn by number, in every spelling seen on flyers
    ("Himno 64", HYMN, 64),
    ("HIMNO #83", HYMN, 83),
    ("H. 83", HYMN, 83),
    ("#83", HYMN, 83),
    ("Himno No. 83", HYMN, 83),
    # boundaries of the hymnal (1..412)
    ("Himno 0", PENDING, None),
    ("Himno 1", HYMN, 1),
    ("Himno 412", HYMN, 412),
    ("Himno 413", PENDING, None),
    # partition: library song (exact, no accents/caps, OCR typo above the cutoff)
    ("Al estar ante Ti", SONG, "al-estar-ante-ti"),
    ("AL ESTAR ANTE TI", SONG, "al-estar-ante-ti"),
    ("El senor es mi pastor", SONG, "el-senor-es-mi-pastor"),
    ("Al estar ante Tl", SONG, "al-estar-ante-ti"),
    # below the cutoff: half a title is not a match
    ("Al estar", PENDING, None),
    # partition: hymn by title, no number
    ("Jehová es mi pastor", HYMN, 83),
    # partition: passage (plain book, numbered book, two ranges of one book)
    ("Salmos 42:1-2", PASSAGE, ["Salmos 42:1-2"]),
    ("1 Corintios 13:4-7", PASSAGE, ["1 Corintios 13:4-7"]),
    ("Salmos 42:1-2 & 63:1-3", PASSAGE, ["Salmos 42:1-2", "Salmos 63:1-3"]),
    # invalid: a time is not a passage, a church name is not a song
    ("Domingo 10:00", PENDING, None),
    ("IGLESIA AMIGOS", PENDING, None),
    # decoration with almost no letters is dropped silently
    ("— ✦ —", SKIPPED, None),
]


@pytest.mark.parametrize("line, kind, expected", CASES, ids=["EP-22-Himno 64", "EP-23-HIMNO #83", "EP-24-H. 83", "EP-25-#83", "EP-26-Himno No. 83", "BVA-14-Himno 0", "BVA-15-Himno 1", "BVA-16-Himno 412", "BVA-17-Himno 413", "EP-27-Al estar ante Ti", "EP-28-AL ESTAR ANTE TI", "EP-29-El senor es mi pastor", "EP-30-Al estar ante Tl", "BVA-18-Al estar", "EP-31-Jehova es mi pastor", "EP-32-Salmos 42:1-2", "EP-33-1 Corintios 13:4-7", "EP-34-Salmos 42:1-2 & 63:1-3", "EP-35-Domingo 10:00", "EP-36-IGLESIA AMIGOS", "EP-37-decoracion"])
def test_line_partition(line, kind, expected, library):
    items, pendientes = F.parse_flyer_text(line, REAL_HYMNAL, library)
    if kind == HYMN:
        assert items == [{"op": "hymn", "himno": expected}] and not pendientes
    elif kind == SONG:
        assert items == [{"op": "song", "key": expected}] and not pendientes
    elif kind == PASSAGE:
        assert [f"{i['book']} {i['range']}" for i in items] == expected and not pendientes
    elif kind == PENDING:
        assert items == [] and pendientes == [line]
    else:
        assert items == [] and pendientes == []


def test_ac_02_flyer_order_is_kept(library):
    text = "ALABANZAS\nHimno 64\nEres mi amigo fiel\nHimno 83\nAl estar ante Ti\nEl Señor es mi pastor"
    items, _ = F.parse_flyer_text(text, REAL_HYMNAL, library)
    assert [i.get("himno") or i.get("key") for i in items] == [
        64, "eres-mi-amigo-fiel", 83, "al-estar-ante-ti", "el-senor-es-mi-pastor"]


# Risk 6 (a hymn or song silently swapped or lost): 3-value boundaries, so each edge also gets
# its inner neighbour. 0.8 cutoff: "Al estar an" scores 0.81 against "al estar ante ti", "Al estar a" 0.77.
@pytest.mark.parametrize("line, expected", [("Himno 2", 2), ("Himno 411", 411),
                                            ("Al estar an", "al-estar-ante-ti"), ("Al estar a", None)],
                         ids=["BVA-32-Himno 2", "BVA-33-Himno 411", "BVA-34-corte-0.81", "BVA-35-corte-0.77"])
def test_three_value_neighbours(line, expected, library):
    items, _ = F.parse_flyer_text(line, REAL_HYMNAL, library)
    got = (items[0].get("himno") or items[0].get("key")) if items else None
    assert got == expected
