from tldl.vtt import Cue
from tldl.ytdlp import youtube


def _marker(t: int) -> str:
    h, rest = divmod(t, 3600)
    m, s = divmod(rest, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]" if h else f"[{m:02d}:{s:02d}]"


def render(cues: list[Cue], interval: int, header: str | None = None) -> str:
    buckets: dict[int, list[str]] = {}
    for cue in cues:
        buckets.setdefault(int(cue.start // interval) * interval, []).extend(cue.lines)
    parts = [header] if header else []
    parts += [f"{_marker(t)} {' '.join(lines)}" for t, lines in sorted(buckets.items())]
    return "\n\n".join(parts) + "\n"


def header(meta: dict) -> str:
    cap = meta["captions"]
    site = "youtube " if youtube(meta["url"]) else ""
    return f"# {meta['title']} | {site}captions ({cap['track']}, {cap['kind']}) | {meta['url']}"
