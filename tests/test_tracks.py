import json
from pathlib import Path

import pytest

from tldl.tracks import NoTrack, Track, primary, select_track

INFO = json.loads(
    (Path(__file__).parent / "fixtures" / "oGjuESv8wRs.info.json").read_text()
)


def test_manual_track_wins_over_the_original_track():
    track, others = select_track(INFO, primary(INFO["language"]))
    assert track == Track("manual", "de")
    assert others == [Track("auto", "de-orig")]


def test_without_manual_tracks_auto_picks_the_original_track():
    track, others = select_track({**INFO, "subtitles": {}}, "de")
    assert track == Track("auto", "de-orig")
    assert others == []


def test_regional_language_picks_its_orig_track():
    vtt = [{"ext": "vtt"}]
    info = {"automatic_captions": {"de-DE-orig": vtt, "en-orig": vtt}}
    assert select_track(info, "de")[0] == Track("auto", "de-DE-orig")


def test_translated_track_needs_allow_translated():
    with pytest.raises(NoTrack) as e:
        select_track(INFO, "en")
    assert "3 translated" in str(e.value)
    assert "--allow-translated" in str(e.value)
    assert select_track(INFO, "en", allow_translated=True)[0] == Track(
        "auto-translated", "en"
    )
