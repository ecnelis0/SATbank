"""Getting a YouTube video into the app: its id, its title, and what was said.

No API key anywhere here. The id comes out of the URL, the title comes from
YouTube's oEmbed endpoint, and the words come from the captions. A video with no
captions cannot be read, and this says so rather than summarising silence - the
student can paste a transcript instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import httpx

OEMBED = "https://www.youtube.com/oembed"

# 11 characters of the YouTube alphabet. Pinned, because "watch?v=" followed by
# anything would happily accept a playlist id and then 404 at fetch time with a
# message about transcripts rather than about the link.
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class VideoUnreadable(RuntimeError):
    """The video cannot be turned into text. The message is shown to the student."""


@dataclass(slots=True)
class Snippet:
    start: float
    text: str


@dataclass(slots=True)
class Transcript:
    text: str
    snippets: list[Snippet] = field(default_factory=list)
    duration_seconds: int | None = None


def youtube_id(url: str) -> str:
    """Pull the video id out of whatever form of link was pasted.

    Handles watch URLs, youtu.be, /shorts/, /embed/, /live/, extra query
    parameters, and a bare id pasted on its own - which is what happens when
    someone copies from the address bar of the mobile app.
    """
    raw = (url or "").strip()
    if not raw:
        raise VideoUnreadable("Paste a YouTube link.")
    if VIDEO_ID.match(raw):
        return raw

    if "//" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")

    candidate: str | None = None
    if host in ("youtu.be",):
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parts[0] in ("shorts", "embed", "live", "v"):
            candidate = parts[1] if len(parts) > 1 else None
        else:
            candidate = parse_qs(parsed.query).get("v", [None])[0]

    if candidate and VIDEO_ID.match(candidate):
        return candidate
    raise VideoUnreadable("That does not look like a YouTube link.")


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def at_second(video_id: str, second: int | None) -> str:
    """A link that opens the video at the moment a concept is explained."""
    if second is None:
        return watch_url(video_id)
    return f"{watch_url(video_id)}&t={int(second)}s"


async def fetch_metadata(video_id: str) -> tuple[str | None, str | None]:
    """Title and channel, from oEmbed. Never fatal: a video with no title is still
    a video, and failing the whole upload over a missing heading would be absurd."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                OEMBED, params={"url": watch_url(video_id), "format": "json"}
            )
            response.raise_for_status()
            body = response.json()
        return body.get("title"), body.get("author_name")
    except Exception:
        return None, None


def _assemble(snippets: list[Snippet]) -> str:
    """Timestamped text, so the model can say where in the video a concept lives.

    One stamp per line of roughly a sentence, rather than per caption cue: cues
    arrive every two or three seconds and a stamp on each buries the words.
    """
    lines: list[str] = []
    buffer: list[str] = []
    start = snippets[0].start if snippets else 0.0

    for snippet in snippets:
        buffer.append(snippet.text.strip())
        if sum(len(part) for part in buffer) >= 220:
            lines.append(f"[{int(start)}s] {' '.join(buffer)}")
            buffer = []
            start = snippet.start
    if buffer:
        lines.append(f"[{int(start)}s] {' '.join(buffer)}")
    return "\n".join(lines)


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("en",)) -> Transcript:
    """The captions, as timestamped text.

    Synchronous and blocking - the library is - so callers run it off the event
    loop. Every failure is turned into one sentence the student can act on;
    the library's own exceptions name internals they did not ask about.
    """
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        AgeRestricted,
        CouldNotRetrieveTranscript,
        IpBlocked,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=list(languages))
    except NoTranscriptFound:
        raise VideoUnreadable(
            "That video has no English captions. Paste the transcript yourself and "
            "it will be read from that instead."
        ) from None
    except TranscriptsDisabled:
        raise VideoUnreadable(
            "Captions are turned off for that video, so there is nothing to read. "
            "Paste the transcript yourself instead."
        ) from None
    except (VideoUnavailable, AgeRestricted):
        raise VideoUnreadable(
            "That video cannot be opened - it may be private or removed."
        ) from None
    except IpBlocked:
        raise VideoUnreadable(
            "YouTube refused the request for captions from this machine. Paste the "
            "transcript yourself instead."
        ) from None
    except CouldNotRetrieveTranscript as exc:
        raise VideoUnreadable(f"The captions could not be fetched ({type(exc).__name__}).") from exc

    snippets = [Snippet(start=float(s.start), text=s.text) for s in fetched.snippets]
    if not snippets:
        raise VideoUnreadable("That video's captions came back empty.")

    last = fetched.snippets[-1]
    duration = int(float(last.start) + float(getattr(last, "duration", 0) or 0))
    return Transcript(text=_assemble(snippets), snippets=snippets, duration_seconds=duration)


def from_pasted(text: str) -> Transcript:
    """A transcript the student pasted. No timestamps, so concepts get no moment."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise VideoUnreadable("That transcript is empty.")
    return Transcript(text=cleaned)


# A long lecture can run past what is worth sending in one prompt. Cut it rather
# than fail, and say so, so a half-read video is never mistaken for a full one.
MAX_TRANSCRIPT_CHARS = 120_000


def clip(transcript: str) -> tuple[str, bool]:
    if len(transcript) <= MAX_TRANSCRIPT_CHARS:
        return transcript, False
    return transcript[:MAX_TRANSCRIPT_CHARS], True
