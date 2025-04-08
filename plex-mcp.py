from typing import Any, Dict, List, Optional
import os
import asyncio
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, Unauthorized
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("plex")

# Environment variables
PLEX_TOKEN = os.environ.get("PLEX_TOKEN")
PLEX_SERVER_URL = os.environ.get("PLEX_SERVER_URL", "").rstrip("/")

# Global PlexServer instance
plex = None

def initialize_plex():
    """Initialize the PlexServer connection."""
    global plex
    
    if not PLEX_TOKEN or not PLEX_SERVER_URL:
        return False
    
    try:
        plex = PlexServer(PLEX_SERVER_URL, PLEX_TOKEN)
        return True
    except Exception as e:
        print(f"Error initializing Plex server: {str(e)}")
        return False

def format_movie(movie) -> str:
    """Format a movie object into a readable string.
    
    Args:
        movie: plexapi Movie object
        
    Returns:
        Formatted movie string
    """
    # Extract relevant information with fallbacks
    title = getattr(movie, 'title', 'Unknown Title')
    year = getattr(movie, 'year', 'Unknown Year')
    summary = getattr(movie, 'summary', 'No summary available')
    
    # Convert duration from milliseconds to minutes
    duration = getattr(movie, 'duration', 0) // 60000 if hasattr(movie, 'duration') else 0
    
    # Get rating with fallback
    rating = getattr(movie, 'rating', 'Unrated')
    
    # Get studio with fallback
    studio = getattr(movie, 'studio', 'Unknown Studio')
    
    # Get directors
    directors = []
    if hasattr(movie, 'directors'):
        directors = [director.tag for director in movie.directors[:3]]
    
    # Get actors
    actors = []
    if hasattr(movie, 'roles'):
        actors = [role.tag for role in movie.roles[:5]]
    
    return f"""
Title: {title} ({year})
Rating: {rating}
Duration: {duration} minutes
Studio: {studio}
Directors: {', '.join(directors) if directors else 'Unknown'}
Starring: {', '.join(actors) if actors else 'Unknown'}
Summary: {summary}
"""

def format_playlist(playlist) -> str:
    """Format a playlist into a readable string.
    
    Args:
        playlist: plexapi Playlist object
        
    Returns:
        Formatted playlist string
    """
    # Calculate total duration in minutes
    duration_mins = sum(item.duration for item in playlist.items()) // 60000 if playlist.items() else 0
    
    return f"""
Playlist: {playlist.title}
Items: {len(playlist.items())}
Duration: {duration_mins} minutes
Last Updated: {playlist.updatedAt.strftime('%Y-%m-%d %H:%M:%S') if hasattr(playlist, 'updatedAt') else 'Unknown'}
"""

@mcp.tool()
async def search_movies(query: str) -> str:
    """Search for movies in your Plex library.
    
    Args:
        query: Search term for finding movies
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Use the synchronous PlexAPI in a thread to avoid blocking
        movies = await asyncio.to_thread(plex.library.search, title=query, libtype="movie")
        
        if not movies:
            return f"No movies found matching '{query}'."
        
        # Format the results
        formatted_results = []
        for i, movie in enumerate(movies[:5], 1):  # Limit to 5 results
            formatted_results.append(f"Result #{i}:\nKey: {movie.ratingKey}\n{format_movie(movie)}")
        
        # Include a count if there are more results
        total_count = len(movies)
        if total_count > 5:
            formatted_results.append(f"\n... and {total_count - 5} more results.")
        
        return "\n---\n".join(formatted_results)
    except Exception as e:
        return f"ERROR: Failed to search movies. {str(e)}"

@mcp.tool()
async def get_movie_details(movie_key: str) -> str:
    """Get detailed information about a specific movie.
    
    Args:
        movie_key: The rating key of the movie (can be found in search results)
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Convert movie_key to integer
        key = int(movie_key)
        
        # Find the movie in the library
        movie = None
        sections = await asyncio.to_thread(lambda: plex.library.sections())
        
        # First try to find in movie sections
        for section in sections:
            if section.type == 'movie':
                try:
                    # Try to find by rating key
                    items = await asyncio.to_thread(lambda s=section, k=key: s.search(filters={"ratingKey": k}))
                    if items:
                        movie = items[0]
                        break
                except Exception:
                    # Continue to next section if this fails
                    pass
        
        # If not found, try a direct search
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
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        playlists = await asyncio.to_thread(plex.playlists)
        
        if not playlists:
            return "No playlists found in your Plex server."
        
        formatted_playlists = []
        for i, playlist in enumerate(playlists, 1):
            formatted_playlists.append(f"Playlist #{i}:\nKey: {playlist.ratingKey}\n{format_playlist(playlist)}")
        
        return "\n---\n".join(formatted_playlists)
    except Exception as e:
        return f"ERROR: Failed to fetch playlists. {str(e)}"

@mcp.tool()
async def get_playlist_items(playlist_key: str) -> str:
    """Get the items in a specific playlist.
    
    Args:
        playlist_key: The rating key of the playlist
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Convert playlist_key to integer
        key = int(playlist_key)
        
        # Get all playlists
        all_playlists = await asyncio.to_thread(lambda: plex.playlists())
        
        # Find the one with matching key
        playlist = None
        for p in all_playlists:
            if p.ratingKey == key:
                playlist = p
                break
        
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
    """Create a new playlist with specified movies.
    
    Args:
        name: Name for the new playlist
        movie_keys: Comma-separated list of movie rating keys to add
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Split and clean the movie keys
        movie_key_list = [int(key.strip()) for key in movie_keys.split(",")]
        
        # Get all movie sections
        sections = await asyncio.to_thread(lambda: plex.library.sections())
        movie_sections = [section for section in sections if section.type == 'movie']
        
        if not movie_sections:
            return "ERROR: No movie libraries found in your Plex server."
        
        # Fetch all the movie objects
        movies = []
        for key in movie_key_list:
            movie = None
            # Search in each movie section
            for section in movie_sections:
                try:
                    items = await asyncio.to_thread(lambda s=section, k=key: s.search(filters={"ratingKey": k}))
                    if items:
                        movie = items[0]
                        break
                except Exception:
                    # Continue to next section if this fails
                    pass
                    
            # If not found in sections, try searching all movies
            if not movie:
                all_movies = await asyncio.to_thread(lambda: plex.library.search(libtype="movie"))
                for m in all_movies:
                    if m.ratingKey == key:
                        movie = m
                        break
            
            if movie:
                movies.append(movie)
            else:
                return f"ERROR: Movie with key {key} not found."
        
        if not movies:
            return "ERROR: No valid movies provided for the playlist."
        
        # Create the playlist
        playlist = await asyncio.to_thread(lambda: plex.createPlaylist(name, items=movies))
        
        return f"Successfully created playlist '{name}' with {len(movies)} movie(s).\nPlaylist Key: {playlist.ratingKey}"
    except Exception as e:
        return f"ERROR: Failed to create playlist. {str(e)}"

@mcp.tool()
async def delete_playlist(playlist_key: str) -> str:
    """Delete a playlist from your Plex server.
    
    Args:
        playlist_key: The rating key of the playlist to delete
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Convert playlist_key to integer
        key = int(playlist_key)
        
        # Get all playlists
        all_playlists = await asyncio.to_thread(lambda: plex.playlists())
        
        # Find the one with matching key
        playlist = None
        for p in all_playlists:
            if p.ratingKey == key:
                playlist = p
                break
        
        if not playlist:
            return f"No playlist found with key {playlist_key}."
        
        # Delete the playlist
        await asyncio.to_thread(playlist.delete)
        
        return f"Successfully deleted playlist '{playlist.title}' with key {playlist_key}."
    except NotFound:
        return f"ERROR: Playlist with key {playlist_key} not found."
    except Exception as e:
        return f"ERROR: Failed to delete playlist. {str(e)}"

@mcp.tool()
async def add_to_playlist(playlist_key: str, movie_key: str) -> str:
    """Add a movie to an existing playlist.
    
    Args:
        playlist_key: The rating key of the playlist
        movie_key: The rating key of the movie to add
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Convert keys to integers
        p_key = int(playlist_key)
        m_key = int(movie_key)
        
        # Get all playlists
        all_playlists = await asyncio.to_thread(lambda: plex.playlists())
        
        # Find the playlist with matching key
        playlist = None
        for p in all_playlists:
            if p.ratingKey == p_key:
                playlist = p
                break
                
        if not playlist:
            return f"No playlist found with key {playlist_key}."
            
        # Get all movie sections
        sections = await asyncio.to_thread(lambda: plex.library.sections())
        movie_sections = [section for section in sections if section.type == 'movie']
        
        # Find the movie with matching key
        movie = None
        for section in movie_sections:
            try:
                items = await asyncio.to_thread(lambda s=section, k=m_key: s.search(filters={"ratingKey": k}))
                if items:
                    movie = items[0]
                    break
            except Exception:
                # Continue to next section if this fails
                pass
                
        # If not found in sections, try searching all movies
        if not movie:
            all_movies = await asyncio.to_thread(lambda: plex.library.search(libtype="movie"))
            for m in all_movies:
                if m.ratingKey == m_key:
                    movie = m
                    break
        
        if not movie:
            return f"No movie found with key {movie_key}."
        
        # Add the movie to the playlist
        await asyncio.to_thread(lambda p=playlist, m=movie: p.addItems([m]))
        
        return f"Successfully added '{movie.title}' to playlist '{playlist.title}'."
    except NotFound as e:
        return f"ERROR: Item not found. {str(e)}"
    except Exception as e:
        return f"ERROR: Failed to add movie to playlist. {str(e)}"

@mcp.tool()
async def recent_movies(count: int = 5) -> str:
    """Get recently added movies from your Plex library.
    
    Args:
        count: Number of recent movies to show (default: 5)
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Get all movie libraries
        movie_sections = [section for section in plex.library.sections() if section.type == 'movie']
        
        if not movie_sections:
            return "No movie libraries found in your Plex server."
        
        # Get recently added movies from all movie libraries
        all_recent = []
        for section in movie_sections:
            recent = await asyncio.to_thread(section.recentlyAdded, maxresults=count)
            all_recent.extend(recent)
        
        # Sort by 'addedAt' and get the most recent ones
        all_recent.sort(key=lambda x: x.addedAt, reverse=True)
        recent_movies = all_recent[:count]
        
        if not recent_movies:
            return "No recent movies found in your Plex library."
        
        formatted_movies = []
        for i, movie in enumerate(recent_movies, 1):
            formatted_movies.append(f"Recent Movie #{i}:\nKey: {movie.ratingKey}\nAdded: {movie.addedAt.strftime('%Y-%m-%d')}\n{format_movie(movie)}")
        
        return "\n---\n".join(formatted_movies)
    except Exception as e:
        return f"ERROR: Failed to fetch recent movies. {str(e)}"

@mcp.tool()
async def get_movie_genres(movie_key: str) -> str:
    """Get genres for a specific movie.
    
    Args:
        movie_key: The rating key of the movie
    """
    if not initialize_plex():
        return "ERROR: Could not connect to Plex server. Please check your PLEX_TOKEN and PLEX_SERVER_URL."
    
    try:
        # Convert movie_key to integer
        key = int(movie_key)
        
        # Get all movie sections
        sections = await asyncio.to_thread(lambda: plex.library.sections())
        movie_sections = [section for section in sections if section.type == 'movie']
        
        # Find the movie with matching key
        movie = None
        for section in movie_sections:
            try:
                items = await asyncio.to_thread(lambda s=section, k=key: s.search(filters={"ratingKey": k}))
                if items:
                    movie = items[0]
                    break
            except Exception:
                # Continue to next section if this fails
                pass
                
        # If not found in sections, try searching all movies
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
    # Initialize and run the server
    mcp.run(transport='stdio')
