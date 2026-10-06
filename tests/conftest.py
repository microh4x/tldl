import shlex
import sys
from pathlib import Path

import pytest

FAKE = Path(__file__).parent / "fake_ytdlp.py"


@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("TLDL_YTDLP", shlex.join([sys.executable, str(FAKE)]))
