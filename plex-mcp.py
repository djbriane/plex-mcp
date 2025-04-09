from typing import Any, Dict, List, Optional
import os
import asyncio
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, Unauthorized
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("plex")

# Utility formatting functions (unchanged)
def format_movie(movie) -> str:
    """Format a movie object into a readable string."""
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
    """Format a playlist into a readable string."""
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

# Encapsulate Plex connection logic in a dedicated class
class PlexClient:
    def __init__(self, server_url: str = None, token: str = None):
        self.server_url = server_url or os.environ.get("PLEX_SERVER_URL", "").rstrip("/")
        self.token = token or os.environ.get("PLEX_TOKEN")
        
        if not self.server_url or not self.token:
            raise ValueError("Missing required configuration: Ensure PLEX_SERVER_URL and PLEX_TOKEN are set.")
        
        self._server = None

    def get_server(self) -> PlexServer:
        """Returns a cached PlexServer instance or initializes one if needed."""
        if self._server is None:
            try:
                self._server = PlexServer(self.server_url, self.token)
            except Exception as exc:
                raise Exception(f"Error initializing Plex server: {exc}")
        return self._server

# Global singleton instance for PlexClient
_plex_client_instance: PlexClient = None

def get_plex_client() -> PlexClient:
    """Return the singleton PlexClient instance, initializing it if necessary."""
    global _plex_client_instance
    if _plex_client_instance is None:
        _plex_client_instance = PlexClient()
    return _plex_client_instance

@mcp.tool()
async def search_movies(query: str) -> str:
    """Search for movies in your Plex library."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        movies = await asyncio.to_thread(plex.library.search, title=query, libtype="movie")
        if not movies:
            return f"No movies found matching '{query}'."
        formatted_results = []
        for i, movie in enumerate(movies[:5], 1):  # Limit to 5 results
            formatted_results.append(f"Result #{i}:\nKey: {movie.ratingKey}\n{format_movie(movie)}")
        if len(movies) > 5:
            formatted_results.append(f"\n... and {len(movies) - 5} more results.")
        return "\n---\n".join(formatted_results)
    except Exception as e:
        return f"ERROR: Failed to search movies. {str(e)}"


@mcp.tool()
async def get_movie_details(movie_key: str) -> str:
    """Get detailed information about a specific movie."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
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
        return f"ERROR: Failed to fetch movie details. {str(e)}"


@mcp.tool()
async def list_playlists() -> str:
    """List all playlists in your Plex server."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
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
        return f"ERROR: Failed to fetch playlists. {str(e)}"


@mcp.tool()
async def get_playlist_items(playlist_key: str) -> str:
    """Get the items in a specific playlist."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
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
        return f"ERROR: Failed to fetch playlist items. {str(e)}"


@mcp.tool()
async def create_playlist(name: str, movie_keys: str) -> str:
    """Create a new playlist with specified movies."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        movie_key_list = [int(key.strip()) for key in movie_keys.split(",") if key.strip()]
        if not movie_key_list:
            return "ERROR: No valid movie keys provided."

        print(f"Creating playlist '{name}' with movie keys: {movie_keys}")
        all_movies = await asyncio.to_thread(lambda: plex.library.search(libtype="movie"))
        print(f"Found {len(all_movies)} total movies in library")
        movie_map = {movie.ratingKey: movie for movie in all_movies}
        movies = []
        not_found_keys = []

        for key in movie_key_list:
            if key in movie_map:
                movies.append(movie_map[key])
                print(f"Found movie: {movie_map[key].title} (Key: {key})")
            else:
                not_found_keys.append(key)
                print(f"Could not find movie with key: {key}")

        if not_found_keys:
            return f"ERROR: Some movie keys were not found: {', '.join(str(k) for k in not_found_keys)}"
        if not movies:
            return "ERROR: No valid movies found with the provided keys."

        try:
            playlist_future = asyncio.create_task(
                asyncio.to_thread(lambda: plex.createPlaylist(name, items=movies))
            )
            playlist = await asyncio.wait_for(playlist_future, timeout=15.0)
            print(f"Playlist created successfully: {playlist.title}")
            return f"Successfully created playlist '{name}' with {len(movies)} movie(s).\nPlaylist Key: {playlist.ratingKey}"
        except asyncio.TimeoutError:
            return ("PENDING: Playlist creation is taking longer than expected. "
                    "The operation might still complete in the background. "
                    "Please check your Plex server to confirm.")
    except ValueError as e:
        return f"ERROR: Invalid input format. Please check movie keys are valid numbers. {str(e)}"
    except Exception as e:
        print(f"Error creating playlist: {str(e)}")
        return f"ERROR: Failed to create playlist. {str(e)}"


@mcp.tool()
async def delete_playlist(playlist_key: str) -> str:
    """Delete a playlist from your Plex server."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
    except Exception as e:
        return f"ERROR: Could not connect to Plex server. {str(e)}"

    try:
        key = int(playlist_key)
        all_playlists = await asyncio.to_thread(plex.playlists)
        playlist = next((p for p in all_playlists if p.ratingKey == key), None)
        if not playlist:
            return f"No playlist found with key {playlist_key}."
        await asyncio.to_thread(playlist.delete)
        return f"Successfully deleted playlist '{playlist.title}' with key {playlist_key}."
    except NotFound:
        return f"ERROR: Playlist with key {playlist_key} not found."
    except Exception as e:
        return f"ERROR: Failed to delete playlist. {str(e)}"


@mcp.tool()
async def add_to_playlist(playlist_key: str, movie_key: str) -> str:
    """Add a movie to an existing playlist."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
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
        return f"Successfully added '{movie.title}' to playlist '{playlist.title}'."
    except NotFound as e:
        return f"ERROR: Item not found. {str(e)}"
    except Exception as e:
        return f"ERROR: Failed to add movie to playlist. {str(e)}"


@mcp.tool()
async def recent_movies(count: int = 5) -> str:
    """Get recently added movies from your Plex library."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
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
        return f"ERROR: Failed to fetch recent movies. {str(e)}"


@mcp.tool()
async def get_movie_genres(movie_key: str) -> str:
    """Get genres for a specific movie."""
    try:
        plex_client = get_plex_client()
        plex = await asyncio.to_thread(plex_client.get_server)
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
        return f"ERROR: Failed to fetch movie genres. {str(e)}"
    
if __name__ == "__main__":
    mcp.run(transport='stdio')