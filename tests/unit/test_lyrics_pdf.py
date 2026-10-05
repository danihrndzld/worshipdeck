"""Lyrics PDF unit tests: text handling only."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from worshipdeck import lyrics_pdf as L  # noqa: E402


def test_join_continuations_rejoins_screen_breaks():
    assert L.join_continuations(["Mi alma te anhela ", "y tiene sed", "Para ver tu gloria"]) == \
        ["Mi alma te anhela y tiene sed", "Para ver tu gloria"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
