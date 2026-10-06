import argparse
import json
import logging
import os
import shlex
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

from tldl import clean, render, tracks, transcribe, vtt, ytdlp
from tldl.transcribe import NoModel, Stopped

log = logging.getLogger(__name__)


def _interval(s: str) -> int:
    n = int(s)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tldl", description="Print a condensed transcript of a URL or audio file."
    )
    p.add_argument("input", metavar="INPUT", help="http(s) URL or local audio file")
    p.add_argument("--source", choices=["auto", "subs", "whisper"], default="auto")
    p.add_argument(
        "--sub-lang", default="auto", help="caption language, e.g. en, de-DE"
    )
    p.add_argument("--allow-translated", action="store_true")
    p.add_argument("--lang", help="Whisper language; default auto-detect")
    p.add_argument("--model", default="small", help="faster-whisper model")
    p.add_argument(
        "--allow-download", action="store_true", help="fetch a missing model"
    )
    p.add_argument("--interval", type=_interval, default=30, help="seconds per block")
    p.add_argument("--no-header", action="store_true")
    p.add_argument(
        "--ytdlp-cmd",
        type=shlex.split,
        default=os.environ.get("TLDL_YTDLP", "yt-dlp"),
        help="yt-dlp command, e.g. 'uvx yt-dlp@latest' (env TLDL_YTDLP)",
    )
    p.add_argument("--list-subs", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"tldl {version('tldl')}")
    return p


def _captions(url: str, opts: argparse.Namespace, tmp: Path) -> tuple[list, dict]:
    info = ytdlp.info(opts.ytdlp_cmd, url)
    info_path = tmp / "info.json"
    info_path.write_text(json.dumps(info))
    spoken = info.get("language")
    lang = opts.sub_lang
    if lang == "auto":
        lang = tracks.primary(spoken) if spoken else "en"
        log.info("caption language %s from %s", lang, spoken or "default")
    elif spoken and tracks.primary(lang) != tracks.primary(spoken):
        log.warning("--sub-lang %s differs from the video language %s", lang, spoken)
    track, others = tracks.select_track(info, lang, opts.allow_translated)
    if others:
        log.warning(
            "other %s tracks: %s",
            lang,
            ", ".join(
                f"{t.key} (--sub-lang {t.key.removesuffix('-orig')})" for t in others
            ),
        )
    log.info("caption track %s (%s)", track.key, track.kind)
    path = ytdlp.captions(opts.ytdlp_cmd, info_path, track, tmp)
    auto = info.get("automatic_captions") or {}
    meta = {
        "url": url,
        "id": info.get("id"),
        "title": info.get("title"),
        "duration_s": info.get("duration"),
        "source": "captions",
        "auto_fallback": None,
        "captions": {
            "track": track.key,
            "kind": track.kind,
            "info_language": spoken,
            "available": {
                "manual": list(info.get("subtitles") or {}),
                "auto_orig": [k for k in auto if k.endswith("-orig")],
                "auto_translated_count": sum(not k.endswith("-orig") for k in auto),
            },
        },
    }
    return vtt.parse(path.read_text(encoding="utf-8")), meta


def _whisper(source: str, opts: argparse.Namespace, tmp: Path, transcribe) -> tuple:
    if _is_url(source):
        path, info = ytdlp.audio(opts.ytdlp_cmd, source, tmp)
        meta = {"url": source, "id": info.get("id"), "title": info.get("title")}
        meta["duration_s"] = info.get("duration")
    else:
        path = Path(source)
        meta = {"url": path.name, "id": None, "title": path.stem, "duration_s": None}
    cues, lang, prob = transcribe(path, opts.model, opts.lang, opts.allow_download)
    meta |= {
        "source": "whisper",
        "auto_fallback": None,
        "whisper": {
            "model": opts.model,
            "language": lang,
            "language_probability": prob,
        },
    }
    return cues, meta


def run(source: str, opts: argparse.Namespace, transcribe) -> tuple[list, dict]:
    with tempfile.TemporaryDirectory(prefix="tldl-") as tmp:
        captions = _is_url(source) and (
            opts.source == "subs" or (opts.source == "auto" and ytdlp.youtube(source))
        )
        if not captions:
            return _whisper(source, opts, Path(tmp), transcribe)
        try:
            return _captions(source, opts, Path(tmp))
        except tracks.NoTrack as e:
            if opts.source == "subs":
                raise
            log.warning("%s; falling back to Whisper", e)
            cues, meta = _whisper(source, opts, Path(tmp), transcribe)
            meta["auto_fallback"] = {"from": "captions", "reason": str(e)}
            return cues, meta


def _write(text: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except BrokenPipeError:
        # Python flushes stdout again at exit; point it at devnull to keep that quiet.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def main(argv: list[str] | None = None, transcribe=transcribe.run) -> int:
    p = parser()
    opts = p.parse_args(argv)
    if not _is_url(opts.input):
        if not Path(opts.input).is_file():
            p.error(f"{opts.input} is neither an http(s) URL nor a file")
        if opts.source == "subs":
            p.error("--source subs needs a URL")
    logging.basicConfig(
        level=logging.DEBUG if opts.verbose else logging.INFO,
        format="tldl: %(message)s",
        force=True,
    )
    # faster-whisper repeats our duration and language lines at INFO.
    logging.getLogger("faster_whisper").setLevel(
        logging.DEBUG if opts.verbose else logging.WARNING
    )
    try:
        if opts.list_subs:
            info = ytdlp.info(opts.ytdlp_cmd, opts.input)
            _write(f"language: {info.get('language')}; {tracks.summary(info)}\n")
            return 0
        cues, meta = run(opts.input, opts, transcribe)
    except Stopped as e:
        cues = clean.whisper(e.cues)
        _write(
            (render.render(cues, opts.interval) + "\n" if cues else "")
            + render.stopped(e.at)
        )
        return 130
    except (tracks.NoTrack, ytdlp.Failed, NoModel, OSError) as e:
        log.error("%s", e)
        return 1
    except KeyboardInterrupt:
        return 130
    head = None if opts.no_header else render.header(meta)
    tidy = clean.captions if meta["source"] == "captions" else clean.whisper
    _write(render.render(tidy(cues), opts.interval, head))
    return 0
