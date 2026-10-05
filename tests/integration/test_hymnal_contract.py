"""Contract between tools/extract_hymnal.py (writes data/hymnal.json) and the builder (reads it).

Techniques: boundary values on the hymn number (0/1, 412/413), invariants over all
412 entries, and a cross-check against the PDF parser on hymns the operator uses.
"""
import re

import pytest
from conftest import REAL_HYMNAL, REAL_HYMNAL_PDF

from worshipdeck import builder as B

HYMNS = __import__("json").loads(REAL_HYMNAL.read_text(encoding="utf-8"))["hymns"]


def test_numbers_are_contiguous_and_match_their_key():
    assert sorted(map(int, HYMNS)) == list(range(1, 413))
    assert all(h["number"] == int(n) for n, h in HYMNS.items())


@pytest.mark.parametrize("number, exists", [(0, False), (1, True), (412, True), (413, False)])
def test_hymn_number_boundaries(number, exists):
    if exists:
        parsed, title = B.load_hymn(REAL_HYMNAL, number)
        assert parsed["verses"] and title
    else:
        with pytest.raises(SystemExit, match=f"Himno {number}"):
            B.load_hymn(REAL_HYMNAL, number)


def test_every_order_tag_points_at_a_real_stanza():
    for n, h in HYMNS.items():
        choruses = h.get("choruses") or ([h["chorus"]] if h.get("chorus") else [])
        for tag in h.get("order") or []:
            if tag.startswith("v"):
                assert 1 <= int(tag[1:]) <= len(h["verses"]), (n, tag)
            else:
                assert 1 <= int(tag[6:] or 1) <= len(choruses), (n, tag)


def test_clean_hymns_have_no_ocr_glue_or_empty_lines():
    for n, h in HYMNS.items():
        if h.get("needs_review"):
            continue
        lines = [line for v in h["verses"] for line in v] + (h.get("chorus") or [])
        assert h["verses"], n
        assert all(line.strip() == line and line for line in lines), n
        assert not any(re.match(r"^\d", line) for line in lines), n  # verse number stuck to text


def test_flagged_hymns_explain_why_and_keep_the_raw_page():
    flagged = {n: h for n, h in HYMNS.items() if h.get("needs_review")}
    assert flagged, "the extractor flags irregular pages; zero flags means the check broke"
    assert all(h["review_notes"] and h.get("raw_lines") for h in flagged.values())


# 225 is the regression: "Coronadle..." used to be read as a "Coro" marker.
@pytest.mark.parametrize("number", [1, 64, 83, 116, 132, 168, 225, 270])
def test_json_and_pdf_parser_agree(number):
    from_json, _ = B.load_hymn(REAL_HYMNAL, number)
    from_pdf, _ = B.load_hymn(REAL_HYMNAL_PDF, number)
    assert from_json["verses"] == from_pdf["verses"]
    assert from_json["chorus"] == from_pdf["chorus"]


def test_second_chorus_closes_hymn_44():
    parsed, _ = B.load_hymn(REAL_HYMNAL, 44)
    sections = B.hymn_sections(parsed, "auto", "auto")
    assert sections[-1][1] == HYMNS["44"]["choruses"][1]
    assert sections[-1][1] != HYMNS["44"]["choruses"][0]
