import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from tldl.tracks import Track

log = logging.getLogger(__name__)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class Failed(Exception):
    pass


def youtube(url: str) -> bool:
    return (urlsplit(url).hostname or "") in YOUTUBE_HOSTS


def _run(cmd: list[str], args: list[str], capture: bool = True) -> str:
    log.debug("running %s", [*cmd, *args])
    # Uncaptured, yt-dlp's progress output goes to our stderr.
    out = {"capture_output": True} if capture else {"stdout": sys.stderr}
    try:
        p = subprocess.run([*cmd, *args], text=True, check=False, **out)
    except FileNotFoundError:
        raise Failed(f"{cmd[0]} not found; set --ytdlp-cmd or TLDL_YTDLP") from None
    if p.returncode:
        if not capture:
            raise Failed(f"yt-dlp exited {p.returncode}; see its output above")
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


def audio(cmd: list[str], url: str, tmpdir: Path) -> tuple[Path, dict]:
    args = [
        "--no-playlist", "-f", "bestaudio/best", "--write-info-json",
        "-o", "%(id)s.%(ext)s", "--paths", str(tmpdir), "--", url,
    ]  # fmt: skip
    _run(cmd, args, capture=False)
    infos = list(Path(tmpdir).glob("*.info.json"))
    found = [f for f in Path(tmpdir).iterdir() if f not in infos]
    if len(found) != 1 or len(infos) != 1:
        raise Failed(f"expected one audio file, yt-dlp wrote {len(found)}")
    return found[0], json.loads(infos[0].read_text(encoding="utf-8"))
