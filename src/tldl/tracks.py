from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    kind: str
    key: str


class NoTrack(Exception):
    def __init__(self, summary: str):
        super().__init__(summary)
        self.summary = summary


def primary(key: str) -> str:
    return key.split("-", 1)[0].lower()


def _has_vtt(formats: list[dict]) -> bool:
    return any(f.get("ext") == "vtt" for f in formats)


def select_track(
    info: dict, lang: str, allow_translated: bool = False
) -> tuple[Track, list[Track]]:
    manual = {
        k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"
    }
    auto = info.get("automatic_captions") or {}
    orig = [k for k in auto if k.endswith("-orig")]
    translated = [k for k in auto if not k.endswith("-orig")]

    def pick(source: dict, keys: list[str], kind: str) -> list[Track]:
        lang_of = {k: k.removesuffix("-orig") for k in keys}
        keys = [
            k
            for k in keys
            if primary(lang_of[k]) == primary(lang) and _has_vtt(source[k])
        ]
        return [
            Track(kind, k) for k in sorted(keys, key=lambda k: (lang_of[k] != lang, k))
        ]

    candidates = pick(manual, list(manual), "manual") + pick(auto, orig, "auto")
    if allow_translated:
        candidates += pick(auto, translated, "auto-translated")
    if not candidates:
        summary = (
            f"no {lang} track; manual: {', '.join(manual) or 'none'}; "
            f"orig: {', '.join(orig) or 'none'}; {len(translated)} translated"
        )
        if not allow_translated and pick(auto, translated, "auto-translated"):
            summary += (
                f"; rerun with --allow-translated for a machine-translated {lang} track"
            )
        raise NoTrack(summary)
    return candidates[0], candidates[1:]
