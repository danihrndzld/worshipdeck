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


def test_ep_56_parse_text_gives_items_views_and_the_sunday(client):
    r = client.post("/api/parse", json={"text": "Himno 64\nAl estar ante Ti\nIGLESIA AMIGOS"}).get_json()
    assert [v["title"] for v in r["views"]][1:] == ["Quiero seguir en los pasos del Maestro", "Al estar Ante ti"]
    assert [p["text"] for p in r["pendientes"]] == ["IGLESIA AMIGOS"]
    assert r["date_label"].startswith("Domingo ")


def test_ep_57_browser_ocr_lines_get_unread_bands_and_crops(client, tmp_path):
    img = draw_flyer(tmp_path / "f.png", ["Himno 64", "Himno 83"], blurred={"Himno 83"})
    lines = [{"text": "Himno 64", "conf": 95, "box": [80, 60, 330, 120]}]  # what tesseract.js saw
    r = client.post("/api/parse", json={"image": data_url(img), "lines": lines, "fresh": True}).get_json()
    assert r["spec"]["items"][1] == {"op": "hymn", "himno": 64}
    unread = [p for p in r["pendientes"] if p["text"] == ""]
    assert len(unread) == 1 and unread[0]["crop"].startswith("data:image/png;base64,")


def test_st_07_reposting_corrected_lines_resolves_them(client, tmp_path):
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
def test_ep_58_server_side_ocr_when_only_an_image_comes(client):
    r = client.post("/api/parse", json={"image": data_url(FLYER)}).get_json()
    assert [i.get("himno") or i.get("key") for i in r["spec"]["items"][1:]] == [
        64, "eres-mi-amigo-fiel", 83, "al-estar-ante-ti", "el-senor-es-mi-pastor"]


def test_eg_13_heic_is_refused_with_a_message(client):
    heic = "data:image/heic;base64," + base64.b64encode(b"\0\0\0\x18ftypheic" + b"\0" * 32).decode()
    r = client.post("/api/parse", json={"image": heic})
    assert r.status_code == 415 and "HEIC" in r.get_json()["error"]


@pytest.mark.parametrize("q, first", [("64", "Himno 64"), ("al estar", "Canción"), ("jehova es mi", "Himno 83")], ids=["EP-59-numero", "EP-60-cancion", "EP-61-titulo-de-himno"])
def test_search(client, q, first):
    assert client.get(f"/api/search?q={q}").get_json()[0]["label"] == first


def test_ac_07_hymn_lyrics_in_sung_order(client):
    r = client.get("/api/hymn/44").get_json()
    assert [s["kind"] for s in r["sections"]][-2:] == ["verse", "chorus"]
    assert client.get("/api/hymn/413").status_code == 404


def test_ac_08_preview_and_build_from_the_same_spec(client):
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
], ids=["EG-14-ruta-en-source-y-template", "EG-15-key-con-ruta", "EG-16-op-desconocida"])
def test_client_specs_cannot_reach_paths_or_unknown_ops(client, bad):
    r = client.post("/api/preview", json=bad)
    if r.status_code == 200:  # clone_range without its source: the church template, never the path
        assert "passwd" not in str(r.get_json())
    else:
        assert r.status_code == 400


def test_ac_09_letras_requires_review_and_returns_a_pdf(client):
    spec = client.post("/api/parse", json={"text": "Himno 64\nAl estar ante Ti"}).get_json()["spec"]
    deck = client.post("/api/build", json=spec).data
    refused = client.post("/api/letras", data={"deck": (io.BytesIO(deck), "OCTUBRE 11.pptx")},
                          content_type="multipart/form-data")
    assert refused.status_code == 400
    ok = client.post("/api/letras", data={"deck": (io.BytesIO(deck), "OCTUBRE 11.pptx"), "reviewed": "true"},
                     content_type="multipart/form-data")
    assert ok.status_code == 200 and len(PdfReader(io.BytesIO(ok.data)).pages) == 2


def test_ac_10_import_deck_marks_songs_already_in_the_library(client):
    from conftest import REPO
    deck = (REPO / "reference" / "decks" / "AGOSTO 30.pptx").read_bytes()
    r = client.post("/api/import-deck", data={"deck": (io.BytesIO(deck), "a.pptx")},
                    content_type="multipart/form-data").get_json()
    assert {s["key"]: s["exists"] for s in r}["hosanna"] is True


# ------------------------------------------------- error guessing on the trust boundary
# Attack list (CTFL §4.4.1 categories): input the server can't decode, paths in names,
# messages that leak the server's file system.

def bad_image(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def test_eg_20_corrupt_image_is_a_4xx_with_a_message(client):
    r = client.post("/api/parse", json={"image": bad_image(b"not an image at all"), "fresh": True,
                                        "lines": [{"text": "Himno 64", "conf": 95, "box": [0, 0, 10, 10]}]})
    assert r.status_code == 400 and "imagen" in r.get_json()["error"]


def test_eg_21_invalid_base64_is_a_4xx_with_a_message(client):
    r = client.post("/api/parse", json={"image": "data:image/png;base64,%%%no", "text": "Himno 64"})
    assert r.status_code == 400 and "imagen" in r.get_json()["error"]


def test_eg_22_output_name_cannot_climb_directories(client):
    r = client.post("/api/build", json={"output": "../../evil.pptx", "items": [{"op": "hymn", "himno": 1}]})
    assert r.status_code == 200 and r.headers["Content-Disposition"].endswith("filename=evil.pptx")


def test_eg_23_delete_cannot_reach_outside_the_library(client):
    from conftest import REPO
    r = client.delete("/api/library/..%2F..%2Fpyproject")  # %2F decodes to "/": no library route matches
    assert 400 <= r.status_code < 500 and (REPO / "pyproject.toml").exists()


@pytest.mark.parametrize("item", [{"op": "hymn", "himno": 9999}, {"op": "hymn", "himno": "abc"}],
                         ids=["EG-24-himno-inexistente", "EG-25-himno-no-numerico"])
def test_errors_do_not_leak_server_paths(client, item):
    r = client.post("/api/preview", json={"items": [item]})
    assert r.status_code == 400 and "/Users/" not in r.get_json()["error"] and "/var/" not in r.get_json()["error"]


# ------------------------------------------------------------- branches left uncovered

def test_br_03_parse_without_input(client):
    assert client.post("/api/parse", json={}).status_code == 400


def test_br_04_unreadable_passage_is_a_400(client):
    r = client.post("/api/parse", json={"text": "Himno 64", "passage": "el salmo del pastor"})
    assert r.status_code == 400 and "No entiendo el pasaje" in r.get_json()["error"]


def test_br_05_empty_search(client):
    assert client.get("/api/search?q=").get_json() == []


def test_br_06_song_lyrics_and_unknown_song(client):
    song = client.get("/api/song/al-estar-ante-ti").get_json()
    assert (song["title_white"], song["title_cream"]) == ("Al estar", "Ante ti")  # two-tone title kept for edits
    assert client.get("/api/song/no-existe").status_code == 404


def test_br_07_library_list_is_sorted_by_title(client):
    titles = [s["title"].lower() for s in client.get("/api/library").get_json()]
    assert titles == sorted(titles) and len(titles) >= 7


def test_br_08_library_add_conflict_and_delete(client, tmp_path, monkeypatch):
    from worshipdeck import builder
    monkeypatch.setattr(builder, "DEFAULT_LIBRARY_DIR", tmp_path)
    song = {"title_white": "Canción", "title_cream": "de prueba", "sections": [{"type": "verse", "lines": ["a"]}]}
    assert client.post("/api/library", json={"title_white": "", "sections": []}).status_code == 400
    key = client.post("/api/library", json=song).get_json()["key"]
    assert client.post("/api/library", json=song).status_code == 409
    renamed = {**song, "title_cream": "renombrada", "replace": key}
    new_key = client.post("/api/library", json=renamed).get_json()["key"]
    assert new_key != key and client.get(f"/api/song/{new_key}").get_json()["title_cream"] == "renombrada"
    assert client.get(f"/api/song/{key}").status_code == 404  # replaced, not duplicated
    assert client.post("/api/library", json={**song, "replace": "no-existe"}).status_code == 404
    assert client.delete(f"/api/library/{new_key}").get_json() == {"deleted": new_key}
    assert client.delete(f"/api/library/{new_key}").status_code == 404


def test_br_09_library_is_read_only_on_vercel(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert client.post("/api/library", json={}).status_code == 501
    assert client.delete("/api/library/hosanna").status_code == 501


def test_br_10_letras_on_a_deck_without_songs(client):
    from conftest import REAL_TEMPLATE
    spec = {"items": [{"op": "clone_range", "start": 1, "end": 3}]}
    deck = client.post("/api/build", json=spec).data
    assert REAL_TEMPLATE.exists()
    r = client.post("/api/letras", data={"deck": (io.BytesIO(deck), "x.pptx"), "reviewed": "true"},
                    content_type="multipart/form-data")
    assert r.status_code == 422


def test_br_11_the_app_shell_is_served(client):
    assert client.get("/").status_code in (200, 404)  # 404 until web/ exists


def test_br_12_text_lines_without_boxes(client):
    r = client.post("/api/parse", json={"lines": [{"id": 0, "text": "Himno 64", "conf": 100},
                                                  {"id": 1, "text": "IGLESIA AMIGOS", "conf": 100}]})
    assert r.status_code == 200 and r.get_json()["spec"]["items"][1] == {"op": "hymn", "himno": 64}
    assert [p["text"] for p in r.get_json()["pendientes"]] == ["IGLESIA AMIGOS"]
