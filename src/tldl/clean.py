import logging
from itertools import groupby

from tldl.vtt import Cue

log = logging.getLogger(__name__)


def captions(cues: list[Cue]) -> list[Cue]:
    """Drop lines repeated from the previous cue, the rolling-caption pattern."""
    out, prev, removed = [], [], 0
    for cue in cues:
        lines = [line for line in cue.lines if line not in prev]
        removed += len(cue.lines) - len(lines)
        prev = cue.lines
        if lines:
            out.append(Cue(cue.start, cue.end, lines))
    log.info(
        "cleanup: removed %d repeated lines, %d of %d cues left",
        removed,
        len(out),
        len(cues),
    )
    return out


def whisper(cues: list[Cue]) -> list[Cue]:
    """Collapse runs of 3 or more identical segments, Whisper's loop failure."""
    out: list[Cue] = []
    for _, group in groupby(
        cues, lambda c: " ".join(" ".join(c.lines).casefold().split())
    ):
        run = list(group)
        if len(run) >= 3:
            log.info("cleanup: collapsed %d repeats at %.0fs", len(run), run[0].start)
            run = run[:1]
        out += run
    log.info("cleanup: %d of %d segments left", len(out), len(cues))
    return out
