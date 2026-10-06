"""Stand-in for yt-dlp: serves the fixtures, exits 2 on any call it does not know."""

import re
import shutil
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
args = sys.argv[1:]

if "-J" in args:
    sys.stdout.write((FIXTURES / "6toXnSudT7o.info.json").read_text())
elif "--load-info-json" in args:
    key = re.sub(r"\\(.)", r"\1", args[args.index("--sub-langs") + 1].strip("^$"))
    vtt = FIXTURES / f"6toXnSudT7o.{key}.vtt"
    shutil.copy(vtt, Path(args[args.index("--paths") + 1]) / vtt.name)
elif "bestaudio/best" in args:
    out = Path(args[args.index("--paths") + 1])
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "sample.mp3", out / "6toXnSudT7o.mp3")
    shutil.copy(FIXTURES / "6toXnSudT7o.info.json", out)
else:
    sys.exit(2)
