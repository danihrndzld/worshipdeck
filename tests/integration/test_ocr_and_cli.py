"""OCR with the real tesseract binary, and the CLI's ask flow run in-process.

Technique: error guessing. The failures that matter on a flyer are a misread
number and a line tesseract drops entirely; both must reach the person as a
question with a crop, never vanish.
"""
import json
from types import SimpleNamespace

import pytest
from conftest import draw_flyer, needs_tesseract

from worshipdeck import cli
from worshipdeck import flyer as F

pytestmark = needs_tesseract


@pytest.fixture
def flyer_img(tmp_path):
    return draw_flyer(tmp_path / "flyer.png",
                      ["IGLESIA AMIGOS", "Himno 64", "Himno 83", "Al estar ante Ti"],
                      blurred={"Himno 83"})


def test_clear_lines_are_read_top_to_bottom(flyer_img):
    read = [line for line in F.ocr_lines(flyer_img) if line["text"]]
    assert [line["text"] for line in read] == ["IGLESIA AMIGOS", "Himno 64", "Al estar ante Ti"]
    assert all(line["conf"] >= F.MIN_CONF for line in read)


def test_an_unreadable_line_is_still_reported_where_it_is(flyer_img):
    lines = F.ocr_lines(flyer_img)
    y_blurred = 60 + 140 * 2  # third line in draw_flyer
    doubtful = [line for line in lines if line["conf"] < F.MIN_CONF]
    assert doubtful, "the blurred line vanished: nobody would be asked about it"
    assert any(line["box"][1] <= y_blurred + 110 and line["box"][3] >= y_blurred for line in doubtful)


def run_cli(monkeypatch, answers, *argv):
    """cli.main with a fake terminal: isatty() is True and input() pops `answers`."""
    asked = []
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=lambda *a, **k: None))  # no Preview

    def fake_input(prompt=""):
        asked.append(prompt)
        return answers.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)
    assert cli.main(list(argv)) == 0
    return asked


def test_cli_asks_with_a_crop_and_uses_the_answer(monkeypatch, tmp_path, flyer_img):
    spec_path, crops = tmp_path / "spec.json", tmp_path / "dudas"
    asked = run_cli(monkeypatch, ["-", "Himno 83"], "parse", str(flyer_img),
                    "-o", str(spec_path), "--crops", str(crops), "--output", "X.pptx")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert len(asked) == 2  # church name, then the blurred line
    assert sorted(p.name for p in crops.iterdir()) == ["01.png", "02.png"]
    assert [i.get("himno") or i.get("key") for i in spec["items"][1:]] == [64, 83, "al-estar-ante-ti"]
    assert "_pendientes" not in spec


def test_cli_without_a_terminal_lists_doubts_with_crops(monkeypatch, tmp_path, flyer_img, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    crops = tmp_path / "dudas"
    assert cli.main(["parse", str(flyer_img), "--crops", str(crops), "--output", "X.pptx"]) == 0
    out = capsys.readouterr()
    spec = json.loads(out.out)
    pend = spec["_pendientes"]
    assert {p["text"] for p in pend} == {"IGLESIA AMIGOS", ""}
    assert all((crops / p["crop"].split("/")[-1]).exists() for p in pend)
    assert "texto que el OCR no leyó" in out.err
