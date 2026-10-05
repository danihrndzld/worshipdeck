"""RVR1960 lookup against the real data/rvr1960.json.

Techniques: equivalence partitions over how a book gets written on a flyer,
boundary values on verse numbers (first/last verse of a chapter, one past it),
and the slide-packing boundary (6 estimated lines per slide).
"""
import pytest

from worshipdeck import bible


@pytest.mark.parametrize("book", ["Salmos", "Salmo", "SALMOS", "salmos"], ids=["EP-38-Salmos", "EP-39-Salmo", "EP-40-SALMOS", "EP-41-salmos"])
def test_psalms_spellings(book):
    assert bible.verses(book, "23:1")[0][1][0] == "Jehová es mi pastor; nada me faltará."


@pytest.mark.parametrize("book", ["Juan", "San Juan", "S. Juan", "S Juan"], ids=["EP-42-Juan", "EP-43-San-Juan", "EP-44-S.-Juan", "EP-45-S-Juan"])
def test_gospel_spellings(book):
    assert bible.verses(book, "3:16")[0][1][0].startswith("Porque de tal manera amó Dios al mundo")


@pytest.mark.parametrize("book, rng", [("1 Corintios", "13:4"), ("1 Juan", "4:8"), ("Cantar de los Cantares", "2:4"),
                                       ("Génesis", "1:1"), ("Genesis", "1:1"), ("Apocalipsis", "22:21")], ids=["EP-46-1-Corintios", "EP-47-1-Juan", "EP-48-Cantar-de-los-Cantares", "EP-49-Genesis-con-tilde", "EP-50-Genesis-sin-tilde", "EP-51-Apocalipsis-22-21"])
def test_numbered_accented_and_alias_books(book, rng):
    assert bible.verses(book, rng)


@pytest.mark.parametrize("rng, ok", [("23:0", False), ("23:1", True), ("23:6", True), ("23:7", False),
                                     ("151:1", False), ("23:1-6", True), ("23:6-1", False)], ids=["BVA-19-23-0", "BVA-20-23-1", "BVA-21-23-6", "BVA-22-23-7", "BVA-23-151-1", "BVA-24-23-1-6", "BVA-25-23-6-1"])
def test_verse_boundaries(rng, ok):
    if ok:
        assert bible.verses("Salmos", rng)
    else:
        with pytest.raises(KeyError):
            bible.verses("Salmos", rng)


@pytest.mark.parametrize("book, rng", [("Hezequiel", "1:1"), ("Salmos", "23"), ("Salmos", "1:6-2:3")], ids=["EP-52-libro-inexistente", "EP-53-sin-versiculo", "EP-54-entre-capitulos"])
def test_invalid_book_or_range(book, rng):
    with pytest.raises(KeyError):
        bible.verses(book, rng)


def test_bva_26_six_lines_share_a_slide_and_the_seventh_starts_another():
    assert len(bible.passage_chunks("Salmos", "63:1-2")) == 1  # 4 + 2 lines
    assert [c[0] for c in bible.passage_chunks("Salmos", "63:1-3")] == ["1", "3"]  # + 2 more


def test_bva_27_a_long_verse_gets_a_slide_of_its_own():
    chunks = bible.passage_chunks("Juan", "3:16-17")  # ~4 wrapped lines each
    assert [c[0] for c in chunks] == ["16", "17"]
