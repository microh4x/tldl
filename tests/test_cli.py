import json
from pathlib import Path

from tldl import clean, cli, render, vtt

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.youtube.com/watch?v=6toXnSudT7o"


def test_stdout_holds_only_the_transcript(capsys):
    assert cli.main([URL]) == 0

    out, err = capsys.readouterr()
    title = json.loads((FIXTURES / "6toXnSudT7o.info.json").read_text())["title"]
    cues = vtt.parse((FIXTURES / "6toXnSudT7o.en-orig.vtt").read_text())
    header = f"# {title} | youtube captions (en-orig, auto) | {URL}"
    assert out == render.render(clean.captions(cues), 30, header)
    assert "en-orig" in err


def test_subs_without_a_matching_track_exits_1(capsys):
    assert cli.main([URL, "--source", "subs", "--sub-lang", "zz"]) == 1

    out, err = capsys.readouterr()
    assert out == ""
    assert "no zz track" in err
