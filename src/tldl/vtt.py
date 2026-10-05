import html
import re
from dataclasses import dataclass

TIME = r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})"
TIMING = re.compile(rf"{TIME}\s+-->\s+{TIME}")
TAG = re.compile(r"<[^>]+>")


@dataclass
class Cue:
    start: float
    end: float
    lines: list[str]


def _seconds(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse(text: str) -> list[Cue]:
    cues = []
    blocks = re.split(r"\n{2,}", text.lstrip("\ufeff").replace("\r\n", "\n"))
    for block in blocks:
        lines = block.split("\n")
        # Header, NOTE, STYLE and REGION blocks carry no timing line.
        i = next((i for i, line in enumerate(lines[:2]) if "-->" in line), None)
        m = i is not None and TIMING.match(lines[i].strip())
        if not m:
            continue
        g = m.groups()
        text_lines = [
            " ".join(html.unescape(TAG.sub("", line)).split())
            for line in lines[i + 1 :]
        ]
        cues.append(
            Cue(_seconds(*g[:4]), _seconds(*g[4:]), [t for t in text_lines if t])
        )
    return cues
