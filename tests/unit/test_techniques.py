"""Unit tests designed with one named technique each (ISTQB, see tests/README.md).

Pure functions only: no files, no tesseract, milliseconds per test.
"""
import datetime

import pytest

from worshipdeck import builder as B
from worshipdeck import flyer as F

# ---------------------------------------------------------------- boundary values

SHORT = B.AUTO_CHUNK_SHORT_LINE  # 28: hymn lines up to here fit 4 per slide


@pytest.mark.parametrize("longest, size", [(SHORT - 1, 4), (SHORT, 4), (SHORT + 1, 2)], ids=["BVA-01-27-chars", "BVA-02-28-chars", "BVA-03-29-chars"])
def test_auto_chunk_size_boundary(longest, size):
    assert B.auto_chunk_size(["x" * longest, "corta"]) == size


def test_bva_04_auto_chunk_size_of_an_empty_stanza():
    assert B.auto_chunk_size([]) == 2  # nothing to measure: the safe size


@pytest.mark.parametrize("conf, asked", [(F.MIN_CONF - 1, True), (F.MIN_CONF, False), (F.MIN_CONF + 1, False)], ids=["BVA-05-conf-59", "BVA-06-conf-60", "BVA-07-conf-61"])
def test_confidence_boundary_decides_who_gets_asked(conf, asked):
    calls = []
    rec = {"text": "Himno 64", "conf": conf, "box": (0, 0, 1, 1)}
    F.parse_flyer_text([rec], {}, {}, ask=lambda *a: calls.append(a) or "")
    assert bool(calls) is asked


@pytest.mark.parametrize("today, sunday", [
    (datetime.date(2026, 10, 10), "OCTUBRE 11.pptx"),    # Saturday -> tomorrow
    (datetime.date(2026, 10, 11), "OCTUBRE 11.pptx"),    # Sunday -> today
    (datetime.date(2026, 10, 12), "OCTUBRE 18.pptx"),    # Monday -> 6 days out
    (datetime.date(2026, 12, 28), "ENERO 3.pptx"),       # across the year boundary
], ids=["BVA-08-sabado", "BVA-09-domingo", "BVA-10-lunes", "BVA-11-cambio-de-ano"])
def test_next_sunday_boundaries(today, sunday):
    assert F.next_sunday_name(today) == sunday


# ---------------------------------------------------------- equivalence partitions

@pytest.mark.parametrize("line, number", [
    ("Himno 64", 64), ("himno64", 64), ("HIMNO # 64", 64), ("Himno Nº 64", 64), ("H. 64", 64), ("#64", 64),
    ("Hosanna", None),           # starts with H, no number
    ("Himno", None),             # the word without a number
    ("Domingo 10:00", None),     # digits, but not after himno/H/#
], ids=["EP-01-Himno-64", "EP-02-himno64", "EP-03-HIMNO-#-64", "EP-04-Himno-No-64", "EP-05-H.-64", "EP-06-#64", "EP-07-Hosanna", "EP-08-Himno-sin-numero", "EP-09-Domingo-10-00"])
def test_hymn_pattern_partitions(line, number):
    m = F.HYMN_RE.search(line)
    assert (int(m.group(1) or m.group(2)) if m else None) == number


@pytest.mark.parametrize("line, refs", [
    ("Salmos 23:1-6", [("Salmos", "23:1-6")]),
    ("San Juan 3:16", [("San Juan", "3:16")]),
    ("Juan 3 : 16 – 18", [("Juan", "3:16-18")]),       # OCR spacing and en dash
    ("Domingo 10:00", []),                               # not a book
    ("Salmos 23", []),                                   # chapter without verses
], ids=["EP-10-Salmos-23-1-6", "EP-11-San-Juan-3-16", "EP-12-espacios-y-guion-largo", "EP-13-Domingo-10-00", "EP-14-capitulo-sin-versiculos"])
def test_scripture_partitions(line, refs):
    assert [(i["book"], i["range"]) for i in F.scripture_items(line)] == refs


# ------------------------------------------------------------------ decision table
# C1 OCR confidence low? · C2 line matches something? · C3 a person can be asked?
# A1 asked · A2 item added · A3 left in _pendientes. The person answers "" (keep).
#           C1     C2     C3     A1     A2     A3
RULES = [
    ("R1", True,  True,  True,  True,  True,  False),
    ("R2", True,  True,  False, False, True,  True),
    ("R3", True,  False, True,  True,  False, True),
    ("R4", True,  False, False, False, False, True),
    ("R5", False, True,  True,  False, True,  False),
    ("R6", False, True,  False, False, True,  False),
    ("R7", False, False, True,  True,  False, True),
    ("R8", False, False, False, False, False, True),
]


@pytest.mark.parametrize("rule, low, matches, can_ask, asked, added, pending", RULES, ids=["DT-01-R1", "DT-02-R2", "DT-03-R3", "DT-04-R4", "DT-05-R5", "DT-06-R6", "DT-07-R7", "DT-08-R8"])
def test_doubtful_line_decision_table(rule, low, matches, can_ask, asked, added, pending):
    library = {"hosanna": {"title_white": "Hosanna", "sections": []}}
    rec = {"text": "Hosanna" if matches else "Feliz domingo", "conf": 30 if low else 90, "box": (0, 0, 1, 1)}
    calls = []
    ask = (lambda *a: calls.append(a) or "") if can_ask else None
    items, pend = F.parse_flyer_text([rec], {}, library, ask)
    assert (bool(calls), bool(items), bool(pend)) == (asked, added, pending)


# --------------------------------------------------------------- state transitions
# Doubtful --text that matches--> Resolved   (item added, no more questions)
# Doubtful --text that doesn't--> Doubtful   (asked again)
# Doubtful --"-" (None)--------> Dropped    (neither item nor pending)
# Doubtful --Enter ("")--------> Kept       (pending, no more questions)

@pytest.mark.parametrize("answers, questions, items, pending", [
    (["Hosanna"], 1, ["hosanna"], 0),                     # Doubtful -> Resolved
    (["Feliz domingo", "Hosanna"], 2, ["hosanna"], 0),    # Doubtful -> Doubtful -> Resolved
    ([None], 1, [], 0),                                   # Doubtful -> Dropped
    (["algo", ""], 2, [], 1),                             # Doubtful -> Doubtful -> Kept
], ids=["ST-01-dudosa-resuelta", "ST-02-dudosa-dudosa-resuelta", "ST-03-dudosa-descartada", "ST-04-dudosa-dudosa-pendiente"])
def test_ask_loop_transitions(answers, questions, items, pending):
    library = {"hosanna": {"title_white": "Hosanna", "sections": []}}
    rec = {"text": "", "conf": 0, "box": (0, 0, 1, 1)}  # an unread band starts Doubtful
    script = list(answers)
    got_items, pend = F.parse_flyer_text([rec], {}, library, lambda *a: script.pop(0))
    assert len(answers) - len(script) == questions
    assert [i["key"] for i in got_items] == items and len(pend) == pending


# --------------------------------------------------- invalid transitions (all transitions)
# Resolved, Dropped and Kept are terminal: none of the 4 events may reach them. One invalid
# transition per case (3 states x 4 events = 12): the person would still answer, the loop must not ask.
ENTER = {"resuelta": "Hosanna", "descartada": None, "pendiente": ""}
EVENT = {"coincide": "Hosanna", "no-coincide": "Feliz domingo", "descartar": None, "enter": ""}
INVALID = [(state, event) for state in ENTER for event in EVENT]


@pytest.mark.parametrize("state, event", INVALID,
                         ids=[
    "ST-I1-resuelta-coincide",
    "ST-I2-resuelta-no-coincide",
    "ST-I3-resuelta-descartar",
    "ST-I4-resuelta-enter",
    "ST-I5-descartada-coincide",
    "ST-I6-descartada-no-coincide",
    "ST-I7-descartada-descartar",
    "ST-I8-descartada-enter",
    "ST-I9-pendiente-coincide",
    "ST-I10-pendiente-no-coincide",
    "ST-I11-pendiente-descartar",
    "ST-I12-pendiente-enter"])
def test_terminal_states_accept_no_more_answers(state, event):
    library = {"hosanna": {"title_white": "Hosanna", "sections": []}}
    script = [ENTER[state], EVENT[event]]
    F.parse_flyer_text([{"text": "", "conf": 0, "box": (0, 0, 1, 1)}], {}, library, lambda *a: script.pop(0))
    assert script == [EVENT[event]]


# ------------------------------------------------------------- branches left uncovered

def test_br_01_unreadable_passage_is_reported():
    with pytest.raises(SystemExit, match="Can't read the passage"):
        F.make_spec("", "X.pptx", passage="el salmo del pastor")


def test_br_02_text_mode_pendientes_get_a_plain_warning():
    spec = {"items": [{"op": "sermon"}], "_pendientes": ["IGLESIA AMIGOS"]}
    assert F.warnings(spec) == ["sin match: 'IGLESIA AMIGOS' (si es una canción, agrégala con `worshipdeck song add`)"]
