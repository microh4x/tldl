import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from tldl.vtt import Cue
from tldl.ytdlp import youtube

log = logging.getLogger(__name__)


def _root() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "tldl"


def canonical_url(url: str) -> str:
    u = urlsplit(url)
    if youtube(url):
        if u.hostname == "youtu.be":
            vid = u.path.strip("/")
        else:
            vid = (parse_qs(u.query).get("v") or [""])[0]
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path, u.query, ""))


def file_url(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return f"file:sha256:{h.hexdigest()[:16]}"


def key(**fields) -> str:
    data = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def load(k: str) -> tuple[list[Cue], dict] | None:
    d = _root() / k
    # meta.json is written last, so its presence means the entry is complete.
    if not (d / "meta.json").is_file():
        return None
    log.info("cached in %s", d)
    cues = json.loads((d / "cues.json").read_text(encoding="utf-8"))
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    return [Cue(*c) for c in cues], meta


def store(k: str, cues: list[Cue], meta: dict, raw_vtt: bytes | None = None) -> None:
    d = _root() / k
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").unlink(missing_ok=True)
    if raw_vtt is not None:
        (d / "raw.vtt").write_bytes(raw_vtt)
    cue_data = [[c.start, c.end, c.lines] for c in cues]
    (d / "cues.json").write_text(json.dumps(cue_data), encoding="utf-8")
    meta = {
        "tool": {"name": "tldl", "version": version("tldl")},
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **meta,
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    log.info("saved to %s", d)
