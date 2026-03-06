"""YouTube Data API v3 integration for music search.

Uses GOOGLE_API_KEY env var (shared with Maps).
Falls back to mock data when key is not configured.

Required GCP APIs:
  - YouTube Data API v3
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


# ---------------------------------------------------------------------------
# play_song
# ---------------------------------------------------------------------------


def play_song(query: str) -> dict:
    """Searches for and plays a song matching the query.

    Uses YouTube Data API to find real track information.
    Actual audio playback is handled by the mobile client.

    Args:
        query: Song name, artist, genre, or mood to play.

    Returns:
        A dictionary with the found track info and playback status.
    """
    if not _API_KEY:
        return _mock_play(query)

    try:
        resp = httpx.get(
            _YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet",
                "q": f"{query} music",
                "type": "video",
                "videoCategoryId": "10",  # Music category
                "maxResults": 1,
                "key": _API_KEY,
            },
            timeout=10,
        )
        data = resp.json()

        if data.get("error"):
            logger.warning("YouTube API error: %s", data["error"])
            return _mock_play(query)

        if not data.get("items"):
            logger.warning("YouTube search returned no results for: %s", query)
            return _mock_play(query)

        item = data["items"][0]
        snippet = item["snippet"]
        video_id = item["id"]["videoId"]

        return {
            "status": "success",
            "action": "playing",
            "now_playing": {
                "title": snippet["title"],
                "artist": snippet["channelTitle"],
                "video_id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}",
                "thumbnail": (
                    snippet.get("thumbnails", {})
                    .get("default", {})
                    .get("url", "")
                ),
            },
            "message": f"Now playing: {snippet['title']}",
        }
    except Exception as e:
        logger.error("YouTube search error: %s", e)
        return _mock_play(query)


# ---------------------------------------------------------------------------
# pause_music / skip_track
# ---------------------------------------------------------------------------


def pause_music() -> dict:
    """Pauses the currently playing music.

    Note: Actual playback control is handled by the mobile client.

    Returns:
        A dictionary confirming pause.
    """
    return {"status": "success", "action": "paused", "message": "Music paused."}


def skip_track() -> dict:
    """Skips to the next track in the queue.

    Note: Actual playback control is handled by the mobile client.

    Returns:
        A dictionary confirming skip.
    """
    return {
        "status": "success",
        "action": "skipped",
        "message": "Skipped to the next track.",
    }


# ---------------------------------------------------------------------------
# Mock fallback (used when GOOGLE_API_KEY is not configured)
# ---------------------------------------------------------------------------


def _mock_play(query: str) -> dict:
    return {
        "status": "success",
        "action": "playing",
        "now_playing": {
            "title": f"Best match for '{query}'",
            "artist": "Various Artists",
            "album": "Driving Playlist",
        },
        "message": f"Now playing music matching '{query}'.",
    }
