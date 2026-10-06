import json
import logging
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from tldl.tracks import Track

log = logging.getLogger(__name__)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class Failed(Exception):
    pass


def youtube(url: str) -> bool:
    return (urlsplit(url).hostname or "") in YOUTUBE_HOSTS


def _run(cmd: list[str], args: list[str]) -> str:
    log.debug("running %s", [*cmd, *args])
    try:
        p = subprocess.run([*cmd, *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise Failed(f"{cmd[0]} not found; set --ytdlp-cmd or TLDL_YTDLP") from None
    if p.returncode:
        last = (p.stderr.strip().splitlines() or ["no output"])[-1]
        raise Failed(f"yt-dlp exited {p.returncode}: {last}")
    return p.stdout


def info(cmd: list[str], url: str) -> dict:
    data = json.loads(_run(cmd, ["--no-playlist", "-J", "--", url]))
    if data.get("_type") == "playlist":
        raise Failed(f"{url} is a playlist; pass a single video URL")
    return data


def captions(cmd: list[str], info_path: Path, track: Track, tmpdir: Path) -> Path:
    write = "--write-subs" if track.kind == "manual" else "--write-auto-subs"
    # --sub-langs takes regexes, so anchor the key to match it alone.
    _run(
        cmd,
        [
            "--load-info-json", str(info_path), "--skip-download", write,
            "--sub-langs", f"^{re.escape(track.key)}$", "--sub-format", "vtt",
            "-o", "%(id)s.%(ext)s", "--paths", str(tmpdir),
        ],
    )  # fmt: skip
    found = list(Path(tmpdir).glob("*.vtt"))
    if len(found) != 1:
        raise Failed(f"expected one .vtt for {track.key}, yt-dlp wrote {len(found)}")
    return found[0]
