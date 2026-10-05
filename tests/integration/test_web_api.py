"""The HTTP API the web app talks to, through Flask's test client.

Techniques: one request per partition of /api/parse input (text, browser OCR
lines, image for server OCR), error guessing on the trust boundary (paths and
ops in a client spec, HEIC uploads, a lyrics PDF without review).
"""
import base64
import io

import pytest
from conftest import FLYER, draw_flyer, needs_tesseract
from pptx import Presentation
from pypdf import PdfReader

from worshipdeck.web import app


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


def data_url(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def test_parse_text_gives_items_views_and_the_sunday(client):
    r = client.post("/api/parse", json={"text": "Himno 64\nAl estar ante Ti\nIGLESIA AMIGOS"}).get_json()
    assert [v["title"] for v in r["views"]][1:] == ["Quiero seguir en los pasos del Maestro", "Al estar Ante ti"]
    assert [p["text"] for p in r["pendientes"]] == ["IGLESIA AMIGOS"]
    assert r["date_label"].startswith("Domingo ")


def test_browser_ocr_lines_get_unread_bands_and_crops(client, tmp_path):
    img = draw_flyer(tmp_path / "f.png", ["Himno 64", "Himno 83"], blurred={"Himno 83"})
    lines = [{"text": "Himno 64", "conf": 95, "box": [80, 60, 330, 120]}]  # what tesseract.js saw
    r = client.post("/api/parse", json={"image": data_url(img), "lines": lines, "fresh": True}).get_json()
    assert r["spec"]["items"][1] == {"op": "hymn", "himno": 64}
    unread = [p for p in r["pendientes"] if p["text"] == ""]
    assert len(unread) == 1 and unread[0]["crop"].startswith("data:image/png;base64,")


def test_reposting_corrected_lines_resolves_them(client, tmp_path):
    img = draw_flyer(tmp_path / "f.png", ["Himno 64", "Himno 83"], blurred={"Himno 83"})
    first = client.post("/api/parse", json={"image": data_url(img), "fresh": True,
                                            "lines": [{"text": "Himno 64", "conf": 95, "box": [80, 60, 330, 120]}]})
    lines = first.get_json()["lines"]
    for line in lines:
        if line["text"] == "":
            line.update(text="Himno 83", conf=100)  # what the person typed under the crop
    r = client.post("/api/parse", json={"image": data_url(img), "lines": lines}).get_json()
    assert [i.get("himno") for i in r["spec"]["items"][1:]] == [64, 83] and r["pendientes"] == []


@needs_tesseract
def test_server_side_ocr_when_only_an_image_comes(client):
    r = client.post("/api/parse", json={"image": data_url(FLYER)}).get_json()
    assert [i.get("himno") or i.get("key") for i in r["spec"]["items"][1:]] == [
        64, "eres-mi-amigo-fiel", 83, "al-estar-ante-ti", "el-senor-es-mi-pastor"]


def test_heic_is_refused_with_a_message(client):
    heic = "data:image/heic;base64," + base64.b64encode(b"\0\0\0\x18ftypheic" + b"\0" * 32).decode()
    r = client.post("/api/parse", json={"image": heic})
    assert r.status_code == 415 and "HEIC" in r.get_json()["error"]


@pytest.mark.parametrize("q, first", [("64", "Himno 64"), ("al estar", "Canción"), ("jehova es mi", "Himno 83")])
def test_search(client, q, first):
    assert client.get(f"/api/search?q={q}").get_json()[0]["label"] == first


def test_hymn_lyrics_in_sung_order(client):
    r = client.get("/api/hymn/44").get_json()
    assert [s["kind"] for s in r["sections"]][-2:] == ["verse", "chorus"]
    assert client.get("/api/hymn/413").status_code == 404


def test_preview_and_build_from_the_same_spec(client):
    spec = client.post("/api/parse", json={"text": "Himno 64", "passage": "Salmos 23:1-2",
                                           "sermon_title": "Pastor"}).get_json()["spec"]
    prev = client.post("/api/preview", json=spec).get_json()
    assert len(prev["slides"]) == 3 + 17 + 1 + 2 and prev["pendientes"] == []
    deck = client.post("/api/build", json=spec)
    assert deck.status_code == 200
    assert len(Presentation(io.BytesIO(deck.data)).slides) == len(prev["slides"])


@pytest.mark.parametrize("bad", [
    {"items": [{"op": "clone_range", "start": 1, "end": 1, "source": "/etc/passwd"}], "template": "/etc/passwd"},
    {"items": [{"op": "song", "key": "../../secret"}]},
    {"items": [{"op": "shell", "cmd": "rm"}]},
])
def test_client_specs_cannot_reach_paths_or_unknown_ops(client, bad):
    r = client.post("/api/preview", json=bad)
    if r.status_code == 200:  # clone_range without its source: the church template, never the path
        assert "passwd" not in str(r.get_json())
    else:
        assert r.status_code == 400


def test_letras_requires_review_and_returns_a_pdf(client):
    spec = client.post("/api/parse", json={"text": "Himno 64\nAl estar ante Ti"}).get_json()["spec"]
    deck = client.post("/api/build", json=spec).data
    refused = client.post("/api/letras", data={"deck": (io.BytesIO(deck), "OCTUBRE 11.pptx")},
                          content_type="multipart/form-data")
    assert refused.status_code == 400
    ok = client.post("/api/letras", data={"deck": (io.BytesIO(deck), "OCTUBRE 11.pptx"), "reviewed": "true"},
                     content_type="multipart/form-data")
    assert ok.status_code == 200 and len(PdfReader(io.BytesIO(ok.data)).pages) == 2


def test_import_deck_marks_songs_already_in_the_library(client):
    from conftest import REPO
    deck = (REPO / "reference" / "decks" / "AGOSTO 30.pptx").read_bytes()
    r = client.post("/api/import-deck", data={"deck": (io.BytesIO(deck), "a.pptx")},
                    content_type="multipart/form-data").get_json()
    assert {s["key"]: s["exists"] for s in r}["hosanna"] is True
