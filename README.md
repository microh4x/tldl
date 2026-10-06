# tldl

`tldl` ("too long; didn't listen") prints a condensed transcript of a URL or a local audio file: one `[MM:SS] text` block per 30 seconds plus one header line. The output is small enough to paste into Claude web and ask for a summary of a 2-hour episode.

It takes YouTube captions when they exist (fast, no audio download) and otherwise runs Whisper `small` on the CPU. Results are cached, so a second run with other output options is instant.

## Prerequisites

- [uv](https://docs.astral.sh/uv/).
- yt-dlp, installed as a uv tool with its own Python, a JavaScript runtime and the impersonation library:

  ```
  uv tool install --python 3.12 --with deno 'yt-dlp[default,curl-cffi]'
  ```

  YouTube changes often, and an old yt-dlp is the most common cause of failures. Update it with `uv tool upgrade yt-dlp`, which keeps the options above. To use another command, set `TLDL_YTDLP` or pass `--ytdlp-cmd`, for example `TLDL_YTDLP="uvx yt-dlp@latest"`.
- The faster-whisper `small` model in the Hugging Face cache (`~/.cache/huggingface/hub`, or `HF_HUB_CACHE`). `tldl` never downloads a model unless you pass `--allow-download` once.

ffmpeg is not required.

## Run without cloning

With only uv installed, uvx fetches `tldl` and brings yt-dlp and deno into the same environment:

```
uvx --python 3.12 --with 'yt-dlp[default,curl-cffi]' --with deno \
  --from git+https://github.com/microh4x/tldl tldl 'https://www.youtube.com/watch?v=...'
```

To get a plain `tldl` command instead, install it with the same options:

```
uv tool install --python 3.12 --with 'yt-dlp[default,curl-cffi]' --with deno \
  git+https://github.com/microh4x/tldl
```

Use Python 3.11 or newer: uv ignores the onnxruntime constraint for Python 3.10 in `pyproject.toml` when it installs from git. uvx reuses its cached environment, so update yt-dlp with `uvx --refresh-package yt-dlp ...`, or with `uv tool upgrade tldl` after `uv tool install`. Neither reads `uv.lock`, so you get the newest dependencies. The Whisper model prerequisite above still applies.

## Install

`uv tool install` does not read `uv.lock`, so pass the lock as constraints to get the tested versions:

```
uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/tldl-constraints.txt
uv tool install --python 3.10 -c /tmp/tldl-constraints.txt .
```

Run this in the project directory, and again after `git pull`. Without installing, `uv run tldl ...` works inside the project.

## Usage

```
tldl https://www.youtube.com/watch?v=6toXnSudT7o > video.txt
tldl https://cre.fm/cre094-conversational-design | wl-copy
tldl episode.mp3 | xclip -selection clipboard
```

To summarise with Claude Code, pipe the transcript into `claude -p`. Haiku is enough for a gist; use `--model sonnet` when the summary feels thin.

```
tldl https://www.youtube.com/watch?v=1LFdiGkqPZQ \
  | claude -p --model haiku "Summarise this transcript. Key points as bullets, with [MM:SS] references."
```

The transcript goes to stdout; logs, the chosen caption track and the cache path go to stderr. `tldl` never reads stdin.

Useful options (`tldl --help` lists all):

- `--source whisper` skips captions; `--source subs` fails instead of falling back to Whisper.
- `--sub-lang de` picks the caption language; the default is the video's language. `--list-subs` shows the tracks.
- `--lang de` skips Whisper's language detection.
- `--interval 60` makes longer blocks; `--no-header` drops the header line.
- `--refresh` ignores the cache.

Whisper runs at about 3.6x realtime on a 16-core laptop, so a 2-hour episode takes about 40 minutes. `tldl` logs an estimate and the progress. Peak memory grows with the length of the audio: about 1 GB for 10 minutes and 8.5 GB for 140 minutes. Ctrl-C prints the part done so far and exits 130; a partial result is not cached.

## Cache

Raw captions and Whisper segments live in `${XDG_CACHE_HOME:-~/.cache}/tldl/<key>/`, one directory per source and settings. Delete a directory to drop an entry. A local file is keyed by its content, so a renamed file still hits the cache.

## Development

```
uv sync --locked
uv run pytest
uv run ruff check
uv run ruff format --check
```

`docs/SPEC.md` is the source of truth; `docs/DEVIATIONS.md` lists where the code differs from it. `TLDL_NETWORK=1 uv run pytest` also runs the tests that call the real yt-dlp.
