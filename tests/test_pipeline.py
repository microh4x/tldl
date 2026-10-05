import re
from pathlib import Path

from tldl import clean, render, vtt

FIXTURE = Path(__file__).parent / "fixtures" / "6toXnSudT7o.en-orig.vtt"


def test_fixture_renders_each_line_once_in_order():
    cues = vtt.parse(FIXTURE.read_text(encoding="utf-8"))
    # The new line of each rolling caption is the last line of a cue longer than 10 ms.
    normal = [c for c in cues if c.end - c.start > 0.02]
    # Spec 6.3 accepts losing a line that repeats the one above it in the same cue (28:03).
    expected = [c.lines[-1] for c in normal if c.lines[-2:] != [c.lines[-1]] * 2]
    assert len(normal) == 662 and len(expected) == 661
    assert expected[0] == "You join us in deepest, darkest Wales"

    out = render.render(clean.captions(cues), 30)

    assert out.endswith("\n") and not out.endswith("\n\n")
    blocks = out.rstrip("\n").split("\n\n")
    markers = [b.split(" ", 1)[0] for b in blocks]
    assert all(re.fullmatch(r"\[\d\d:\d\d\]", m) for m in markers)
    assert markers == sorted(markers)
    text = " ".join(b.split(" ", 1)[1] for b in blocks)
    assert text == " ".join(expected)
    assert ">>" in text and "&gt;" not in text
