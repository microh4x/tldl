# tldl: implementation specification

Date: 2026-10-05. Status: ready for implementation; open questions have working defaults. Audience: Claude Code (implementer) and the owner.
Supersedes: `261005-url2vtt-spec-v03.md` (renamed from url2vtt; v03 kept for comparison).

**Changes in v04:** renamed to `tldl`; local audio files as input; partial output on Ctrl-C; test plan rebuilt as about 12 vertical-slice tests with a fake yt-dlp script and an injected transcriber; step 1 and part of step 2 verified (section 11); project lives at `/work/tldl` (host `/home/ja/projects/tldw/tldl`), model cache at `/work/hf-cache/hub`.

**Changes in v03 (scope cut after review):**

- Removed the interactive prompt system (v02 section 5.5, decisions D1 to D9, `prompt.py`, exit code 7, flags `--no-input`, `--choose-track`, `--confirm-over`, `--min-lang-prob`). Every case now resolves to a deterministic default plus a stderr warning that names the flag to rerun with.
- Removed the native downloader (`--downloader`, `--max-mb`, `native.py`). It returns only if step 1 shows yt-dlp fails on cre.fm.
- Removed `--out-dir` with its versioned files, slug and meta writer. Redirect stdout instead; raw data and meta live in the cache directory, whose path goes to stderr.
- Removed `--offline` (local-first loading already means no download by default), `--interval 0`, `--cpu-threads`, `--model-dir`, `--loop-threshold`, `--keep-audio`.
- Exit codes reduced to 0, 1, 2, 130.
- `--sub-lang` defaults to `auto`: the video's own language, else `en`.
- Audio download drops `-x`, so ffmpeg is no longer a prerequisite (U6).
- The caption download reuses the saved info JSON, so the captions path makes one metadata request instead of two (U16).
- Rolling-caption cleanup confirmed against the real fixture (U4); a tag-based rule was tried and rejected (6.3).
- Cache key uses the source actually used, not the requested one.

Confidence labels: **decided** (agreed or my default, override welcome), **verified** (seen in docs or in the owner's data), **unverified** (listed in section 11 with how to check).

## 1. Purpose and scope

`tldl <url-or-file>` turns a URL or a local audio file into a transcript to paste into Claude web for summarising a long (about 2 h) episode.

- **Two sources:** YouTube captions via yt-dlp (fast, no audio), or Whisper `small` on CPU over downloaded audio or a local file.
- **Output:** a condensed transcript on stdout, one `[MM:SS] text` block per 30 s interval plus one header line. Logs and warnings go to stderr, so the output pipes cleanly to a file or clipboard tool.
- **No prompts:** the tool never reads stdin. When a choice is ambiguous, it takes the documented default and logs a warning naming the alternatives and the flag that selects them.
- **Why condensed:** a VTT spends a timing line on every cue. Rough estimate for 2 h: 1,200 to 2,400 cues at 15 to 20 tokens each, so 20k to 50k tokens of timestamps, about as much as the spoken text (about 25k tokens in English, more in German). The 30 s format costs about 1k to 1.5k tokens. Estimates, not measured (U12).
- **Out of scope:** LLM calls, diarization, web UI, Docker, splitting into parts, multiple URLs per run, translation, GPU, RSS/feed parsing, interactive prompts, a non-yt-dlp downloader, file output beyond stdout. Section 14 lists the triggers for adding the deferred ones.

## 2. Decisions

| Topic | Decision | Status |
|---|---|---|
| Interface | CLI only; transcript on stdout | decided |
| Engine | faster-whisper, model `small`, `int8`, CPU, VAD on | decided |
| Models | Shared with the owner's existing install through the default Hugging Face cache; loaded local-first | decided |
| Packaging | uv project, src layout, committed `uv.lock`, no Docker | decided |
| Sources | `--source {auto,subs,whisper}`, default `auto` (captions first for YouTube) | decided |
| yt-dlp | External prerequisite called as a subprocess through a configurable command, default `yt-dlp` on PATH | my default (Q2) |
| Output format | Follows the owner's `clean_vtt.py`: `[MM:SS] text`, 30 s, blank line between intervals; adds one header line | decided |
| Default `--sub-lang` | `auto`: primary of `info["language"]`, else `en` | my default (Q3) |
| Ambiguity | Deterministic default plus warning; never prompt | decided |
| Name | `tldl` ("too long; didn't listen"), project dir `tldw/tldl` | decided |

## 3. Environment

- Linux; home `/home/ja`. CPU only; 16 cores, 27 GiB RAM (Q5). The Claude Code sandbox runs on the same laptop with HOME `/claude`, Python 3.10.12 (yt-dlp warns that 3.10 is deprecated), and no cached faster-whisper model.
- Existing model, verified from the owner's listing: `~/.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120/` containing `config.json`, `model.bin`, `tokenizer.json`, `vocabulary.txt`. This is the multilingual CTranslate2 `small`. The `.pt` files in `~/.cache/whisper/` (openai-whisper) and `ggml-small.bin` under `~/.local/share/com.bradenwong.whispering/` (whisper.cpp) use other formats and are not used.
- External prerequisites (not managed by the project lock): `uv` and `yt-dlp`. Install yt-dlp as a uv tool with its own Python, a JavaScript runtime and the impersonation library: `uv tool install --python 3.12 --with deno 'yt-dlp[default,curl-cffi]'`; update with `uv tool upgrade yt-dlp`, which keeps these options. Reasons: yt-dlp has deprecated Python 3.10; YouTube needs a JS runtime (`deno` from PyPI, used through the `yt-dlp-ejs` package in `[default]`) or some formats go missing; `curl-cffi` lets yt-dlp impersonate a browser on sites that require it. Verified: `yt-dlp -v` reports `JS runtimes: deno-2.9.7` and `--list-impersonate-targets` lists curl_cffi targets. In the sandbox, `/usr/local/bin/yt-dlp` is broken, so use `TLDL_YTDLP="uvx --python 3.12 --with deno --from yt-dlp[default,curl-cffi]@latest yt-dlp"`. ffmpeg is not required if U6 holds; if it fails, add `-x` back and list ffmpeg here.
- Model sharing rule: the tool must not write into `~/.cache/huggingface` unless `--allow-download` is given. The local-first load means an already cached model never triggers a Hub check, and a newer upstream revision is never pulled implicitly.

## 4. CLI contract

`tldl INPUT [options]`

| Flag | Default | Meaning |
|---|---|---|
| `INPUT` | required | An `http`/`https` URL, or a path to an existing local audio file. A local file always goes to Whisper; `--source subs` with a file is a usage error |
| `--source {auto,subs,whisper}` | `auto` | `auto`: YouTube hosts try captions first, others go to Whisper. `subs`: force captions (any site yt-dlp supports), fail if none. `whisper`: never try captions |
| `--sub-lang LANG` | `auto` | Caption language (`en`, `de`, `de-DE`). `auto` uses the video's language, else `en` |
| `--allow-translated` | off | Permit machine-translated caption tracks; the header marks them |
| `--lang LANG` | auto-detect | Whisper language. Independent of `--sub-lang` |
| `--model NAME` | `small` | faster-whisper model name |
| `--allow-download` | off | Permit downloading a model that is not cached |
| `--interval N` | `30` | Seconds per block, at least 1 |
| `--no-header` | off | Drop the header line |
| `--refresh` | off | Ignore the cache |
| `--ytdlp-cmd CMD` | env `TLDL_YTDLP`, else `yt-dlp` | Split with `shlex`; for example `uvx yt-dlp@latest` |
| `--list-subs` | off | Print a summary of caption tracks to stdout and exit 0 |
| `-v, --verbose` | off | DEBUG logging |
| `--version` | | |

**stdout/stderr:** stdout carries only the transcript (or the `--list-subs` summary), UTF-8 (reconfigure stdout explicitly), tolerating `BrokenPipeError`. Everything else (logs, timings, warnings, chosen caption track, cache directory path) goes to stderr. Temp files live in a `tempfile.TemporaryDirectory`, so Ctrl-C cleans them up; exit 130. Ctrl-C during transcription first renders the cues done so far to stdout, without a header, followed by a line `[... stopped at MM:SS]`; a partial result is not cached, and there is no resume. Ctrl-C before the first segment (download, model load, language detection) prints nothing to stdout.

**Exit codes:** 0 ok, 1 error (the message on stderr says what failed and what to try), 2 usage error, 130 Ctrl-C.

## 5. Pipeline

```
url  -> canonicalise -> cache lookup (unless --refresh)
file -> SHA-256      -> cache lookup (unless --refresh)
   captions: info JSON -> select_track -> track VTT (reusing info JSON) -> parse -> cues
   whisper : yt-dlp audio, or the local file -> faster-whisper -> cues
cues (raw) -> cache -> clean -> render -> stdout
```

### 5.1 Source selection

- YouTube hosts: `youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`. `auto` tries captions there; if no acceptable track exists, it logs a warning naming what was available and falls through to Whisper, and records `auto_fallback` in the meta. Other hosts go straight to Whisper (no wasted yt-dlp call).
- Always pass `--no-playlist` to yt-dlp. If yt-dlp returns a playlist anyway, exit 1 with a clear message.
- `--source subs` with no acceptable track exits 1 with the same summary of available tracks.

### 5.2 Caption flow

Why our code selects the track: the owner's real `--list-subs` output (video `6toXnSudT7o`, verified) shows "has no subtitles" (only automatic captions), `vtt` on every track, and **20 languages carrying `-orig`** (bn, nl-NL, en, fr-FR, de-DE, iw, hi, id, it, ja, ko, ml, pl, pt-BR, pa, ru, es-US, ta, te, uk), plus translated tracks. For regional languages both `X-orig` and translated `X` exist (`de-DE-orig` and `de-DE`). So `-orig` alone does not identify the spoken language, and a plain language code can return a machine translation. Verified explanation (U3): the video has 20 auto-dubbed audio tracks, each with its own ASR (automatic speech recognition) track, and `info["language"]` (`en-US`) names the original.

1. **Metadata call:** `<ytdlp> --no-playlist -J -- URL`, parse JSON from stdout, save it to the temp dir. Expected keys: `subtitles` (manual), `automatic_captions`, `language`, `title`, `id`, `duration` (U1, U15).
2. **Resolve the language:** with `--sub-lang auto`, use `primary(info["language"])` if present, else `en`; log which one and why. `primary(key)` is the lower-cased text before the first `-`.
3. **`select_track(info, lang, allow_translated=False)`** (pure, in `tracks.py`):
   1. Manual: keys in `subtitles` (excluding `live_chat`) whose primary equals `primary(lang)`; exact key match first, then alphabetical.
   2. Automatic original: keys in `automatic_captions` ending in `-orig` whose primary (after removing `-orig`) equals `primary(lang)`; exact match first, then alphabetical.
   3. Automatic translated (plain keys with matching primary, no `-orig`): only with `allow_translated`; kind `auto-translated`.
   4. The chosen track must offer an entry with `ext == "vtt"`; skip candidates without one.
   5. Otherwise raise `NoTrack` carrying a summary: manual keys, `-orig` keys, count of translated keys.

   Returns `Track(kind: manual|auto|auto-translated, key: str)` plus the other candidates. When there is more than one candidate, the caller logs a warning listing them and the `--sub-lang` value that selects each. When an explicit `--sub-lang` disagrees with `info["language"]`, log a warning.
4. **Download call:** `<ytdlp> --load-info-json <saved.json> --skip-download (--write-subs | --write-auto-subs) --sub-langs '^<re.escape(key)>$' --sub-format vtt -o '%(id)s.%(ext)s' --paths <tmpdir>`. `--sub-langs` entries are regexes (verified), hence the anchors. Expect exactly one `.vtt`; none or several exits 1. Subtitle URLs in the info JSON can expire, but the two calls run seconds apart (U16).
5. Parse, clean, continue. The chosen track key goes to stderr, the header line and the meta.

`--list-subs` runs step 1 only and prints: `language`, manual keys, `-orig` keys, count of translated keys. It never prints the raw listing.

### 5.3 Whisper flow

- **Audio:** a local file is used as is. A URL goes through `<ytdlp> --no-playlist -f bestaudio/best --write-info-json -o '%(id)s.%(ext)s' --paths <tmpdir> -- URL`. No `-x`: faster-whisper decodes through PyAV, which bundles its own ffmpeg libraries (U6). On auto-dubbed YouTube videos the default selection picks the original-language audio (U3). This call does not capture output: yt-dlp's stdout (where it prints progress) goes to our stderr, so a long download shows progress and keeps stdout clean; on failure the error says to see yt-dlp's output above. The audio file is the one file in the temp dir that is not `.info.json`. The audio goes into its own subdirectory, because the `auto` fallback runs it after the captions step has written to the temp dir. The metadata and caption calls keep capturing output. An offline test covers the `auto` fallback through the fake yt-dlp; an opt-in test runs the real yt-dlp against a local HTTP server.
- **Model (local-first):** `WhisperModel(model, device="cpu", compute_type="int8", local_files_only=True)`. If the model is not cached, exit 1 with the repo name and "rerun with `--allow-download`". With `--allow-download`, retry with `local_files_only=False`. The missing-model exception (`LocalEntryNotFoundError`, U14) subclasses `FileNotFoundError`, so catch that and raise `NoModel`, without importing `huggingface_hub`.
- **Before transcribing:** log the audio duration (`info.duration`) and an estimated run time from a constant speed factor (3.5x realtime from the 1-minute measurement; re-measure in acceptance, U10). Ctrl-C is the way out of a job that is too long (see section 4 for partial output).
- **Transcribe:** `language=lang` (None means auto-detect), `task="transcribe"`, `beam_size=5`, `vad_filter=True`, `condition_on_previous_text=False`. `transcribe()` detects the language before it returns (U13): log `info.language` and `info.language_probability` immediately; if the probability is below 0.8 and `--lang` is not given, add a warning that names `--lang`. `segments` is a lazy generator: iterate to completion and log progress (position against `info.duration`) to stderr every 30 s of wall time.

## 6. Data and algorithms

### 6.1 Cue

`Cue(start: float, end: float, lines: list[str])`, seconds as floats, each line single-line and stripped. One type serves both sources: a caption cue keeps its lines, because cleanup compares neighbouring cues; a Whisper segment becomes a cue with one line. The cache stores cues, so cue boundaries survive until cleanup.

### 6.2 VTT parsing

Accept a BOM and a `WEBVTT` header (with optional text and `Kind:`/`Language:` lines). Blocks are separated by blank lines; ignore `NOTE`, `STYLE` and `REGION` blocks. A cue block is: optional identifier line (any line without `-->`), a timing line, then text lines. Timings match `(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})` for both ends (hour optional); cue settings after the end time are ignored. Identifiers are recognised structurally, never by "is a number".

Per text line: strip tags with `<[^>]+>`, apply `html.unescape`, normalise all whitespace including NBSP, drop empty lines. Keep bracketed cues such as `[music]` and the `>>` speaker-change marker (encoded as `&gt;&gt;` in the file). The parser keeps cue boundaries (a list of lines per cue), because cleanup compares neighbouring cues.

### 6.3 Cleanup rules (run at output time, on cached raw cues)

Invariant: each spoken phrase appears once, in order; legitimate repeats separated by other text are never removed; nothing is deduplicated globally.

- **Automatic captions (rolling captions):** verified structure (U4, `6toXnSudT7o` en-orig, 1,323 cues): cues alternate between a normal cue and a 10 ms cue. A normal cue holds the previous line plus one new line; a 10 ms cue repeats the new line alone. Rule: for each cue, remove lines that also occur in the immediately preceding cue, then drop cues left empty. On the fixture this yields 661 lines from 662 normal cues; the one loss is the cue at 28:03 that reads "Heat." twice (the accepted behaviour below). Rejected: keeping only lines with inline word-timing tags, because short new lines ("lockers.", "[music]") carry no tags; that rule lost 92 of 661 lines. Manual tracks are left untouched.
- **Whisper source:** collapse runs of 3 or more consecutive identical segments (compared case-folded and whitespace-normalised) to one.
- Both: log how many cues were removed and the first timestamp of each removal. Raw data stays in the cache.
- Not done: merging tiny cues, rewriting text, punctuation repair.

Accepted behaviour: a genuine immediate repeat of a line is indistinguishable from the rolling pattern and gets dropped. This is logged.

### 6.4 Rendering

- Header (unless `--no-header`): `# {title} | {channel} | {source_desc} | {url}` then a blank line. `channel` is yt-dlp's `channel`, else `uploader`; the part is left out when neither is set (local files, cre.fm). For a local file, `title` is the file name without extension and `url` is the file name. `source_desc` examples: `youtube captions (de-DE-orig, auto)`, `youtube captions (en, manual)`, `whisper small (de, p=0.99)`, `youtube captions (en, auto-translated)`.
- Bucket cleaned cues by `floor(start / interval) * interval`. For each non-empty bucket in ascending order: marker, a space, all cue lines joined with single spaces, then a blank line.
- Marker: `[MM:SS]` when the bucket start is under one hour, else `[HH:MM:SS]` (the switch happens within a file, as in `clean_vtt.py`).
- The output ends with a single trailing newline.

### 6.5 Cache

`${XDG_CACHE_HOME:-~/.cache}/tldl/<key>/` holds:

- `cues.json`: raw cues before cleanup, as `[start, end, lines]` lists; the track kind is in `meta.json`.
- `meta.json`, written last so that its presence marks a complete entry: `tool{name,version}`, `created` (ISO 8601), `url`, `id`, `title`, `duration_s`, `source` (`captions|whisper`), `auto_fallback` (null or `{from, reason}`), `captions{track, kind, info_language, available{manual[], auto_orig[], auto_translated_count}}`, `whisper{model, language, language_probability}`, `timings_s{total}`. No `yt_dlp_version`: it costs one more yt-dlp call per run.
- `raw.vtt`: the downloaded caption file byte for byte (captions only).

`key` = first 16 hex of the SHA-256 of canonical JSON of `{canonical_url, source_used, sub_lang, allow_translated, lang, model}`, where fields irrelevant to the source used are null. `sub_lang` is the value as given (`auto` stays `auto`), so a lookup needs no metadata call; `auto` and an explicit `en` make two entries for the same track. For a local file, `canonical_url` is `file:sha256:<first 16 hex of the file's SHA-256>`, so a moved or renamed file still hits the cache. Lookup tries the captions key first (for `auto`/`subs` on YouTube), then the whisper key. `--interval` and `--no-header` are not in the key because cleanup and rendering run at output time. Canonical URL: for YouTube, `https://www.youtube.com/watch?v=<id>`; otherwise lower-case scheme and host, drop the fragment. A cache hit logs the directory path; a store logs it too. A hit on a local file shows the file's current name in the header. `--refresh` skips the lookup and overwrites the entry. No eviction in v1.

## 7. Project layout and tooling

```
tldl/
  pyproject.toml   uv.lock   .python-version   README.md   docs/SPEC.md
  src/tldl/
    __init__.py
    cli.py         argparse, logging, orchestration, exit codes
    ytdlp.py       command resolution, subprocess helpers (metadata, captions, audio)
    tracks.py      select_track, summary (pure)
    transcribe.py  faster-whisper wrapper with progress
    vtt.py         parser
    clean.py       rolling-caption cleanup, loop collapse (pure)
    render.py      condensed renderer (pure)
    cache.py       key, load, store
  tests/  fixtures/  fake_ytdlp.py  test_pipeline.py  test_tracks.py  test_cli.py  test_edges.py
```

- `uv init --package tldl`; entry point `tldl = "tldl.cli:main"`; `requires-python = ">=3.10"` (Ubuntu 22.04 system Python; confirm with `uv lock`, U7); `.python-version` pinned to 3.10. No 3.11-only features (`tomllib`, `except*`, `typing.Self`).
- Runtime dependency: `faster-whisper` only. Dev group: `ruff`, `pytest`.
- Stdlib `argparse` and `logging`; typed code; `subprocess.run([...])` with argument lists, never `shell=True`.
- Gates: `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`.
- Daily use: `uv run tldl ...` inside the project. Global install depends on U8 (Q6).

### 7.1 Public surface

Only these names are fixed in advance; helpers come out of TDD. Each type lives in the module that creates it, so there is no shared models module.

| Module | Public surface |
|---|---|
| `vtt.py` | `Cue(start: float, end: float, lines: list[str])`; `parse(text: str) -> list[Cue]` |
| `tracks.py` | `Track(kind: str, key: str)`; `NoTrack(summary)`; `primary(key) -> str`; `select_track(info, lang, allow_translated=False) -> (Track, others)` |
| `ytdlp.py` | `info(cmd, url) -> dict`; `captions(cmd, info_path, track, tmpdir) -> Path`; `audio(cmd, url, tmpdir) -> (Path, dict)`; `Failed(msg)`. `cmd` is the split command; the `--ytdlp-cmd` default reads `TLDL_YTDLP` |
| `transcribe.py` | `run(path, model, lang, allow_download) -> (list[Cue], lang, prob)`; `Stopped(cues, at)`, raised on Ctrl-C with the partial cues; `NoModel(repo)` |
| `clean.py` | `captions(cues) -> list[Cue]`; `whisper(cues) -> list[Cue]`; both log what they removed |
| `render.py` | `header(meta) -> str`; `render(cues, interval, header=None) -> str` |
| `cache.py` | `key(**fields) -> str`; `load(key) -> (cues, meta) or None`; `store(key, cues, meta, raw_vtt=None)` |
| `cli.py` | `main(argv=None, transcribe=transcribe.run) -> int`; `run(source, opts, transcribe) -> (cues, meta)`. `opts` is the argparse `Namespace`; `run` returns raw cues and `main` cleans and renders them |

`meta` is a plain dict shaped like `meta.json` (section 6.5). `cli.main` catches `Stopped`, renders its cues plus the stop line, and exits 130. It catches `NoTrack`, `ytdlp.Failed`, `transcribe.NoModel` and `OSError`, logs one line and exits 1; anything else keeps its traceback.

## 8. Testing

Offline by default; the one network test is opt-in. Vertical slices, most useful first; each test must fail on a real bug, so no test exists only to raise coverage. About 15 tests in all: 13 offline plus two opt-in tests.

| # | Slice | Tests |
|---|---|---|
| 1 | Fixture VTT -> parse -> clean -> render (`test_pipeline.py`) | Output holds each of the 661 lines once, in order, in `[MM:SS]` blocks, with `>>` decoded and one trailing newline |
| 2 | Track choice (`test_tracks.py`) | `auto` picks `en-orig`; `de` picks `de-DE-orig`; a translated track is never picked without `allow_translated` |
| 3 | CLI, captions path (`test_cli.py`, `test_upstream.py`) | stdout holds only the transcript; `--source subs` with no matching track exits 1. Opt-in: real yt-dlp on the sample still picks `en-orig`, gets one `.vtt` and renders 600+ lines (upstream breakage); real yt-dlp downloads `sample.mp3` from a local `http.server` and real Whisper hears "signal processing" |
| 4 | CLI, local file to Whisper (`test_cli.py`) | Two tests. One checks exact stdout for segments `A, A, B, B, B, C`: the header shows the file name and language, the loop of 3 collapses to one, the run of 2 survives. One checks that `Stopped` prints the partial cues and the stop line with no header and exits 130; slice 5 adds "caches nothing". A third (added after a bug found by hand) runs a YouTube URL with `--sub-lang zz` through the `auto` fallback and checks the whisper header |
| 5 | Cache (`test_cli.py`) | A second run of a renamed local file with another `--interval` calls neither yt-dlp nor the transcriber |
| 6 | Edges the fixture cannot show (`test_edges.py`) | Marker switches to `[HH:MM:SS]` past one hour; "Ja." repeated with other text between survives cleanup; one synthetic VTT covers an hour field, an identifier line and cue settings |

Test seams, no mocking:

- **yt-dlp:** tests set `TLDL_YTDLP` to `python tests/fake_ytdlp.py`. The fake prints the fixture JSON for `-J` and copies the fixture VTT into the `--paths` directory for the caption call, so the real argument building and subprocess code run. For the audio call it copies `sample.mp3` and the info JSON into the `--paths` directory. Any other call exits 2.
- **Upstream:** `test_upstream.py` runs the real yt-dlp (the `TLDL_YTDLP` set before pytest starts, else `yt-dlp`) only when `TLDL_NETWORK=1`; run it after `uv tool upgrade yt-dlp`. The served-file test also needs the cached model (`HF_HUB_CACHE`).
- **Cache:** an autouse fixture in `tests/conftest.py` points `XDG_CACHE_HOME` at `tmp_path`.
- **Whisper:** `cli.main(argv=None, transcribe=transcribe.run)`, which parses arguments and calls `cli.run(source, opts, transcribe) -> (cues, meta)` (no argparse or exit codes inside `run`); tests pass a function that returns fixed cues plus a language and probability.

Fixture: the info JSON is trimmed to about 5 KB: `id`, `title`, `channel`, `language`, `duration`, all 21 `-orig` keys, 3 translated keys (including `en` and `de-DE`), each with a format list of `[{"ext": "vtt"}, {"ext": "srt"}]`. The real counts are recorded in section 11 (U1). `sample.mp3` is a 1.8 s English utterance ("Speech signal processing", dpsa on freesound.org, CC BY 3.0); `tests/fixtures/CREDITS.md` holds the attribution.

Not tested: model loading (verified by hand, U14, and in acceptance), `--list-subs` (a print loop), `live_chat` and tracks without `vtt` (absent from the real data).

## 9. Acceptance criteria

1. `tldl <youtube-url>` prints only the condensed transcript on stdout; the chosen caption track, timings and cache path appear on stderr.
2. `--source whisper` on the same URL works; `tldl https://cre.fm/cre094-conversational-design` (auto resolves to Whisper) works; `tldl 026.mp3` (2 h 20 min, German) works, and its run time is recorded as U10.
2a. Ctrl-C during a Whisper run prints the partial transcript and the stop marker, then exits 130.
3. A second run with a different `--interval` performs no fetch or transcription.
4. A default run with the shared cache present makes no Hugging Face request; a missing model never downloads without `--allow-download`.
5. `uv sync --locked`, `ruff check`, `ruff format --check` and `pytest` pass on a clean checkout.
6. Real-data checks: on a caption fixture the transcript contains each phrase once; on a Whisper run the output was skimmed for hallucination loops, and the cached raw segments confirm what cleanup removed.
7. The tool never reads stdin: `tldl URL < /dev/null` and an interactive run behave the same.
8. The token estimate in section 1 is checked once with a real transcript (informational).

## 10. Risks

1. cre.fm works through yt-dlp's generic extractor (U9); other podcast sites can fail. A downloaded file is the fallback (local input).
2. CPU runtime and memory: 3.56x realtime on the 16-core dev laptop, so 39 minutes for a 2 h 20 min episode (U10). Peak memory grows with audio length: 1.0 GB for 10 minutes, 8.5 GB for 140 minutes, inside faster-whisper. A smaller machine (such as a VM) needs a memory check before long episodes; chunking the audio is the fix if it falls short.
3. `small` is weaker on German and technical vocabulary than larger models (not measured on CRE audio).
4. Whisper hallucinations on music or silence are reduced by VAD and the loop filter, not eliminated. Seen in acceptance: invented text over the cre094 intro jingle, and a 6x loop in `026.mp3` that the filter collapsed.
5. Whisper skips speech under loud background noise. On `6toXnSudT7o` (workshop and engine noise), segments ran up to 848 s with a dozen words each; Whisper kept 2,534 words against 3,816 in the captions. Nothing warns about it. The `small` model is likely part of the cause (risk 10.3). Captions stay the default for YouTube; the German podcast `026.mp3` showed no such segment (longest 16 s).
6. Auto-caption quality: checked on one German conversation (`1LFdiGkqPZQ`, 128 min, `de-orig`): captions 20.6k words in seconds, Whisper 19.4k words in 30 min, same content. Captions keep more fillers and repeats; Whisper punctuates a little better. Captions first stays the default.
7. Translation trap (5.2): a plain language code can be a machine translation; `-orig` semantics are verified on one video only (U3).
8. YouTube can throttle or block requests (HTTP 429). The captions path makes one metadata request plus the subtitle fetch; no retry loops in v1.
9. yt-dlp breaks when sites change; the fix is updating it, not the project.
10. A wrong default pick (track, language) costs a rerun; the warning names the flag. If this happens often in practice, revisit prompts (section 14).

## 11. Verification log (fill in while implementing)

| ID | Assumption | Status | How to verify |
|---|---|---|---|
| V1 | `--sub-langs` entries are regex; `--sub-format`, `--write-subs`, `--write-auto-subs`, `--list-subs` exist | verified (docs) | `yt-dlp --help` |
| V2 | faster-whisper uses the Hugging Face cache by default | verified | listing |
| V3 | Sample video has only automatic captions, `vtt` on every track, 20 `-orig` tracks | verified (owner's output) | rerun `--list-subs` |
| U1 | `-J` output has `subtitles`, `automatic_captions`, `language` | verified 2026-10-05: all present; `subtitles` empty, 182 automatic tracks (21 `-orig`, 161 translated), `vtt` on each | run on `6toXnSudT7o`, inspect keys |
| U2 | Anchored `--sub-langs '^en-orig$'` downloads exactly that track | verified: `'^en\-orig$'` (the `re.escape` form) wrote one file, `6toXnSudT7o.en-orig.vtt` | run it, list the temp dir |
| U3 | Which `-orig` track is the spoken language on the sample; whether it is auto-dubbed | verified: English (`en-orig`); 20 audio tracks are noted `dubbed-auto`, the en-US track is `original (default)` with `language_preference` 10, and yt-dlp's default selection picks it | compare `language`, title, audio |
| U4 | Auto-caption VTT structure | verified: see 6.3; short new lines carry no word-timing tags | inspect the fixture |
| U5 | `local_files_only` parameter name in the resolved faster-whisper | verified (1.2.1): `local_files_only`, `download_root`, `cpu_threads` exist | `help(WhisperModel)` |
| U6 | faster-whisper decodes yt-dlp `bestaudio` (webm/opus, m4a) without a system ffmpeg | verified 2026-10-06 for webm/opus: `--source whisper` on `6toXnSudT7o` (format 251) ran end to end with `ffmpeg` and `ffprobe` hidden from PATH; m4a not tried | run on a downloaded file with ffmpeg off PATH |
| U7 | Python range supported by faster-whisper's dependencies | unverified | `uv lock` |
| U8 | `uv tool install .` ignores `uv.lock` | verified (uv 0.6.3): no `--locked` or `--frozen` flag; a plain install resolved fresh on Python 3.12. `uv export --frozen --no-dev --no-emit-project --no-hashes -o c.txt` plus `uv tool install --python 3.10 -c c.txt .` reproduces the project venv exactly | `uv tool install --help`, install into a scratch `UV_TOOL_DIR`, compare versions |
| U9 | yt-dlp handles the cre.fm URL | verified: generic extractor finds 4 formats (oga, m4a, mp3, opus); `duration` is null, so the long-job log reads duration from the downloaded file | run it |
| U10 | CPU throughput of `small` int8 on this machine | verified 2026-10-06 on the 16-core dev laptop: 10-min German clip in 166 s (3.6x realtime, maxrss 1.0 GB); full `026.mp3` (139.7 min) in 39.3 min against an estimate of 38.8 (3.56x), maxrss 8.5 GB. `SPEED` is 3.6; another machine (such as a VM) must measure it again, because it only feeds the estimate log | time a 10-minute clip, then the full file |
| U12 | Token estimates in section 1 | checked by character count (no tokenizer offline): `026.mp3` output is 148k characters, 25k German words, 280 markers in 3,000 characters (about 1.5k tokens); the text itself is roughly 40k to 50k tokens. The 2,286 raw segments as VTT would add about 45k tokens of timing lines | count a real transcript |
| U13 | `transcribe()` finishes language detection before any segment is consumed | verified: `info.language=de`, p=1.00, 3.2 s before iterating | read `info.language` before iterating |
| U14 | `local_files_only=True` loads the cached snapshot with no network; which exception a missing model raises | verified: cached `small` loads; missing `tiny` raises `huggingface_hub.errors.LocalEntryNotFoundError` | run with the cache present, then with `--model tiny` not cached |
| U15 | `info["language"]` exists and is reliable | verified on one video: `en-US`, matches the original audio | inspect the trimmed info JSON |
| U16 | `--load-info-json` plus `--write-auto-subs` downloads the track with no new metadata request | verified: the only request was the `timedtext` URL | run with `-v`, inspect requests |

## 12. Build order (with stop points)

0. **Preflight:** report `uv --version`, `yt-dlp --version`, Python, CPU cores, RAM; list the HF cache path from section 3. Missing tools: report and ask before installing anything.
1. **Real data first (by hand, no code):** on `6toXnSudT7o` run the metadata call, keep a trimmed info JSON (`id`, `title`, `language`, `subtitles`, `automatic_captions`), download the chosen track's VTT with `--load-info-json`, keep both as fixtures. Try the cre.fm URL with yt-dlp. Update U1 to U4, U9, U15, U16. **STOP and report** (spoken language, `-orig` finding, VTT structure, cre.fm result).
2. Done by hand on a 1-minute clip (U5, U13, U14; U10 partly). The 10-minute timing moved into step 5.
3. `uv init`, dependencies, ruff and pytest config, fixtures; then slices 1 and 2 from section 8.
4. Slices 3 to 6: yt-dlp helpers, transcribe wrapper, cache, CLI wiring.
5. Acceptance runs (section 9), including the 10-minute timing and the full `026.mp3`; needs mains power. Fill the verification log. **STOP and report.**
6. README (usage, prerequisites, yt-dlp update routine, clipboard example); decide the global-install story (U8).

## 13. Working agreement for Claude Code

- Read `--help` before using any yt-dlp or uv flag; this spec's flag names are partly recalled. Correct the spec where reality differs and say so.
- Stay in scope (section 1). Anything else goes to section 14, not the code.
- Note deviations from this spec in `docs/DEVIATIONS.md` with the reason, and mention them at the next stop point.
- `git init`; small commits; run the gates from section 7 before calling a step done.
- Write only inside the project, the tldl cache directory and temp directories. Do not touch other files under `~/.cache/huggingface`.
- Be gentle with YouTube: no loops, no retries; on 429, stop and report.
- Report failed or unverified assumptions instead of working around them silently.
- Do not install system packages or tools without asking.

### Suggested `CLAUDE.md` for the repo

```
# tldl
Read docs/SPEC.md first; it is the source of truth. Follow section 12 and stop at the STOP points.
Commands: uv sync --locked | uv run pytest | uv run ruff check | uv run ruff format --check | uv run tldl --help
Rules: stdout carries only the transcript; logs to stderr; never read stdin; no shell=True; no network in tests;
verify flags with --help; log deviations in docs/DEVIATIONS.md; runtime dependency is faster-whisper only.
```

## 14. Questions and deferred work

### Questions for the owner

1. **Q1, name:** answered: `tldl`.
2. **Q2, yt-dlp:** OK with the external `yt-dlp` on PATH plus `--ytdlp-cmd`/`TLDL_YTDLP`? Is yt-dlp installed today, and how?
3. **Q3, `--sub-lang auto`:** confirm the video's language as default, else `en`.
4. **Q4, sample set and permissions:** besides cre094 and `6toXnSudT7o`, which one or two URLs for acceptance (ideally one German YouTube video with captions and one episode of 2 h or longer)? May Claude Code use the network (YouTube, cre.fm, PyPI, Hugging Face) and run a multi-hour transcription during acceptance? Answered 2026-10-06: `026.mp3` for the long episode; German YouTube `1LFdiGkqPZQ` (used) and `QfgDbeNM1tc`, both about 2 h with `de-orig` captions only; network and long runs allowed on mains power.
5. **Q5, machine:** answered: the sandbox is the dev laptop (16 cores, 27 GiB RAM). It may later run on a VM behind a web frontend; measure U10 and peak memory again there.
6. **Q6, global command:** after U8, `uv tool install .` or `uv run` inside the project?

### Deferred, with the trigger for adding each

| Feature | Add when |
|---|---|
| Native downloader (stdlib, `<audio>`/`og:audio`, size cap) | yt-dlp fails on a URL you actually need (U9) |
| Interactive prompts for track, language, model download | Wrong default picks force reruns more than occasionally |
| `--out-dir` with versioned files | Redirecting stdout plus the cache directory is not enough |
| `--keep-audio` | You want to rerun Whisper with another model without downloading again |
| Resume an interrupted Whisper run | An interruption cost a long run twice |
| `--cpu-threads`, `--loop-threshold` | The library default or threshold 3 measurably falls short |
| Splitting into parts (`--max-chars`) | A full transcript does not paste or attach in Claude web |
| Larger Whisper model | `small` disappoints on German |
| Web UI (job queue, progress callback, cancel flag, URL allowlist) | Someone other than you needs to run it; `cli.run` is the entry point, fed a `Namespace` from `parser.parse_args`; add a typed `Options` only then |
| RSS/feed support, multiple URLs, cache eviction, `--copy` | A concrete need appears |

### TODOs

- Fill the verification log during steps 1 to 5.
- Pick a reference YouTube video that matches the real use (talk or podcast, little background noise) to replace `6toXnSudT7o` in acceptance; the truck video is mostly workshop noise (risk 10.5). Candidates: `1LFdiGkqPZQ`, `QfgDbeNM1tc` (Q4).
- Document the yt-dlp update routine in the README (`uv tool upgrade yt-dlp`).
