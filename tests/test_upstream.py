import os

import pytest

from tldl import clean, cli

pytestmark = pytest.mark.skipif(
    os.environ.get("TLDL_NETWORK") != "1", reason="set TLDL_NETWORK=1 to run"
)


def test_real_ytdlp_still_gets_the_original_track(monkeypatch):
    monkeypatch.delenv("TLDL_YTDLP")
    opts = cli.parser().parse_args(["https://www.youtube.com/watch?v=6toXnSudT7o"])

    cues, meta = cli.run(opts.input, opts, None)

    assert meta["captions"]["track"] == "en-orig"
    assert len(clean.captions(cues)) >= 600
