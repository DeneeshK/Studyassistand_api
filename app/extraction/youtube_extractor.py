"""YouTube URL validation, caption retrieval, and transcript cleanup.

Strategy (in priority order):
  1. youtube-transcript-api  — official YouTube caption API, no cookies needed,
     works reliably in production environments.
  2. yt-dlp                  — fallback for edge-cases (age-gated, rare formats).

The yt-dlp path is kept so that the existing logic is never lost, but
`youtube-transcript-api` is always tried first because it does not need
session cookies to pass YouTube's bot-detection checks.
"""

from __future__ import annotations

import html
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

import requests


logger = logging.getLogger(__name__)

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
}

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

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


def _extract_video_id(url: str) -> str | None:
    """Extract the bare YouTube video-ID string from any supported URL form."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    host = parsed.netloc.lower()

    # youtu.be/<id>
    if host == "youtu.be":
        vid = parsed.path.strip("/")
        return vid if vid else None

    # /shorts/<id>  |  /embed/<id>  |  /live/<id>
    for prefix in ("/shorts/", "/embed/", "/live/"):
        if parsed.path.startswith(prefix):
            vid = parsed.path[len(prefix):].split("/")[0]
            return vid if vid else None

    # /watch?v=<id>
    qs = parse_qs(parsed.query)
    ids = qs.get("v", [])
    return ids[0] if ids else None


# ---------------------------------------------------------------------------
# Primary extractor — youtube-transcript-api (no cookies needed)
# ---------------------------------------------------------------------------

def _load_transcript_api():
    """Import youtube-transcript-api, raising an install hint when missing.

    v1.x replaced the old static `YouTubeTranscriptApi.list_transcripts(...)`
    call with an instantiated client (`YouTubeTranscriptApi().list(...)`) and
    added dedicated IpBlocked/RequestBlocked exceptions for YouTube's
    datacenter-IP bot detection -- the exact failure mode that used to force
    every request down to the yt-dlp fallback, which is itself just as
    exposed to that same blocking.
    """
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi,
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
            CouldNotRetrieveTranscript,
            IpBlocked,
            RequestBlocked,
        )
        return (
            YouTubeTranscriptApi,
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
            CouldNotRetrieveTranscript,
            IpBlocked,
            RequestBlocked,
        )
    except ImportError as exc:
        raise RuntimeError(
            "youtube-transcript-api is required. "
            "Install it with: pip install youtube-transcript-api"
        ) from exc


def _build_transcript_api_client(YouTubeTranscriptApi):
    """Build a YouTubeTranscriptApi client, routed through a proxy if configured.

    YOUTUBE_PROXY_URL is the mitigation for IpBlocked/RequestBlocked errors:
    without it, a server running on a datacenter/cloud IP (AWS, GCP, Azure,
    etc.) can get blocked by YouTube's bot detection with no recourse.
    """
    from app.config import settings

    if not settings.YOUTUBE_PROXY_URL:
        return YouTubeTranscriptApi()

    from youtube_transcript_api.proxies import GenericProxyConfig

    return YouTubeTranscriptApi(
        proxy_config=GenericProxyConfig(
            http_url=settings.YOUTUBE_PROXY_URL,
            https_url=settings.YOUTUBE_PROXY_URL,
        )
    )


_LANG_PRIORITY = ["en", "en-US", "en-GB", "en-IN"]


def _fetch_with_transcript_api(video_id: str) -> str | None:
    """Use youtube-transcript-api to fetch and join captions for *video_id*.

    Tries preferred English tracks first, then falls back to any available
    transcript (including auto-generated ones).

    Returns joined transcript text, or None if nothing is available.
    """
    (
        YouTubeTranscriptApi,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
        CouldNotRetrieveTranscript,
        IpBlocked,
        RequestBlocked,
    ) = _load_transcript_api()

    api = _build_transcript_api_client(YouTubeTranscriptApi)

    try:
        transcript_list = api.list(video_id)
    except IpBlocked:
        logger.warning(
            "youtube-transcript-api: this server's IP is blocked by YouTube video_id=%s. "
            "Set YOUTUBE_PROXY_URL to route caption requests through a proxy.",
            video_id,
        )
        return None
    except RequestBlocked:
        logger.warning(
            "youtube-transcript-api: request blocked by YouTube bot detection video_id=%s. "
            "Set YOUTUBE_PROXY_URL to route caption requests through a proxy.",
            video_id,
        )
        return None
    except (TranscriptsDisabled, VideoUnavailable, CouldNotRetrieveTranscript) as exc:
        logger.warning(
            "youtube-transcript-api: transcript unavailable video_id=%s reason=%s",
            video_id,
            exc.__class__.__name__,
        )
        return None
    except Exception as exc:
        logger.warning(
            "youtube-transcript-api: unexpected error listing transcripts video_id=%s error=%s",
            video_id,
            exc,
        )
        return None

    # 1. Try manually-created transcripts in preferred languages.
    try:
        transcript = transcript_list.find_manually_created_transcript(_LANG_PRIORITY)
        logger.info("Using manually-created caption track video_id=%s", video_id)
        return _join_transcript_entries(transcript.fetch())
    except NoTranscriptFound:
        pass

    # 2. Try auto-generated transcripts in preferred languages.
    try:
        transcript = transcript_list.find_generated_transcript(_LANG_PRIORITY)
        logger.info("Using auto-generated caption track video_id=%s", video_id)
        return _join_transcript_entries(transcript.fetch())
    except NoTranscriptFound:
        pass

    # 3. Fall back to whatever language is available (manual first, then auto).
    for transcript in transcript_list:
        try:
            logger.info(
                "Using fallback caption track video_id=%s lang=%s is_generated=%s",
                video_id,
                transcript.language_code,
                transcript.is_generated,
            )
            return _join_transcript_entries(transcript.fetch())
        except Exception:
            continue

    return None


def _join_transcript_entries(entries) -> str:
    """Join a list of transcript entry dicts into a single text string."""
    lines = []
    for entry in entries:
        # youtube-transcript-api v0.6+ returns objects; older versions return dicts
        if hasattr(entry, "text"):
            text = entry.text
        else:
            text = entry.get("text", "")
        text = text.strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback extractor — yt-dlp (original implementation, kept as safety net)
# ---------------------------------------------------------------------------

def _load_ytdlp():
    """Import and return yt-dlp, raising an install hint when unavailable."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is required for the YouTube fallback extractor. "
            "Install it with: pip install yt-dlp"
        ) from exc
    return yt_dlp


def _preferred_caption(captions: dict) -> list[dict] | None:
    """Choose the best available caption format list, preferring English tracks."""
    if not captions:
        return None

    preferred_keys = ["en", "en-US", "en-GB", "en-orig"]
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


def _fetch_with_ytdlp(url: str) -> tuple[str, str | None]:
    """Attempt transcript extraction via yt-dlp (fallback path).

    Returns (transcript_text, video_title). Transcript text may be empty.
    """
    from app.config import settings

    yt_dlp = _load_ytdlp()
    options = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
    }
    if settings.YOUTUBE_PROXY_URL:
        # This fallback path is just as exposed to YouTube's datacenter-IP
        # bot detection as the primary path, so it shares the same proxy.
        options["proxy"] = settings.YOUTUBE_PROXY_URL

    with yt_dlp.YoutubeDL(options) as ydl:
        logger.info("yt-dlp: fetching metadata for fallback transcript lookup url=%s", url)
        info = ydl.extract_info(url, download=False)

    title = info.get("title")
    captions = info.get("subtitles") or {}
    automatic_captions = info.get("automatic_captions") or {}
    formats = _preferred_caption(captions) or _preferred_caption(automatic_captions)

    if not formats:
        logger.warning("yt-dlp: no captions available title=%s", title)
        return "", title

    caption_url, ext = _caption_format_url(formats)
    logger.info("yt-dlp: downloading caption track ext=%s", ext)
    response = requests.get(caption_url, timeout=20)
    response.raise_for_status()

    if ext == "json3" or response.text.lstrip().startswith("{"):
        transcript = _parse_json3(response.text)
    else:
        transcript = _parse_vtt(response.text)

    return transcript, title


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

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

    Tries the official youtube-transcript-api first (production-safe, no cookies
    needed), then falls back to yt-dlp for edge cases.

    Args:
        url: Supported YouTube video URL.

    Returns:
        A tuple of (cleaned_transcript_text, video_title).
        transcript text is empty string when no captions are available.

    Raises:
        ValueError: When a video ID cannot be parsed from the URL.
        RuntimeError: When both extraction paths fail.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not parse a video ID from URL: {url!r}")

    # ── Primary path: youtube-transcript-api ──────────────────────────────
    title: str | None = None
    try:
        raw = _fetch_with_transcript_api(video_id)
        if raw:
            logger.info(
                "Transcript fetched via youtube-transcript-api video_id=%s chars=%s",
                video_id,
                len(raw),
            )
            return clean_transcript(raw), title
        logger.info(
            "youtube-transcript-api returned no transcript; trying yt-dlp fallback video_id=%s",
            video_id,
        )
    except Exception as primary_exc:
        logger.warning(
            "youtube-transcript-api failed; trying yt-dlp fallback video_id=%s error=%s",
            video_id,
            primary_exc,
        )

    # ── Fallback path: yt-dlp ─────────────────────────────────────────────
    try:
        raw, title = _fetch_with_ytdlp(url)
        logger.info(
            "Transcript fetched via yt-dlp video_id=%s chars=%s title=%s",
            video_id,
            len(raw),
            title is not None,
        )
        return clean_transcript(raw), title
    except Exception as fallback_exc:
        logger.warning(
            "yt-dlp fallback also failed video_id=%s error=%s",
            video_id,
            fallback_exc,
        )
        # Return empty transcript so the route can surface a user-facing message.
        return "", title
