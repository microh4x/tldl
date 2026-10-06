import json
from pathlib import Path

from tldl import clean, cli, render, vtt
from tldl.transcribe import Stopped
from tldl.vtt import Cue

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.youtube.com/watch?v=oGjuESv8wRs"


def _cues(*texts: str) -> list[Cue]:
    return [Cue(i, i + 1, [t]) for i, t in enumerate(texts)]


def test_stdout_holds_only_the_transcript(capsys):
    assert cli.main([URL]) == 0

    out, err = capsys.readouterr()
    title = json.loads((FIXTURES / "oGjuESv8wRs.info.json").read_text())["title"]
    cues = vtt.parse((FIXTURES / "oGjuESv8wRs.de.vtt").read_text())
    header = f"# {title} | Tim Pritlove | youtube captions (de, manual) | {URL}"
    assert out == render.render(clean.captions(cues), 30, header)
    assert "caption track de (manual)" in err


def test_subs_without_a_matching_track_exits_1(capsys):
    assert cli.main([URL, "--source", "subs", "--sub-lang", "zz"]) == 1

    out, err = capsys.readouterr()
    assert out == ""
    assert "no zz track" in err


def test_local_file_goes_to_whisper_and_collapses_loops(tmp_path, capsys):
    audio = tmp_path / "talk.mp3"
    audio.write_bytes(b"")
    calls = []

    def transcribe(path, model, lang, allow_download):
        calls.append(path)
        return _cues("A", "A", "B", "B", "B", "C"), "de", 0.99

    assert cli.main([str(audio)], transcribe=transcribe) == 0

    out, _ = capsys.readouterr()
    assert out == "# talk | whisper small (de, p=0.99) | talk.mp3\n\n[00:00] A A B C\n"
    assert calls == [audio]


def test_ctrl_c_prints_partial_cues_without_header(tmp_path, capsys):
    audio = tmp_path / "talk.mp3"
    audio.write_bytes(b"")

    def transcribe(path, model, lang, allow_download):
        raise Stopped(_cues("A", "B"), 65.0)

    assert cli.main([str(audio)], transcribe=transcribe) == 130

    out, _ = capsys.readouterr()
    assert out == "[00:00] A B\n\n[... stopped at 01:05]\n"
    assert not (tmp_path / "cache").exists()


def test_second_run_of_a_renamed_file_comes_from_the_cache(tmp_path, capsys):
    audio = tmp_path / "talk.mp3"
    audio.write_bytes(b"same audio")
    calls = []

    def transcribe(path, model, lang, allow_download):
        calls.append(path)
        return [Cue(0, 1, ["A"]), Cue(40, 41, ["B"])], "de", 0.99

    assert cli.main([str(audio)], transcribe=transcribe) == 0
    moved = audio.rename(tmp_path / "moved.mp3")
    capsys.readouterr()
    assert cli.main([str(moved), "--interval", "60"], transcribe=transcribe) == 0

    out, _ = capsys.readouterr()
    assert out == "# moved | whisper small (de, p=0.99) | moved.mp3\n\n[00:00] A B\n"
    assert calls == [audio]


def test_youtube_without_a_matching_track_falls_back_to_whisper(capsys):
    calls = []

    def transcribe(path, model, lang, allow_download):
        calls.append(path.name)
        return _cues("A"), "en", 0.99

    assert cli.main([URL, "--sub-lang", "zz"], transcribe=transcribe) == 0

    out, err = capsys.readouterr()
    title = json.loads((FIXTURES / "oGjuESv8wRs.info.json").read_text())["title"]
    head = f"# {title} | Tim Pritlove | youtube whisper small (en, p=0.99) | {URL}"
    assert out == f"{head}\n\n[00:00] A\n"
    assert calls == ["oGjuESv8wRs.mp3"]
    assert "falling back to Whisper" in err
