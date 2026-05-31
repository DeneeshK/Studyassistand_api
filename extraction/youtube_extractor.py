from __future__ import annotations

import html
import json
import re
from urllib.parse import urlparse

import requests


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
}


def _load_ytdlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is required for YouTube notes. Install the Study Assistant "
            "dependencies with: pip install -r app/requirements.txt"
        ) from exc
    return yt_dlp


def is_valid_youtube_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    host = parsed.netloc.lower()
    if host not in YOUTUBE_HOSTS:
        return False

    if host == "youtu.be":
        return bool(parsed.path.strip("/"))

    return (
        parsed.path == "/watch"
        or parsed.path.startswith("/shorts/")
        or parsed.path.startswith("/embed/")
        or parsed.path.startswith("/live/")
    )


def _preferred_caption(captions: dict) -> list[dict] | None:
    if not captions:
        return None

    preferred_keys = [
        "en",
        "en-US",
        "en-GB",
        "en-orig",
    ]
    preferred_keys.extend(sorted(key for key in captions if key.startswith("en")))
    preferred_keys.extend(sorted(captions))

    seen: set[str] = set()
    for key in preferred_keys:
        if key in seen or key not in captions:
            continue
        seen.add(key)
        formats = captions.get(key) or []
        if formats:
            return formats
    return None


def _caption_format_url(formats: list[dict]) -> tuple[str, str]:
    preferred_exts = ["json3", "vtt", "srv3", "ttml"]
    for ext in preferred_exts:
        for item in formats:
            if item.get("url") and item.get("ext") == ext:
                return item["url"], ext
    for item in formats:
        if item.get("url"):
            return item["url"], item.get("ext", "")
    raise RuntimeError("Caption metadata did not include a downloadable URL.")


def _parse_json3(content: str) -> str:
    data = json.loads(content)
    lines: list[str] = []
    for event in data.get("events", []):
        parts = []
        for segment in event.get("segs", []) or []:
            value = segment.get("utf8", "")
            if value:
                parts.append(value)
        line = "".join(parts).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _parse_vtt(content: str) -> str:
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.startswith("WEBVTT")
            or line.startswith("Kind:")
            or line.startswith("Language:")
            or "-->" in line
            or re.match(r"^\d+$", line)
        ):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{[^}]+\}", "", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def clean_transcript(transcript: str) -> str:
    text = html.unescape(transcript or "")
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\([^)]*music[^)]*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    cleaned_lines: list[str] = []
    previous = ""
    for line in text.splitlines():
        clean_line = line.strip()
        if clean_line and clean_line != previous:
            cleaned_lines.append(clean_line)
            previous = clean_line

    return "\n".join(cleaned_lines).strip()


def fetch_youtube_transcript(url: str) -> tuple[str, str | None]:
    yt_dlp = _load_ytdlp()
    options = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title")
    captions = info.get("subtitles") or {}
    automatic_captions = info.get("automatic_captions") or {}
    formats = _preferred_caption(captions) or _preferred_caption(automatic_captions)

    if not formats:
        return "", title

    caption_url, ext = _caption_format_url(formats)
    response = requests.get(caption_url, timeout=20)
    response.raise_for_status()

    if ext == "json3" or response.text.lstrip().startswith("{"):
        transcript = _parse_json3(response.text)
    else:
        transcript = _parse_vtt(response.text)

    return clean_transcript(transcript), title
