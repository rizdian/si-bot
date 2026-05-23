import logging
import random
from typing import Optional

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

logger = logging.getLogger("bot")

sp: Optional[object] = None
_valid_genre_seeds: set[str] = set()

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
        try:
            _valid_genre_seeds.update(sp.recommendation_genre_seeds().get("genres", []))
        except Exception:
            pass
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


def spotify_search_track(query: str) -> Optional[str]:
    if not sp:
        return None

    try:
        results = sp.search(q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return None

        track = tracks[0]
        artist_name = track["artists"][0]["name"]
        track_name = track["name"]
        refined_query = f"{track_name} {artist_name}"
        logger.info(
            "Spotify search hit for '%s' -> '%s'", query, refined_query,
        )
        return refined_query
    except Exception as e:
        logger.warning("Spotify search failed for '%s': %s", query, e)
        return None


def spotify_recommend(title: str, exclude: set[str] | None = None) -> Optional[str]:
    if not sp:
        return None

    exclude = exclude or set()

    try:
        results = sp.search(q=title, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return None

        track = tracks[0]
        track_id = track["id"]
        artist_id = track["artists"][0]["id"]

        seed_genres = []
        try:
            artist_data = sp.artist(artist_id)
            genres = artist_data.get("genres", [])
            if _valid_genre_seeds:
                seed_genres = [g for g in genres if g in _valid_genre_seeds][:2]
            else:
                seed_genres = genres[:1]
        except Exception:
            pass

        seeds = {"seed_tracks": [track_id], "limit": 8}
        if artist_id:
            seeds["seed_artists"] = [artist_id]
        if seed_genres:
            seeds["seed_genres"] = seed_genres[:2]

        try:
            recs = sp.recommendations(**seeds)
        except Exception:
            seeds.pop("seed_genres", None)
            recs = sp.recommendations(**seeds)
        rec_tracks = recs.get("tracks", [])

        candidates = []
        for t in rec_tracks:
            artist_name = t["artists"][0]["name"]
            track_name = t["name"]
            key = f"{track_name.lower()} {artist_name.lower()}"
            if key not in exclude:
                candidates.append(f"{track_name} {artist_name}")

        if candidates:
            chosen = random.choice(candidates)
            logger.info("Spotify recommend for '%s' -> '%s'", title, chosen)
            return chosen

        return None
    except Exception as e:
        logger.warning("Spotify recommend failed for '%s': %s", title, e)
        return None


def spotify_fallback_artist_track(title: str, exclude: set[str] | None = None) -> Optional[str]:
    if not sp:
        return None

    exclude = exclude or set()

    try:
        results = sp.search(q=title, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return None

        artist_id = tracks[0]["artists"][0]["id"]

        related_artists = sp.artist_related_artists(artist_id).get("artists", [])
        if not related_artists:
            return None

        random.shuffle(related_artists)

        for related in related_artists[:3]:
            top_tracks = sp.artist_top_tracks(related["id"]).get("tracks", [])
            random.shuffle(top_tracks)
            for t in top_tracks:
                artist_name = t["artists"][0]["name"]
                track_name = t["name"]
                key = f"{track_name.lower()} {artist_name.lower()}"
                if key not in exclude:
                    query = f"{track_name} {artist_name}"
                    logger.info("Spotify related artist for '%s' -> '%s'", title, query)
                    return query

        return None
    except Exception as e:
        logger.warning("Spotify fallback artist failed for '%s': %s", title, e)
        return None
