# Deviations from docs/SPEC.md

- **Python 3.10, not 3.11.** The host runs Ubuntu 22.04, whose system Python is 3.10. The code must not use 3.11-only features.
- **onnxruntime pinned below 1.24 on Python 3.10.** onnxruntime 1.24 ships no cp310 wheels, and uv's resolver picks it anyway. A `[tool.uv] constraint-dependencies` entry fixes this without adding a runtime dependency. Installs that bypass the lock (plain pip) may hit the same error.
- **PyAV pinned below 19 as a direct dependency.** PyAV 19 dropped the `metadata_errors` argument that faster-whisper 1.2.1 passes to `av.open`, so every Whisper run crashed on Python 3.12, where uv picks PyAV 19. A `[tool.uv]` constraint would not reach uvx or `uv tool install` from git, so the pin goes in `dependencies`. Drop it once faster-whisper stops passing the argument.
