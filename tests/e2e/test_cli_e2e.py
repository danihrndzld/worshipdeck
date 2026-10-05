"""The installed `worshipdeck` command, run as a subprocess the way the operator runs it.

Few and slow on purpose (the Trophy's thin top): one happy path per user journey,
the interactive journey through a real pseudo-terminal, one error path.
"""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from conftest import FLYER, draw_flyer, needs_soffice, needs_tesseract
from pptx import Presentation
from pypdf import PdfReader

EXE = str(Path(sys.executable).parent / "worshipdeck")
pytestmark = needs_tesseract


def run(*args, cwd, **kw):
    return subprocess.run([EXE, *map(str, args)], cwd=cwd, capture_output=True, text=True,
                          timeout=120, check=False, **kw)


@pytest.fixture(scope="module")
def deck(tmp_path_factory):
    """Flyer image -> deck in one command (the weekly journey)."""
    d = tmp_path_factory.mktemp("week")
    r = run("make", FLYER, "--no-ask", "--sermon-lead", "Sed por la", "--sermon-title", "Presencia de Dios",
            "--passage", "Salmos 42:1-2", "-o", d / "SEPTIEMBRE 6.pptx", cwd=d)
    assert r.returncode == 0, r.stderr
    return d / "SEPTIEMBRE 6.pptx", r


def test_make_writes_the_deck_and_its_spec(deck):
    path, r = deck
    assert zipfile.ZipFile(path).testzip() is None
    assert len(Presentation(str(path)).slides) == 72
    spec = json.loads(path.with_suffix(".spec.json").read_text(encoding="utf-8"))
    assert [i["op"] for i in spec["items"]][-2:] == ["sermon", "scripture"]
    assert "RV1960" in r.stderr  # the passage text is still to paste


def test_letras_pdf_from_the_reviewed_deck(deck):
    path, _ = deck
    r = run("letras", "--deck", path, "--reviewed", cwd=path.parent)
    assert r.returncode == 0, r.stderr
    pdf = path.parent / f"Letras - {path.stem}.pdf"
    assert len(PdfReader(pdf).pages) == 5  # one page per song: 2 hymns + 3 songs


def test_letras_refuses_a_deck_nobody_reviewed(deck):
    path, _ = deck
    r = run("letras", "--deck", path, cwd=path.parent)
    assert r.returncode != 0 and "--reviewed" in r.stderr


@pytest.mark.slow
@needs_soffice
def test_libreoffice_renders_every_slide(deck, tmp_path):
    path, _ = deck
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp_path, path],
                   capture_output=True, timeout=180, check=True)
    assert len(PdfReader(tmp_path / f"{path.stem}.pdf").pages) == 72


def test_interactive_questions_through_a_real_terminal(tmp_path):
    img = draw_flyer(tmp_path / "flyer.png", ["IGLESIA AMIGOS", "Himno 64", "Himno 83"], blurred={"Himno 83"})
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "open").write_text("#!/bin/sh\nexit 0\n")  # macOS would pop up Preview
    (shim / "open").chmod(0o755)
    env = {**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}

    master, slave = os.openpty()
    proc = subprocess.Popen([EXE, "parse", img, "-o", tmp_path / "spec.json", "--output", "X.pptx"],
                            stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=tmp_path, env=env, text=True)
    os.close(slave)
    os.write(master, b"-\nHimno 83\n")  # drop the church name, type the blurred hymn
    _, err = proc.communicate(timeout=120)
    os.close(master)

    assert proc.returncode == 0, err
    assert err.count("?") >= 2 and "recorte:" in err
    spec = json.loads((tmp_path / "spec.json").read_text(encoding="utf-8"))
    assert [i.get("himno") for i in spec["items"][1:]] == [64, 83]


def test_a_missing_image_fails_with_a_message_not_a_traceback(tmp_path):
    r = run("parse", tmp_path / "no-existe.png", "--no-ask", cwd=tmp_path)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr and "tesseract" in r.stderr
