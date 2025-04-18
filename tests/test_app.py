import asyncio
import pytest
from unittest.mock import MagicMock
from datetime import datetime

# Module: Tests for plex_mcp module
# This file contains tests for the plex_mcp module functions, including edge cases,
# large datasets, and error handling.

# --- Import the Module Under Test ---
from plex_mcp.plex_mcp import (
    MovieSearchParams,
    search_movies,
    get_movie_details,
    list_playlists,
    get_playlist_items,
    create_playlist,
    delete_playlist,
    add_to_playlist,
    recent_movies,
    get_movie_genres,
)

# --- Set Dummy Environment Variables ---
@pytest.fixture(autouse=True)
def set_dummy_env(monkeypatch):
    monkeypatch.setenv("PLEX_SERVER_URL", "http://dummy")
    monkeypatch.setenv("PLEX_TOKEN", "dummy")

# --- Dummy Classes to Simulate Plex Objects ---

class DummyTag:
    def __init__(self, tag):
        self.tag = tag


class DummyMovie:
    def __init__(
        self,
        rating_key,
        title,
        year=2022,
        duration=120 * 60_000,  # in ms
        studio="Test Studio",
        summary="A test summary",
        rating="PG",
        directors=None,
        roles=None,
        genres=None,
        type_="movie",
        addedAt=None,  # New parameter
    ):
        self.ratingKey = rating_key
        self.title = title
        self.year = year
        self.duration = duration
        self.studio = studio
        self.summary = summary
        self.rating = rating
        self.directors = [DummyTag(d) for d in (directors or [])]
        self.roles = [DummyTag(r) for r in (roles or [])]
        self.genres = [DummyTag(g) for g in (genres or [])]
        self.type = type_
        self.addedAt = addedAt  # New attribute

# Subclass for movies with genres.
class DummyMovieWithGenres(DummyMovie):
    def __init__(self, ratingKey, title, genres, **kwargs):
        super().__init__(ratingKey, title, **kwargs)
        self.genres = genres

class DummyGenre:
    def __init__(self, tag):
        self.tag = tag

class DummySection:
    def __init__(self, section_type, title="Movies"):
        self.type = section_type
        self.title = title

    def search(self, filters):
        # By default, if ratingKey equals 1, return a DummyMovie.
        if filters.get("ratingKey") == 1:
            return [DummyMovie(1, "Test Movie")]
        return []

    def recentlyAdded(self, maxresults):
        return []

class DummyLibrary:
    def __init__(self, movies=None):
        self._movies = movies if movies is not None else []

    def search(self, **kwargs):
        title = kwargs.get("title")
        if isinstance(title, MovieSearchParams):
            title = title.title  # Unwrap if passed improperly
        if kwargs.get("libtype") == "movie":
            return [m for m in self._movies if title is None or title.lower() in m.title.lower()]
        return []

    def sections(self):
        return [DummySection("movie")]

class DummyPlaylist:
    def __init__(self, ratingKey, title, items):
        self.ratingKey = ratingKey
        self.title = title
        self._items = items  # list of movies
        self.updatedAt = datetime(2022, 1, 1, 12, 0, 0)

    def items(self):
        return self._items

    def delete(self):
        pass

    def addItems(self, items):
        self._items.extend(items)

class DummyPlexServer:
    def __init__(self, movies=None, playlists=None):
        self.library = DummyLibrary(movies)
        self._playlists = playlists if playlists is not None else []

    def playlists(self):
        return self._playlists

    def createPlaylist(self, name, items):
        new_playlist = DummyPlaylist(1, name, items)
        self._playlists.append(new_playlist)
        return new_playlist

# Asynchronous dummy_get_plex_server function.
async def dummy_get_plex_server(movies=None, playlists=None):
    await asyncio.sleep(0)
    return DummyPlexServer(movies, playlists)

# --- Fixtures ---

@pytest.fixture
def patch_get_plex_server(monkeypatch):
    """Fixture to patch the get_plex_server function with a dummy Plex server."""
    def _patch(movies=None, playlists=None):
        monkeypatch.setattr(
            "plex_mcp.plex_mcp.get_plex_server",
            lambda: dummy_get_plex_server(movies, playlists)
        )
    return _patch

@pytest.fixture
def dummy_movie():
    return DummyMovie(
        rating_key=1,
        title="Test Movie",
        year=2022,
        directors=["Jane Doe"],
        roles=["Test Actor"],
        genres=["Thriller"]
    )

# --- Tests for search_movies ---

@pytest.mark.asyncio
async def test_search_movies_found(patch_get_plex_server, dummy_movie):
    """Test that search_movies returns a formatted result when a movie is found."""
    patch_get_plex_server([dummy_movie])
    result = await search_movies(MovieSearchParams(title="Test"))
    assert "Test Movie" in result
    assert "more results" not in result

@pytest.mark.asyncio
async def test_search_movies_multiple_results(patch_get_plex_server):
    """Test that search_movies shows an extra results message when more than 5 movies are found."""
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 8)]
    patch_get_plex_server(movies)
    result = await search_movies(MovieSearchParams(title="Test"))
    for i in range(1, 6):
        assert f"Test Movie {i}" in result
    assert "and 2 more results" in result

@pytest.mark.asyncio
async def test_search_movies_not_found(monkeypatch, patch_get_plex_server):
    """Test that search_movies returns a 'not found' message when no movies match the query."""
    patch_get_plex_server([])
    monkeypatch.setattr(DummySection, "search", lambda self, filters: [])
    result = await search_movies(MovieSearchParams(title="NonExisting"))
    assert "No movies found" in result

@pytest.mark.asyncio
async def test_search_movies_exception(monkeypatch):
    """Test that search_movies returns an error message when an exception occurs."""
    # Mock the Plex library to raise an exception during search
    dummy_server = DummyPlexServer([DummyMovie(1, "Test Movie")])
    dummy_server.library.search = MagicMock(side_effect=Exception("Search error"))

    # Patch get_plex_server to return the dummy server
    async def mock_get_plex_server():
        return dummy_server

    monkeypatch.setattr("plex_mcp.plex_mcp.get_plex_server", mock_get_plex_server)

    # Call the function under test
    result = await search_movies(MovieSearchParams(title="Test"))

    # Assert the error message is returned
    assert "ERROR: Could not search Plex" in result
    assert "Search error" in result

@pytest.mark.asyncio
async def test_search_movies_empty_string(patch_get_plex_server):
    """Test search_movies with an empty string returns the not-found message."""
    patch_get_plex_server([])
    result = await search_movies(MovieSearchParams(title=""))
    assert result.startswith("No movies found")

@pytest.mark.asyncio
async def test_search_movies_none_input(patch_get_plex_server, dummy_movie):
    """Test that search_movies with None input returns results (treated as unfiltered search)."""
    patch_get_plex_server([dummy_movie])
    result = await search_movies(None)
    assert "Test Movie" in result

@pytest.mark.asyncio
async def test_search_movies_large_dataset(patch_get_plex_server):
    """Test that search_movies correctly handles a large dataset of movies."""
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 201)]
    patch_get_plex_server(movies)
    result = await search_movies(MovieSearchParams(title="Test"))
    for i in range(1, 6):
        assert f"Test Movie {i}" in result
    assert "and 195 more results" in result

@pytest.mark.asyncio
async def test_search_movies_with_default_limit(patch_get_plex_server):
    """Test that search_movies respects the default limit of 5 results."""
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 11)]
    patch_get_plex_server(movies)

    result = await search_movies(MovieSearchParams(title="Test"))
    assert "Result #1" in result
    assert "Result #5" in result
    assert "... and 5 more results." in result
    assert "Result #6" not in result  # Ensure only 5 results are shown

@pytest.mark.asyncio
async def test_search_movies_with_custom_limit(patch_get_plex_server):
    """Test that search_movies respects a custom limit parameter."""
    # Mock the Plex library search to return 10 dummy movies
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 11)]
    patch_get_plex_server(movies)

    result = await search_movies(MovieSearchParams(title="Test"), limit=8)
    assert "Result #1" in result
    assert "Result #8" in result
    assert "... and 2 more results." in result
    assert "Result #9" not in result  # Ensure only 8 results are shown

@pytest.mark.asyncio
async def test_search_movies_with_limit_exceeding_results(patch_get_plex_server):
    """Test that search_movies handles a limit larger than the number of results."""
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 4)]
    patch_get_plex_server(movies)

    result = await search_movies(MovieSearchParams(title="Test"), limit=10)
    assert "Result #1" in result
    assert "Result #3" in result
    assert "... and" not in result  # Ensure no "and more results" message is shown
    assert "Result #4" not in result  # Ensure no extra results are shown

@pytest.mark.asyncio
async def test_search_movies_with_invalid_limit(patch_get_plex_server):
    """Test that search_movies handles an invalid limit (e.g., 0 or negative)."""
    # Mock the Plex library search to return 10 dummy movies
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 11)]
    patch_get_plex_server(movies)

    result = await search_movies(MovieSearchParams(title="Test"), limit=0)
    assert "Result #1" in result
    assert "Result #5" in result
    assert "... and 5 more results." in result
    assert "Result #6" not in result  # Ensure only 5 results are shown (default behavior)

@pytest.mark.asyncio
async def test_search_movies_no_results(patch_get_plex_server):
    """Test that search_movies returns an appropriate message when no results are found."""
    patch_get_plex_server([])

    result = await search_movies(MovieSearchParams(title="Nonexistent"))
    assert "No movies found" in result

# --- Tests for get_movie_details ---

@pytest.mark.asyncio
async def test_get_movie_details_valid(patch_get_plex_server, dummy_movie):
    """Test that get_movie_details returns a formatted movie string when a movie is found."""
    patch_get_plex_server([dummy_movie])
    result = await get_movie_details("1")
    assert "Test Movie" in result
    assert "2022" in result

@pytest.mark.asyncio
async def test_get_movie_details_invalid_key(patch_get_plex_server, dummy_movie):
    """Test that get_movie_details returns an error for a non-numeric movie key."""
    patch_get_plex_server([dummy_movie])
    result = await get_movie_details("invalid")
    assert "ERROR" in result

@pytest.mark.asyncio
async def test_get_movie_details_not_found(patch_get_plex_server):
    """Test that get_movie_details returns a 'not found' message when the movie is missing."""
    patch_get_plex_server([])

    result = await get_movie_details("1")
    assert "No movie found with key 1" in result

# --- Tests for list_playlists ---

@pytest.mark.asyncio
async def test_list_playlists_empty(patch_get_plex_server):
    """Test that list_playlists returns a message when there are no playlists."""
    patch_get_plex_server(playlists=[])

    result = await list_playlists()
    assert "No playlists found" in result

@pytest.mark.asyncio
async def test_list_playlists_found(patch_get_plex_server, dummy_movie):
    """Test that list_playlists returns a formatted list when playlists exist."""
    dummy_playlist = DummyPlaylist(1, "My Playlist", [dummy_movie])
    patch_get_plex_server(playlists=[dummy_playlist])

    result = await list_playlists()
    assert "My Playlist" in result
    assert "Playlist #1" in result

# --- Tests for get_playlist_items ---

@pytest.mark.asyncio
async def test_get_playlist_items_found(patch_get_plex_server, dummy_movie):
    """Test that get_playlist_items returns the items of a found playlist."""
    dummy_playlist = DummyPlaylist(2, "My Playlist", [dummy_movie])
    patch_get_plex_server(playlists=[dummy_playlist])

    result = await get_playlist_items("2")
    assert "Test Movie" in result

@pytest.mark.asyncio
async def test_get_playlist_items_not_found(patch_get_plex_server):
    """Test that get_playlist_items returns an error when the playlist is not found."""
    patch_get_plex_server(playlists=[])

    result = await get_playlist_items("99")
    assert "No playlist found with key 99" in result

# --- Tests for create_playlist ---

@pytest.mark.asyncio
async def test_create_playlist_success(patch_get_plex_server, dummy_movie):
    """Test that create_playlist returns a success message on valid input."""
    patch_get_plex_server([dummy_movie])

    result = await create_playlist("My Playlist", "1")
    assert "Successfully created playlist 'My Playlist'" in result

@pytest.mark.asyncio
async def test_create_playlist_no_valid_movies(patch_get_plex_server):
    """Test that create_playlist returns an error when no valid movies are provided."""
    patch_get_plex_server([])

    result = await create_playlist("My Playlist", "1,2")
    assert "ERROR:" in result

# --- Tests for delete_playlist ---

@pytest.mark.asyncio
async def test_delete_playlist_success(patch_get_plex_server, dummy_movie):
    """Test that delete_playlist returns a success message when deletion is successful."""
    dummy_playlist = DummyPlaylist(3, "Delete Me", [dummy_movie])
    patch_get_plex_server(playlists=[dummy_playlist])

    result = await delete_playlist("3")
    assert "Successfully deleted playlist" in result

@pytest.mark.asyncio
async def test_delete_playlist_not_found(patch_get_plex_server):
    """Test that delete_playlist returns an error when no matching playlist is found."""
    patch_get_plex_server(playlists=[])

    result = await delete_playlist("99")
    assert "No playlist found with key 99" in result

# --- Tests for add_to_playlist ---

@pytest.mark.asyncio
async def test_add_to_playlist_success(patch_get_plex_server):
    """Test that add_to_playlist returns a success message when a movie is added."""
    dummy_playlist = DummyPlaylist(4, "My Playlist", [])
    dummy_movie = DummyMovie(5, "Added Movie")
    patch_get_plex_server([dummy_movie], playlists=[dummy_playlist])

    result = await add_to_playlist("4", "5")
    assert "Successfully added 'Added Movie' to playlist" in result

@pytest.mark.asyncio
async def test_add_to_playlist_playlist_not_found(patch_get_plex_server):
    """Test that add_to_playlist returns an error when the specified playlist is not found."""
    patch_get_plex_server(playlists=[])

    result = await add_to_playlist("999", "5")
    assert "No playlist found with key 999" in result

# --- Tests for recent_movies ---

@pytest.mark.asyncio
async def test_recent_movies_found(patch_get_plex_server):
    """Test that recent_movies returns recent movie information when available."""
    recent_movie = DummyMovie(1, "Recent Movie", addedAt=datetime(2022, 5, 1))
    patch_get_plex_server([recent_movie])

    result = await recent_movies(5)
    assert "Recent Movie" in result

@pytest.mark.asyncio
async def test_recent_movies_not_found(patch_get_plex_server):
    """Test that recent_movies returns an error message when no recent movies are found."""
    patch_get_plex_server([])

    result = await recent_movies(5)
    assert "No recent movies found" in result

# --- Tests for get_movie_genres ---

@pytest.mark.asyncio
async def test_get_movie_genres_found(monkeypatch, patch_get_plex_server):
    """Test that get_movie_genres returns the correct genres for a movie."""
    # Create a dummy movie with genre tags
    movie_with_genres = DummyMovie(
        rating_key=1,
        title="Test Movie",
        genres=["Action", "Thriller"]
    )

    # Patch DummySection.search to return our dummy movie when the ratingKey matches
    monkeypatch.setattr(
        DummySection,
        "search",
        lambda self, filters: [movie_with_genres] if filters.get("ratingKey") == 1 else []
    )

    patch_get_plex_server([movie_with_genres])
    result = await get_movie_genres("1")
    assert "Action" in result
    assert "Thriller" in result

@pytest.mark.asyncio
async def test_get_movie_genres_not_found(monkeypatch, patch_get_plex_server):
    """Test that get_movie_genres returns an error message when no matching movie is found."""
    patch_get_plex_server([])
    monkeypatch.setattr(DummySection, "search", lambda self, filters: [])
    result = await get_movie_genres("1")
    assert "No movie found with key 1" in result