import logging
import random
import re
from typing import Optional

import aiohttp

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, OPENROUTER_API_KEY
from commands.ai import ask_openrouter

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


def _parse_title_artist(title: str) -> tuple[str, str]:
    for sep in (" - ", " — ", " – ", " | "):
        if sep in title:
            parts = title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    if " by " in title.lower():
        idx = title.lower().index(" by ")
        return title[:idx].strip(), title[idx + 4:].strip()
    words = title.split()
    if len(words) > 1:
        return " ".join(words[:len(words) // 2]), " ".join(words[len(words) // 2:])
    return title, ""


async def ai_recommend_music(
    title: str,
    exclude: set[str] | None = None,
    session: aiohttp.ClientSession | None = None,
) -> Optional[str]:
    if not OPENROUTER_API_KEY or not session:
        return None

    exclude = exclude or set()
    artist, track_name = _parse_title_artist(title)

    if track_name:
        song_desc = f"'{track_name}' by {artist}"
    else:
        song_desc = f"'{title}'"

    prompt = (
        f"Give me exactly 5 song recommendations that are similar in mood, "
        f"style, or genre to {song_desc}. "
        f"Format: one per line, only 'Song Title - Artist Name'. "
        f"No numbers, no explanations, no extra text."
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a music recommendation engine. "
                "IMPORTANT: only recommend real existing MUSIC songs by the original artist. "
                "Never suggest podcasts, audiobooks, sound effects. "
                "Always respond with exactly 5 lines. "
                "Each line must be: Song Title - Artist Name. "
                "No other text."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        reply = await ask_openrouter(session, messages)

        if not reply or "❌" in reply:
            return None

        candidates = []
        for line in reply.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            clean = re.sub(r"^[\d\.\)\-\s]+", "", line).strip()
            clean = re.sub(r"[*\"`]", "", clean).strip()
            if " - " in clean:
                parts = clean.split(" - ", 1)
                song = parts[0].strip()
                art = parts[1].strip()
            elif " by " in clean.lower():
                idx = clean.lower().index(" by ")
                song = clean[:idx].strip()
                art = clean[idx + 4:].strip()
            else:
                continue

            key = f"{song.lower()} {art.lower()}"
            if key not in exclude:
                candidates.append(f"{song} {art}")

        if candidates:
            chosen = random.choice(candidates)
            logger.info("AI recommend for '%s' -> '%s'", title, chosen)
            return chosen

        return None
    except Exception as e:
        logger.warning("AI recommend failed for '%s': %s", title, e)
        return None
