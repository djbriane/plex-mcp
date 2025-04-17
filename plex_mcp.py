"""
Module: plex_mcp

This module provides tools for interacting with a Plex server via FastMCP.
It includes functions to search for movies, retrieve movie details, manage playlists,
and obtain recent movies and movie genres. Logging and asynchronous execution are used
to handle non-blocking I/O and to provide informative error messages.
"""

# --- Import Statements ---
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import os
import asyncio
import logging

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, Unauthorized
from mcp.server.fastmcp import FastMCP

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,  # Use DEBUG for more verbosity during development
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- FastMCP Server Initialization ---
mcp = FastMCP("plex")

# --- Utility Formatting Functions ---

def format_movie(movie) -> str:
    """
    Format a movie object into a human-readable string.
    
    Parameters:
        movie: A Plex movie object.
        
    Returns:
        A formatted string containing movie details.
    """
    title = getattr(movie, 'title', 'Unknown Title')
    year = getattr(movie, 'year', 'Unknown Year')
    summary = getattr(movie, 'summary', 'No summary available')
    duration = getattr(movie, 'duration', 0) // 60000 if hasattr(movie, 'duration') else 0
    rating = getattr(movie, 'rating', 'Unrated')
    studio = getattr(movie, 'studio', 'Unknown Studio')
    directors = [director.tag for director in getattr(movie, 'directors', [])[:3]]
    actors = [role.tag for role in getattr(movie, 'roles', [])[:5]]
    
    return (
        f"Title: {title} ({year})\n"
        f"Rating: {rating}\n"
        f"Duration: {duration} minutes\n"
        f"Studio: {studio}\n"
        f"Directors: {', '.join(directors) if directors else 'Unknown'}\n"
        f"Starring: {', '.join(actors) if actors else 'Unknown'}\n"
        f"Summary: {summary}\n"
    )

def format_playlist(playlist) -> str:
    """
    Format a playlist into a human-readable string.
    
    Parameters:
        playlist: A Plex playlist object.
        
    Returns:
        A formatted string containing playlist details.
    """
    duration_mins = sum(item.duration for item in playlist.items()) // 60000 if playlist.items() else 0
    updated = (
        playlist.updatedAt.strftime('%Y-%m-%d %H:%M:%S')
        if hasattr(playlist, 'updatedAt') else 'Unknown'
    )
    return (
        f"Playlist: {playlist.title}\n"
        f"Items: {len(playlist.items())}\n"
        f"Duration: {duration_mins} minutes\n"
        f"Last Updated: {updated}\n"
    )

# --- Plex Client Class ---

class PlexClient:
    """
    Encapsulate the Plex connection logic.
    This class handles initialization and caching of the PlexServer instance.
    """
    def __init__(self, server_url: str = None, token: str = None):
        self.server_url = server_url or os.environ.get("PLEX_SERVER_URL", "").rstrip("/")
        self.token = token or os.environ.get("PLEX_TOKEN")
        
        if not self.server_url or not self.token:
            raise ValueError("Missing required configuration: Ensure PLEX_SERVER_URL and PLEX_TOKEN are set.")
        
        self._server = None

    def get_server(self) -> PlexServer:
        """
        Return a cached PlexServer instance or initialize one if not already available.
        
        Returns:
            A connected PlexServer instance.
        
        Raises:
            Exception: If connection initialization fails.
        """
        if self._server is None:
            try:
                self._server = PlexServer(self.server_url, self.token)
                logger.info("Successfully initialized PlexServer.")
            except Exception as exc:
                logger.exception("Error initializing Plex server: %s", exc)
                raise Exception(f"Error initializing Plex server: {exc}")
        return self._server

# --- Data Classes ---

@dataclass
class MovieSearchParams:
    title:        Optional[str]  = None
    year:         Optional[int]  = None
    director:     Optional[str]  = None
    studio:       Optional[str]  = None
    genre:        Optional[str]  = None
    actor:        Optional[str]  = None
    rating:       Optional[str]  = None
    country:      Optional[str]  = None
    language:     Optional[str]  = None
    watched:      Optional[bool] = None   # True=only watched, False=only unwatched
    min_duration: Optional[int]  = None   # in minutes
    max_duration: Optional[int]  = None   # in minutes

    def to_filters(self) -> Dict[str, Any]:
        FIELD_MAP = {
            "title":        "title",
            "year":         "year",
            "director":     "director",
            "studio":       "studio",
            "genre":        "genre",
            "actor":        "actor",
            "rating":       "rating",
            "country":      "country",
            "language":     "language",
            "watched":      "unwatched",
            "min_duration": "minDuration",
            "max_duration": "maxDuration",
        }

        filters: Dict[str, Any] = {"libtype": "movie"}

        for field_name, plex_arg in FIELD_MAP.items():
            value = getattr(self, field_name)
            if value is None:
                continue

            if field_name == "watched":
                # invert for Plex 'unwatched' flag
                filters["unwatched"] = not value
                continue

            if field_name in ("min_duration", "max_duration"):
                # convert minutes to milliseconds
                filters[plex_arg] = value * 60_000
                continue

            filters[plex_arg] = value

        return filters


# --- Global Singleton and Access Functions ---

_plex_client_instance: PlexClient = None

def get_plex_client() -> PlexClient:
    """
    Return the singleton PlexClient instance, initializing it if necessary.
    
    Returns:
        A PlexClient instance.
    """
    global _plex_client_instance
    if _plex_client_instance is None:
        _plex_client_instance = PlexClient()
    return _plex_client_instance

async def get_plex_server() -> PlexServer:
    """
    Asynchronously get a PlexServer instance via the singleton PlexClient.
    
    Returns:
        A PlexServer instance.
        
    Raises:
        Exception: When the Plex server connection fails.
    """
    try:
        plex_client = get_plex_client()  # Singleton accessor
        plex = await asyncio.to_thread(plex_client.get_server)
        return plex
    except Exception as e:
        logger.exception("Failed to get Plex server instance")
        raise e

# --- Tool Methods ---

@mcp.tool()
async def search_movies(
    title:        Optional[str]  = None,
    year:         Optional[int]  = None,
    director:     Optional[str]  = None,
    studio:       Optional[str]  = None,
    genre:        Optional[str]  = None,
    actor:        Optional[str]  = None,
    rating:       Optional[str]  = None,
    country:      Optional[str]  = None,
    language:     Optional[str]  = None,
    watched:      Optional[bool] = None,
    min_duration: Optional[int]  = None,
    max_duration: Optional[int]  = None,
) -> str:
    """
    Search for movies in your Plex library using optional filters.
    
    Parameters:
        title: Optional title or substring to match.
        year: Optional release year to filter by.
        director: Optional director name to filter by.
        studio: Optional studio name to filter by.
        genre: Optional genre tag to filter by.
        actor: Optional actor name to filter by.
        rating: Optional rating (e.g., "PG-13") to filter by.
        country: Optional country of origin to filter by.
        language: Optional audio or subtitle language to filter by.
        watched: Optional boolean; True returns only watched movies, False only unwatched.
        min_duration: Optional minimum duration in minutes.
        max_duration: Optional maximum duration in minutes.
        
    Returns:
        A formatted string of up to 5 matching movies (with a count of any additional results),
        or an error message if the search fails or no movies are found.
    """
    params = MovieSearchParams(
        title, year, director, studio,
        genre, actor, rating, country,
        language, watched, min_duration, max_duration
    )
    filters = params.to_filters()
    logger.info("Searching Plex with filters: %r", filters)

    try:
        plex = await get_plex_server()
        movies = await asyncio.to_thread(plex.library.search, **filters)
    except Exception as e:
        logger.exception("search_movies failed connecting to Plex")
        return f"ERROR: Could not search Plex. {e}"

    if not movies:
        return f"No movies found matching filters {filters!r}."

    results: List[str] = []
    for i, m in enumerate(movies[:5], start=1):
        results.append(f"Result #{i}:\nKey: {m.ratingKey}\n{format_movie(m)}")

    if len(movies) > 5:
        results.append(f"\n... and {len(movies)-5} more results.")

    return "\n---\n".join(results)

@mcp.tool()
async def get_movie_details(movie_key: str) -> str:
    """
    Get detailed information about a specific movie.
    
    Parameters:
        movie_key: The key identifying the movie.
        
    Returns:
        A formatted string with movie details or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        key = int(movie_key)
        sections = await asyncio.to_thread(plex.library.sections)
        movie = None
        for section in sections:
            if section.type == 'movie':
                try:
                    items = await asyncio.to_thread(lambda s=section, k=key: s.search(filters={"ratingKey": k}))
                    if items:
                        movie = items[0]
                        break
                except Exception:
                    continue
        if not movie:
            all_movies = await asyncio.to_thread(lambda: plex.library.search(libtype="movie"))
            for m in all_movies:
                if m.ratingKey == key:
                    movie = m
                    break
        if not movie:
            return f"No movie found with key {movie_key}."
        return format_movie(movie)
    except NotFound:
        return f"ERROR: Movie with key {movie_key} not found."
    except Exception as e:
        logger.exception("Failed to fetch movie details for key '%s'", movie_key)
        return f"ERROR: Failed to fetch movie details. {str(e)}"

@mcp.tool()
async def list_playlists() -> str:
    """
    List all playlists in the Plex server.
    
    Returns:
        A formatted string of playlists or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        playlists = await asyncio.to_thread(plex.playlists)
        if not playlists:
            return "No playlists found in your Plex server."
        formatted_playlists = []
        for i, playlist in enumerate(playlists, 1):
            formatted_playlists.append(
                f"Playlist #{i}:\nKey: {playlist.ratingKey}\n{format_playlist(playlist)}"
            )
        return "\n---\n".join(formatted_playlists)
    except Exception as e:
        logger.exception("Failed to fetch playlists")
        return f"ERROR: Failed to fetch playlists. {str(e)}"

@mcp.tool()
async def get_playlist_items(playlist_key: str) -> str:
    """
    Get the items in a specific playlist.
    
    Parameters:
        playlist_key: The key of the playlist to retrieve items from.
        
    Returns:
        A formatted string of playlist items or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        key = int(playlist_key)
        all_playlists = await asyncio.to_thread(plex.playlists)
        playlist = next((p for p in all_playlists if p.ratingKey == key), None)
        if not playlist:
            return f"No playlist found with key {playlist_key}."

        items = playlist.items()
        if not items:
            return "No items found in this playlist."

        formatted_items = []
        for i, item in enumerate(items, 1):
            title = item.title
            year = getattr(item, 'year', '')
            type_str = item.type.capitalize()
            formatted_items.append(f"{i}. {title} ({year}) - {type_str}")
        return "\n".join(formatted_items)
    except NotFound:
        return f"ERROR: Playlist with key {playlist_key} not found."
    except Exception as e:
        logger.exception("Failed to fetch items for playlist key '%s'", playlist_key)
        return f"ERROR: Failed to fetch playlist items. {str(e)}"

@mcp.tool()
async def create_playlist(name: str, movie_keys: str) -> str:
    """
    Create a new playlist with specified movies.
    
    Parameters:
        name: The desired name for the new playlist.
        movie_keys: A comma-separated string of movie keys to include.
        
    Returns:
        A success message with playlist details or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        movie_key_list = [int(key.strip()) for key in movie_keys.split(",") if key.strip()]
        if not movie_key_list:
            return "ERROR: No valid movie keys provided."

        logger.info("Creating playlist '%s' with movie keys: %s", name, movie_keys)
        all_movies = await asyncio.to_thread(lambda: plex.library.search(libtype="movie"))
        logger.info("Found %d total movies in library", len(all_movies))
        movie_map = {movie.ratingKey: movie for movie in all_movies}
        movies = []
        not_found_keys = []

        for key in movie_key_list:
            if key in movie_map:
                movies.append(movie_map[key])
                logger.info("Found movie: %s (Key: %d)", movie_map[key].title, key)
            else:
                not_found_keys.append(key)
                logger.warning("Could not find movie with key: %d", key)

        if not_found_keys:
            return f"ERROR: Some movie keys were not found: {', '.join(str(k) for k in not_found_keys)}"
        if not movies:
            return "ERROR: No valid movies found with the provided keys."

        try:
            playlist_future = asyncio.create_task(
                asyncio.to_thread(lambda: plex.createPlaylist(name, items=movies))
            )
            playlist = await asyncio.wait_for(playlist_future, timeout=15.0)
            logger.info("Playlist created successfully: %s", playlist.title)
            return f"Successfully created playlist '{name}' with {len(movies)} movie(s).\nPlaylist Key: {playlist.ratingKey}"
        except asyncio.TimeoutError:
            logger.warning("Playlist creation is taking longer than expected for '%s'", name)
            return ("PENDING: Playlist creation is taking longer than expected. "
                    "The operation might still complete in the background. "
                    "Please check your Plex server to confirm.")
    except ValueError as e:
        logger.error("Invalid input format for movie keys: %s", e)
        return f"ERROR: Invalid input format. Please check movie keys are valid numbers. {str(e)}"
    except Exception as e:
        logger.exception("Error creating playlist")
        return f"ERROR: Failed to create playlist. {str(e)}"

@mcp.tool()
async def delete_playlist(playlist_key: str) -> str:
    """
    Delete a playlist from the Plex server.
    
    Parameters:
        playlist_key: The key of the playlist to delete.
        
    Returns:
        A success message if deletion is successful, or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        key = int(playlist_key)
        all_playlists = await asyncio.to_thread(plex.playlists)
        playlist = next((p for p in all_playlists if p.ratingKey == key), None)
        if not playlist:
            return f"No playlist found with key {playlist_key}."
        await asyncio.to_thread(playlist.delete)
        logger.info("Playlist '%s' with key %s successfully deleted.", playlist.title, playlist_key)
        return f"Successfully deleted playlist '{playlist.title}' with key {playlist_key}."
    except NotFound:
        return f"ERROR: Playlist with key {playlist_key} not found."
    except Exception as e:
        logger.exception("Failed to delete playlist with key '%s'", playlist_key)
        return f"ERROR: Failed to delete playlist. {str(e)}"

@mcp.tool()
async def add_to_playlist(playlist_key: str, movie_key: str) -> str:
    """
    Add a movie to an existing playlist.
    
    Parameters:
        playlist_key: The key of the playlist.
        movie_key: The key of the movie to add.
        
    Returns:
        A success message if the movie is added, or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        p_key = int(playlist_key)
        m_key = int(movie_key)
        all_playlists = await asyncio.to_thread(plex.playlists)
        playlist = next((p for p in all_playlists if p.ratingKey == p_key), None)
        if not playlist:
            return f"No playlist found with key {playlist_key}."

        sections = await asyncio.to_thread(plex.library.sections)
        movie_sections = [section for section in sections if section.type == 'movie']
        movie = None
        for section in movie_sections:
            try:
                items = await asyncio.to_thread(lambda s=section, k=m_key: s.search(filters={"ratingKey": k}))
                if items:
                    movie = items[0]
                    break
            except Exception:
                continue
        if not movie:
            all_movies = await asyncio.to_thread(lambda: plex.library.search(libtype="movie"))
            for m in all_movies:
                if m.ratingKey == m_key:
                    movie = m
                    break
        if not movie:
            return f"No movie found with key {movie_key}."

        await asyncio.to_thread(lambda p=playlist, m=movie: p.addItems([m]))
        logger.info("Added movie '%s' to playlist '%s'", movie.title, playlist.title)
        return f"Successfully added '{movie.title}' to playlist '{playlist.title}'."
    except NotFound as e:
        return f"ERROR: Item not found. {str(e)}"
    except Exception as e:
        logger.exception("Failed to add movie to playlist")
        return f"ERROR: Failed to add movie to playlist. {str(e)}"

@mcp.tool()
async def recent_movies(count: int = 5) -> str:
    """
    Get recently added movies from the Plex library.
    
    Parameters:
        count: The maximum number of recent movies to return.
        
    Returns:
        A formatted string of recent movies or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        movie_sections = [section for section in plex.library.sections() if section.type == 'movie']
        if not movie_sections:
            return "No movie libraries found in your Plex server."
        all_recent = []
        for section in movie_sections:
            recent = await asyncio.to_thread(section.recentlyAdded, maxresults=count)
            all_recent.extend(recent)
        all_recent.sort(key=lambda x: x.addedAt, reverse=True)
        recent_movies_list = all_recent[:count]
        if not recent_movies_list:
            return "No recent movies found in your Plex library."
        formatted_movies = []
        for i, movie in enumerate(recent_movies_list, 1):
            formatted_movies.append(
                f"Recent Movie #{i}:\nKey: {movie.ratingKey}\nAdded: {movie.addedAt.strftime('%Y-%m-%d')}\n{format_movie(movie)}"
            )
        return "\n---\n".join(formatted_movies)
    except Exception as e:
        logger.exception("Failed to fetch recent movies")
        return f"ERROR: Failed to fetch recent movies. {str(e)}"

@mcp.tool()
async def get_movie_genres(movie_key: str) -> str:
    """
    Get genres for a specific movie.
    
    Parameters:
        movie_key: The key of the movie.
        
    Returns:
        A formatted string of movie genres or an error message.
    """
    try:
        plex = await get_plex_server()
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        key = int(movie_key)
        sections = await asyncio.to_thread(plex.library.sections)
        movie = None
        for section in sections:
            try:
                items = await asyncio.to_thread(lambda s=section, k=key: s.search(filters={"ratingKey": k}))
                if items:
                    movie = items[0]
                    break
            except Exception:
                continue
        if not movie:
            all_movies = await asyncio.to_thread(lambda: plex.library.search(libtype="movie"))
            for m in all_movies:
                if m.ratingKey == key:
                    movie = m
                    break
        if not movie:
            return f"No movie found with key {movie_key}."
        genres = [genre.tag for genre in movie.genres] if hasattr(movie, 'genres') else []
        if not genres:
            return f"No genres found for movie '{movie.title}'."
        return f"Genres for '{movie.title}':\n{', '.join(genres)}"
    except NotFound:
        return f"ERROR: Movie with key {movie_key} not found."
    except Exception as e:
        logger.exception("Failed to fetch genres for movie with key '%s'", movie_key)
        return f"ERROR: Failed to fetch movie genres. {str(e)}"

# --- Main Execution ---
if __name__ == "__main__":
    mcp.run(transport='stdio')
    