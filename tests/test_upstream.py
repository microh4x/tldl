import functools
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tldl import clean, cli

# Read at import, before the conftest fixture swaps in the fake.
REAL_YTDLP = os.environ.get("TLDL_YTDLP", "yt-dlp")

pytestmark = pytest.mark.skipif(
    os.environ.get("TLDL_NETWORK") != "1", reason="set TLDL_NETWORK=1 to run"
)


def test_real_ytdlp_still_gets_the_original_track(monkeypatch):
    monkeypatch.setenv("TLDL_YTDLP", REAL_YTDLP)
    opts = cli.parser().parse_args(["https://www.youtube.com/watch?v=6toXnSudT7o"])

    cues, meta = cli.run(opts.input, opts, None)

    assert meta["captions"]["track"] == "en-orig"
    assert len(clean.captions(cues)) >= 600


def test_real_ytdlp_and_whisper_transcribe_a_served_file(monkeypatch, capsys):
    monkeypatch.setenv("TLDL_YTDLP", REAL_YTDLP)
    handler = functools.partial(
        SimpleHTTPRequestHandler, directory=Path(__file__).parent / "fixtures"
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/sample.mp3"
        assert cli.main([url]) == 0
    finally:
        server.shutdown()

    out = capsys.readouterr().out
    assert out.startswith("# sample | whisper small (en, ")
    assert "signal processing" in out.casefold()
