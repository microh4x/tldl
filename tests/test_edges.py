from tldl import clean, render, vtt
from tldl.vtt import Cue


def test_marker_switches_to_hours_within_one_output():
    cues = [Cue(3599, 3600, ["a"]), Cue(3600, 3601, ["b"])]

    assert render.render(cues, 30) == "[59:30] a\n\n[01:00:00] b\n"


def test_a_repeat_with_other_text_between_survives_cleanup():
    cues = [Cue(0, 1, ["Ja."]), Cue(1, 2, ["Nein."]), Cue(2, 3, ["Ja."])]

    for tidy in (clean.captions, clean.whisper):
        assert tidy(cues) == cues


def test_parse_handles_hour_field_identifier_and_cue_settings():
    text = (
        "WEBVTT\nKind: captions\n\n"
        "cue-7\n"
        "01:00:05.000 --> 01:00:07.500 align:start position:0%\n"
        "<c>first</c> line\n"
        "&gt;&gt; second\n"
    )

    assert vtt.parse(text) == [Cue(3605.0, 3607.5, ["first line", ">> second"])]
