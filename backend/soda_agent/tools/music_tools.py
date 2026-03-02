def play_song(query: str) -> dict:
    """Plays a song, artist, genre, or playlist matching the query.

    Args:
        query: Song name, artist, genre, or mood to play.

    Returns:
        A dictionary confirming playback.
    """
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


def pause_music() -> dict:
    """Pauses the currently playing music.

    Returns:
        A dictionary confirming pause.
    """
    return {"status": "success", "action": "paused", "message": "Music paused."}


def skip_track() -> dict:
    """Skips to the next track in the queue.

    Returns:
        A dictionary with the next track info.
    """
    return {
        "status": "success",
        "action": "skipped",
        "now_playing": {
            "title": "Next Song",
            "artist": "Another Artist",
        },
        "message": "Skipped to the next track.",
    }
