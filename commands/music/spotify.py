import logging
from typing import Optional

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

logger = logging.getLogger("bot")

sp: Optional[object] = None

if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
            )
        )
        logger.info("Spotify client initialized")
    except Exception as e:
        logger.error("Failed to initialize Spotify client: %s", e)
else:
    logger.warning("Spotify credentials not configured")


def spotify_to_queries(url: str) -> tuple[list[str], Optional[str]]:
    if not sp:
        raise Exception("Fitur Spotify tidak dikonfigurasi.")

    queries: list[str] = []
    info: Optional[str] = None

    try:
        if "track" in url:
            track = sp.track(url)
            queries.append(f"{track['name']} {track['artists'][0]['name']}")
            info = f"ℹ️ Menambahkan lagu Spotify: **{track['name']}**"

        elif "album" in url:
            album = sp.album(url)
            for item in album["tracks"]["items"]:
                queries.append(f"{item['name']} {album['artists'][0]['name']}")
            info = f"ℹ️ Menambahkan **{len(queries)}** lagu dari album: **{album['name']}**"

        elif "playlist" in url:
            results = sp.playlist_items(url)
            tracks = results["items"]
            while results["next"]:
                results = sp.next(results)
                tracks.extend(results["items"])
            for item in tracks:
                if item["track"]:
                    t = item["track"]
                    queries.append(f"{t['name']} {t['artists'][0]['name']}")
            name = sp.playlist(url, fields="name")["name"]
            info = f"ℹ️ Menambahkan **{len(queries)}** lagu dari playlist: **{name}**"

        elif "artist" in url:
            artist = sp.artist(url)
            for track in sp.artist_top_tracks(url)["tracks"]:
                queries.append(f"{track['name']} {artist['name']}")
            info = f"ℹ️ Menambahkan **{len(queries)}** top tracks dari: **{artist['name']}**"

        else:
            raise Exception("Link Spotify tidak dikenali.")
    except Exception as e:
        logger.error("Spotify extraction error: %s", e)
        raise Exception(f"Gagal mengambil data dari Spotify: {e}") from e

    return queries, info
