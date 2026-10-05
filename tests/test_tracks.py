import json
from pathlib import Path

import pytest

from tldl.tracks import NoTrack, Track, primary, select_track

INFO = json.loads(
    (Path(__file__).parent / "fixtures" / "6toXnSudT7o.info.json").read_text()
)


def test_auto_picks_the_original_language_track():
    track, others = select_track(INFO, primary(INFO["language"]))
    assert track == Track("auto", "en-orig")
    assert others == []


def test_regional_language_picks_its_orig_track():
    assert select_track(INFO, "de")[0] == Track("auto", "de-DE-orig")


def test_translated_track_needs_allow_translated():
    info = {**INFO, "automatic_captions": dict(INFO["automatic_captions"])}
    del info["automatic_captions"]["de-DE-orig"]
    with pytest.raises(NoTrack) as e:
        select_track(info, "de")
    assert "3 translated" in str(e.value)
    assert "--allow-translated" in str(e.value)
    assert select_track(info, "de", allow_translated=True)[0] == Track(
        "auto-translated", "de-DE"
    )
