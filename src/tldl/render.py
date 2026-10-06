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
    site = "youtube " if youtube(meta["url"]) else ""
    if meta["source"] == "captions":
        cap = meta["captions"]
        desc = f"captions ({cap['track']}, {cap['kind']})"
    else:
        w = meta["whisper"]
        desc = (
            f"whisper {w['model']} ({w['language']}, p={w['language_probability']:.2f})"
        )
    # Cache entries from before the channel field lack the key.
    channel = f"{meta['channel']} | " if meta.get("channel") else ""
    return f"# {meta['title']} | {channel}{site}{desc} | {meta['url']}"


def stopped(at: float) -> str:
    return f"[... stopped at {_marker(int(at))[1:-1]}]\n"
