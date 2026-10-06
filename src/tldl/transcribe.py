import logging
import time
from pathlib import Path

from faster_whisper import WhisperModel, utils

from tldl.vtt import Cue

log = logging.getLogger(__name__)

# Realtime factor for small/int8 on the 16-core dev laptop (U10); re-measure elsewhere.
SPEED = 3.6
PROGRESS_EVERY_S = 30


class Stopped(Exception):
    def __init__(self, cues: list[Cue], at: float):
        super().__init__(f"stopped at {at:.0f}s")
        self.cues = cues
        self.at = at


class NoModel(Exception):
    def __init__(self, repo: str):
        super().__init__(f"model {repo} is not cached; rerun with --allow-download")
        self.repo = repo


def _load(model: str, allow_download: bool) -> WhisperModel:
    try:
        return WhisperModel(
            model, device="cpu", compute_type="int8", local_files_only=True
        )
    except FileNotFoundError:
        # huggingface_hub's LocalEntryNotFoundError subclasses FileNotFoundError (U14).
        if not allow_download:
            raise NoModel(utils._MODELS.get(model, model)) from None
    log.info("downloading model %s", model)
    return WhisperModel(model, device="cpu", compute_type="int8")


def run(
    path: Path, model: str, lang: str | None, allow_download: bool
) -> tuple[list[Cue], str, float]:
    segments, info = _load(model, allow_download).transcribe(
        str(path),
        language=lang,
        task="transcribe",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    log.info(
        "audio %.1f min, estimate %.1f min",
        info.duration / 60,
        info.duration / SPEED / 60,
    )
    log.info("language %s (p=%.2f)", info.language, info.language_probability)
    if lang is None and info.language_probability < 0.8:
        log.warning("language detection is unsure; set --lang if it is wrong")
    cues: list[Cue] = []
    last = time.monotonic()
    try:
        for seg in segments:
            if text := " ".join(seg.text.split()):
                cues.append(Cue(seg.start, seg.end, [text]))
            if time.monotonic() - last >= PROGRESS_EVERY_S:
                last = time.monotonic()
                log.info("at %.0f of %.0f min", seg.end / 60, info.duration / 60)
    except KeyboardInterrupt:
        raise Stopped(cues, cues[-1].end if cues else 0.0) from None
    return cues, info.language, info.language_probability
