"""YouTube URL validation, caption retrieval, and transcript cleanup."""

from __future__ import annotations

import html
import json
import logging
import re
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
}


def _load_ytdlp():
    """Import and return yt-dlp, raising an install hint when unavailable."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is required for YouTube notes. Install the Study Assistant "
            "dependencies with: pip install -r app/requirements.txt"
        ) from exc
    return yt_dlp


def is_valid_youtube_url(url: str) -> bool:
    """Return whether the URL matches a supported YouTube video URL pattern."""
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
    """Choose the best available caption format list, preferring English tracks."""
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
    """Return a downloadable caption URL and extension from caption metadata."""
    preferred_exts = ["json3", "vtt", "srv3", "ttml"]
    for ext in preferred_exts:
        for item in formats:
            if item.get("url") and item.get("ext") == ext:
                return item["url"], ext
    for item in formats:
        if item.get("url"):
            return item["url"], item.get("ext", "")
    logger.warning("Caption metadata did not include a downloadable URL")
    raise RuntimeError("Caption metadata did not include a downloadable URL.")


def _parse_json3(content: str) -> str:
    """Parse YouTube JSON3 captions into newline-separated transcript text."""
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
    """Parse VTT-like caption text into newline-separated transcript text."""
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
    """Normalize transcript text and remove common caption artifacts."""
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
    """Fetch, parse, and clean the best available transcript for a YouTube URL.

    Args:
        url: Supported YouTube video URL.

    Returns:
        A tuple of cleaned transcript text and the video title when available.

    Raises:
        RuntimeError: If caption metadata is malformed.
        requests.HTTPError: If downloading the selected caption file fails.
    """
    yt_dlp = _load_ytdlp()
    options = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        logger.info("Fetching YouTube metadata for transcript lookup")
        info = ydl.extract_info(url, download=False)

    title = info.get("title")
    captions = info.get("subtitles") or {}
    automatic_captions = info.get("automatic_captions") or {}
    formats = _preferred_caption(captions) or _preferred_caption(automatic_captions)

    if not formats:
        logger.warning("No YouTube captions were available title_available=%s", title is not None)
        return "", title

    caption_url, ext = _caption_format_url(formats)
    logger.info("Downloading YouTube caption track ext=%s", ext)
    response = requests.get(caption_url, timeout=20)
    response.raise_for_status()

    if ext == "json3" or response.text.lstrip().startswith("{"):
        transcript = _parse_json3(response.text)
    else:
        transcript = _parse_vtt(response.text)

    logger.info("Fetched YouTube transcript title_available=%s transcript_chars=%s", title is not None, len(transcript))
    return clean_transcript(transcript), title
