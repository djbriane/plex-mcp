import asyncio
import pytest
from unittest.mock import MagicMock

# Assume your code is in a module called `plex_mcp`
from plex_mcp import (
    search_movies,
    get_movie_details,
    get_plex_server,
)

# --- Fixture to Set Dummy Environment Variables ---
@pytest.fixture(autouse=True)
def set_dummy_env(monkeypatch):
    monkeypatch.setenv("PLEX_SERVER_URL", "http://dummy")
    monkeypatch.setenv("PLEX_TOKEN", "dummy")

# --- Dummy Classes to Simulate Plex Objects ---

class DummyMovie:
    def __init__(self, ratingKey, title, year=2022, summary="A test movie", duration=7200000, rating="PG", studio="Test Studio"):
        self.ratingKey = ratingKey
        self.title = title
        self.year = year
        self.summary = summary
        self.duration = duration
        self.rating = rating
        self.studio = studio
        # For simplicity, empty lists for directors/roles.
        self.directors = []
        self.roles = []

class DummySection:
    def __init__(self, section_type, title="Movies"):
        self.type = section_type
        self.title = title

    def search(self, filters):
        # By default, if ratingKey equals 1, return a dummy movie.
        # (This will be overridden in tests simulating "not found".)
        if filters.get("ratingKey") == 1:
            return [DummyMovie(1, "Test Movie")]
        return []

class DummyLibrary:
    def __init__(self, movies=None):
        self._movies = movies if movies is not None else []
    
    def search(self, **kwargs):
        # When a search is performed on the library and libtype is "movie",
        # return the stored movies.
        if kwargs.get("libtype") == "movie":
            return self._movies
        return []
    
    def sections(self):
        # Return a list with one dummy section (simulate a movie section).
        return [DummySection("movie")]

class DummyPlexServer:
    def __init__(self, movies=None):
        # Accept an optional list of movies for testing.
        self.library = DummyLibrary(movies)
    
    def playlists(self):
        # For testing, return an empty list.
        return []

# Asynchronous dummy_get_plex_server function.
async def dummy_get_plex_server(movies=None) -> DummyPlexServer:
    return DummyPlexServer(movies)

# --- Fixture to Patch get_plex_server for Tests ---
@pytest.fixture
def patch_get_plex_server(monkeypatch):
    def _patch(movies=None):
        monkeypatch.setattr(
            "plex_mcp.get_plex_server",
            lambda: asyncio.sleep(0, result=DummyPlexServer(movies))
        )
    return _patch

# --- Tests for search_movies (for context) ---

@pytest.mark.asyncio
async def test_search_movies_found(patch_get_plex_server):
    patch_get_plex_server([DummyMovie(1, "Test Movie")])
    query = "Test"
    result = await search_movies(query)
    assert "Test Movie" in result
    assert "more results" not in result

@pytest.mark.asyncio
async def test_search_movies_multiple_results(patch_get_plex_server):
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 8)]
    patch_get_plex_server(movies)
    query = "Test"
    result = await search_movies(query)
    for i in range(1, 6):
        assert f"Test Movie {i}" in result
    assert "and 2 more results" in result

@pytest.mark.asyncio
async def test_search_movies_not_found(patch_get_plex_server, monkeypatch):
    # Provide an empty list of movies.
    patch_get_plex_server([])
    # Override DummySection.search to always return an empty list, simulating not found.
    monkeypatch.setattr(DummySection, "search", lambda self, filters: [])
    result = await search_movies("NonExisting")
    assert "No movies found" in result

@pytest.mark.asyncio
async def test_search_movies_exception(monkeypatch):
    dummy_server = DummyPlexServer([DummyMovie(1, "Test Movie")])
    dummy_server.library.search = MagicMock(side_effect=Exception("Search error"))
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=dummy_server))
    result = await search_movies("Test")
    assert "ERROR: Failed to search movies" in result
    assert "Search error" in result

# --- Expanded Tests for get_movie_details ---

@pytest.mark.asyncio
async def test_get_movie_details_valid(patch_get_plex_server):
    """
    Test that get_movie_details returns a formatted movie string when a movie is found.
    """
    patch_get_plex_server([DummyMovie(1, "Test Movie")])
    result = await get_movie_details("1")
    assert "Test Movie" in result
    assert "2022" in result

@pytest.mark.asyncio
async def test_get_movie_details_invalid_key(patch_get_plex_server):
    """
    Test that get_movie_details returns an error when the movie key is not numeric.
    """
    patch_get_plex_server([DummyMovie(1, "Test Movie")])
    result = await get_movie_details("invalid")
    assert "ERROR" in result

@pytest.mark.asyncio
async def test_get_movie_details_not_found(patch_get_plex_server, monkeypatch):
    """
    Test that get_movie_details returns a 'not found' message when no movie matches the key.
    """
    # Patch the dummy server with an empty list.
    patch_get_plex_server([])
    # Override DummySection.search so that no section finds the movie.
    monkeypatch.setattr(DummySection, "search", lambda self, filters: [])
    result = await get_movie_details("1")
    assert "No movie found with key 1" in result

@pytest.mark.asyncio
async def test_get_movie_details_exception(monkeypatch):
    """
    Test that get_movie_details returns an error message when an exception occurs during search.
    """
    # Create a dummy plex server and simulate an exception during the section search.
    dummy_server = DummyPlexServer([DummyMovie(1, "Test Movie")])
    # Override library.sections() to raise an exception.
    monkeypatch.setattr(dummy_server.library, "sections", lambda: (_ for _ in ()).throw(Exception("Section search failed")))
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=dummy_server))
    
    result = await get_movie_details("1")
    assert "ERROR: Failed to fetch movie details" in result
    assert "Section search failed" in result