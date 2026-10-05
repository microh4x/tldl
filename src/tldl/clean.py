import logging

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
