import re
from pathlib import Path

from tldl import clean, render, vtt

FIXTURE = Path(__file__).parent / "fixtures" / "oGjuESv8wRs.de-orig.vtt"


def test_fixture_renders_each_line_once_in_order():
    cues = vtt.parse(FIXTURE.read_text(encoding="utf-8"))
    # The new line of each rolling caption is the last line of a cue longer than 10 ms.
    normal = [c for c in cues if c.end - c.start > 0.02]
    expected = [c.lines[-1] for c in normal]
    assert len(normal) == 83
    assert expected[0] == "Ich habe mich erinnert an 1980, da waren"

    out = render.render(clean.captions(cues), 30)

    assert out.endswith("\n") and not out.endswith("\n\n")
    blocks = out.rstrip("\n").split("\n\n")
    markers = [b.split(" ", 1)[0] for b in blocks]
    assert all(re.fullmatch(r"\[\d\d:\d\d\]", m) for m in markers)
    assert markers == sorted(markers)
    text = " ".join(b.split(" ", 1)[1] for b in blocks)
    assert text == " ".join(expected)
