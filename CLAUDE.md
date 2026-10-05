# tldl
Read docs/SPEC.md first; it is the source of truth. Follow section 12 and stop at the STOP points.
Commands: uv sync --locked | uv run pytest | uv run ruff check | uv run ruff format --check | uv run tldl --help
Rules: stdout carries only the transcript; logs to stderr; never read stdin; no shell=True; no network in tests;
verify flags with --help; log deviations in docs/DEVIATIONS.md; runtime dependency is faster-whisper only.
Sandbox: the /work disk is nearly full, so set UV_PROJECT_ENVIRONMENT=/claude/venvs/tldl (tmpfs, rebuild with uv sync).
Model cache: HF_HUB_CACHE=/work/hf-cache/hub. yt-dlp: TLDL_YTDLP="uvx --python 3.12 --with deno --from yt-dlp[default,curl-cffi]@latest yt-dlp" (see SPEC section 3).
