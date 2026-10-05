# Deviations from docs/SPEC.md

- **Python 3.10, not 3.11.** The host runs Ubuntu 22.04, whose system Python is 3.10. The code must not use 3.11-only features.
- **onnxruntime pinned below 1.24 on Python 3.10.** onnxruntime 1.24 ships no cp310 wheels, and uv's resolver picks it anyway. A `[tool.uv] constraint-dependencies` entry fixes this without adding a runtime dependency. Installs that bypass the lock (plain pip) may hit the same error.
