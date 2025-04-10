import asyncio
import pytest
from unittest.mock import MagicMock

# Assume your code is in a module called `plex_mcp`
from plex_mcp import (
    search_movies,
    get_movie_details,
    get_plex_server,
)

# Dummy classes to simulate Plex objects

class DummyMovie:
    def __init__(self, ratingKey, title, year=2022, summary="A test movie", duration=7200000, rating="PG", studio="Test Studio"):
        self.ratingKey = ratingKey
        self.title = title
        self.year = year
        self.summary = summary
        self.duration = duration
        self.rating = rating
        self.studio = studio
        # For simplicity, empty lists for directors/roles
        self.directors = []
        self.roles = []

class DummySection:
    def __init__(self, section_type, title="Movies"):
        self.type = section_type
        self.title = title

    def search(self, filters):
        # Return a dummy movie if the ratingKey matches 1, otherwise empty list.
        if filters.get("ratingKey") == 1:
            return [DummyMovie(1, "Test Movie")]
        return []

class DummyLibrary:
    def __init__(self, movies=None):
        self._movies = movies if movies is not None else []
    
    def search(self, **kwargs):
        # When a search is performed on the library and libtype is movie, return our list.
        if kwargs.get("libtype") == "movie":
            return self._movies
        return []
    
    def sections(self):
        # Return a list of one dummy section simulating a movie section.
        return [DummySection("movie")]

class DummyPlexServer:
    def __init__(self, movies=None):
        # Accept an optional list of movies for testing.
        self.library = DummyLibrary(movies)
    
    def playlists(self):
        # For testing, return an empty list.
        return []

# Create an asynchronous dummy_get_plex_server function.
async def dummy_get_plex_server(movies=None) -> DummyPlexServer:
    return DummyPlexServer(movies)

# Fixture to patch get_plex_server for tests
@pytest.fixture
def patch_get_plex_server(monkeypatch):
    def _patch(movies=None):
        monkeypatch.setattr(
            "plex_mcp.get_plex_server",
            lambda: asyncio.sleep(0, result=DummyPlexServer(movies))
        )
    return _patch

#
# Tests for search_movies
#

@pytest.mark.asyncio
async def test_search_movies_found(patch_get_plex_server):
    """
    Test that search_movies returns a formatted result when a movie is found.
    """
    # Provide one movie in the dummy server.
    patch_get_plex_server([DummyMovie(1, "Test Movie")])
    query = "Test"
    result = await search_movies(query)
    # Check that the result includes the dummy movie title.
    assert "Test Movie" in result
    # When exactly one result is present, there should be no "more results" message.
    assert "more results" not in result

@pytest.mark.asyncio
async def test_search_movies_multiple_results(patch_get_plex_server):
    """
    Test that search_movies shows an extra results message when more than 5 movies are found.
    """
    # Create a list of 7 dummy movies.
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 8)]
    patch_get_plex_server(movies)
    query = "Test"
    result = await search_movies(query)
    # Verify that the first 5 movies are listed.
    for i in range(1, 6):
        assert f"Test Movie {i}" in result
    # Verify that the extra results message indicates the remaining 2 movies.
    assert "and 2 more results" in result

@pytest.mark.asyncio
async def test_search_movies_not_found(patch_get_plex_server):
    """
    Test that search_movies returns an appropriate message when no movies are found.
    """
    # Provide an empty list of movies.
    patch_get_plex_server([])
    result = await search_movies("NonExisting")
    assert "No movies found" in result

@pytest.mark.asyncio
async def test_search_movies_exception(monkeypatch):
    """
    Test that if library.search raises an exception, search_movies returns an error message.
    """
    # Create a dummy plex server where library.search raises an error.
    dummy_server = DummyPlexServer([DummyMovie(1, "Test Movie")])
    dummy_server.library.search = MagicMock(side_effect=Exception("Search error"))
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=dummy_server))
    
    result = await search_movies("Test")
    # Verify that the error message is returned and includes the exception message.
    assert "ERROR: Failed to search movies" in result
    assert "Search error" in result

#
# Tests for get_movie_details
#

@pytest.mark.asyncio
async def test_get_movie_details_valid(patch_get_plex_server):
    """
    Test that get_movie_details returns a formatted movie string when a movie is found.
    """
    patch_get_plex_server([DummyMovie(1, "Test Movie")])
    result = await get_movie_details("1")
    # Check for expected information in the formatted movie string.
    assert "Test Movie" in result
    assert "2022" in result

@pytest.mark.asyncio
async def test_get_movie_details_invalid_key(patch_get_plex_server):
    """
    Test that get_movie_details returns an error message when the key is invalid.
    """
    patch_get_plex_server([DummyMovie(1, "Test Movie")])
    result = await get_movie_details("invalid")
    assert "ERROR" in result