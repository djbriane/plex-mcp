import asyncio
import pytest
from unittest.mock import MagicMock
from datetime import datetime

# Assume your code is in a module called `plex_mcp`
from plex_mcp import (
    search_movies,
    get_movie_details,
    list_playlists,
    get_playlist_items,
    create_playlist,
    delete_playlist,
    add_to_playlist,
    recent_movies,
    get_movie_genres,
    get_plex_server,
)

# --- Set Dummy Environment Variables ---
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
        self.directors = []
        self.roles = []
        # Add 'type' attribute required by get_playlist_items
        self.type = "movie"
    @property
    def addedAt(self):
        return getattr(self, "_addedAt", datetime(2022, 1, 1))
    @addedAt.setter
    def addedAt(self, value):
        self._addedAt = value

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
        if kwargs.get("libtype") == "movie":
            return self._movies
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

# Extend DummyPlexServer to support playlists and createPlaylist.
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

# --- Fixture to Patch get_plex_server for Tests ---
@pytest.fixture
def patch_get_plex_server(monkeypatch):
    def _patch(movies=None, playlists=None):
        monkeypatch.setattr(
            "plex_mcp.get_plex_server",
            lambda: asyncio.sleep(0, result=DummyPlexServer(movies, playlists))
        )
    return _patch

@pytest.fixture
def dummy_movie():
    return DummyMovie(1, "Test Movie")

# Test search_movies with a valid query
@pytest.mark.asyncio
async def test_search_movies_found(patch_get_plex_server, dummy_movie):
    patch_get_plex_server([dummy_movie])
    result = await search_movies("Test")
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
async def test_search_movies_not_found(monkeypatch, patch_get_plex_server):
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

# Test search_movies with an empty string
@pytest.mark.asyncio
async def test_search_movies_empty_string(patch_get_plex_server):
    # Patch the plex server with an empty movie list to simulate no results.
    patch_get_plex_server([])
    result = await search_movies("")
    # Expect the function to return the message indicating no movies found.
    assert result == "No movies found matching ''."

# Test search_movies with None as input
@pytest.mark.asyncio
async def test_search_movies_none_input(patch_get_plex_server, dummy_movie):
    patch_get_plex_server([dummy_movie])
    try:
        result = await search_movies(None)
    except Exception as e:
        # If an exception is raised, capture its string representation.
        result = str(e)
    # The expected behavior should be defined by your application;
    # Here we assert that an error indication is present.
    assert "ERROR" in result

# Test search_movies with a large dataset
@pytest.mark.asyncio
async def test_search_movies_large_dataset(patch_get_plex_server):

    # Create a list of 200 dummy movies.
    movies = [DummyMovie(i, f"Test Movie {i}") for i in range(1, 201)]
    patch_get_plex_server(movies)
    result = await search_movies("Test")
    # Expect the first five to be included.
    for i in range(1, 6):
        assert f"Test Movie {i}" in result
    # Check that it mentions the remaining movies (200 - 5 = 195 more).
    assert "and 195 more results" in result

# --- Tests for get_movie_details ---
@pytest.mark.asyncio
async def test_get_movie_details_invalid_key(patch_get_plex_server, dummy_movie):
    patch_get_plex_server([dummy_movie])
    result = await get_movie_details("invalid")
    assert "ERROR" in result

# --- Tests for list_playlists ---
@pytest.mark.asyncio
async def test_list_playlists_empty(monkeypatch):
    class DummyPlexServerNoPlaylists(DummyPlexServer):
        def playlists(self):
            return []
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerNoPlaylists()))
    result = await list_playlists()
    assert "No playlists found" in result

@pytest.mark.asyncio
async def test_list_playlists_found(monkeypatch, dummy_movie):
    dummy_playlist = DummyPlaylist(1, "My Playlist", [dummy_movie])
    class DummyPlexServerWithPlaylists(DummyPlexServer):
        def playlists(self):
            return [dummy_playlist]
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerWithPlaylists()))
    result = await list_playlists()
    assert "My Playlist" in result
    assert "Playlist #1" in result

# --- Tests for get_playlist_items ---
@pytest.mark.asyncio
async def test_get_playlist_items_found(monkeypatch, dummy_movie):
    dummy_playlist = DummyPlaylist(2, "My Playlist", [dummy_movie])
    class DummyPlexServerWithPlaylists(DummyPlexServer):
        def playlists(self):
            return [dummy_playlist]
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerWithPlaylists()))
    result = await get_playlist_items("2")
    # Now, DummyMovie has a 'type' attribute.
    assert "Test Movie" in result

@pytest.mark.asyncio
async def test_get_playlist_items_not_found(monkeypatch):
    class DummyPlexServerNoPlaylists(DummyPlexServer):
        def playlists(self):
            return []
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerNoPlaylists()))
    result = await get_playlist_items("99")
    assert "No playlist found with key 99" in result

# --- Tests for create_playlist ---
@pytest.mark.asyncio
async def test_create_playlist_success(monkeypatch, dummy_movie):
    class DummyPlexServerWithCreate(DummyPlexServer):
        def createPlaylist(self, name, items):
            return DummyPlaylist(1, name, items)
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerWithCreate([dummy_movie])))
    result = await create_playlist("My Playlist", "1")
    assert "Successfully created playlist 'My Playlist'" in result

@pytest.mark.asyncio
async def test_create_playlist_no_valid_movies(monkeypatch):
    class DummyPlexServerWithSearch(DummyPlexServer):
        def createPlaylist(self, name, items):
            return DummyPlaylist(1, name, items)
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerWithSearch([])))
    result = await create_playlist("My Playlist", "1,2")
    assert "ERROR:" in result

# --- Tests for delete_playlist ---
@pytest.mark.asyncio
async def test_delete_playlist_success(monkeypatch, dummy_movie):
    dummy_playlist = DummyPlaylist(3, "Delete Me", [dummy_movie])
    class DummyPlexServerWithPlaylist(DummyPlexServer):
        def playlists(self):
            return [dummy_playlist]
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerWithPlaylist()))
    result = await delete_playlist("3")
    assert "Successfully deleted playlist" in result

@pytest.mark.asyncio
async def test_delete_playlist_not_found(monkeypatch):
    class DummyPlexServerNoPlaylists(DummyPlexServer):
        def playlists(self):
            return []
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerNoPlaylists()))
    result = await delete_playlist("99")
    assert "No playlist found with key 99" in result

# --- Tests for add_to_playlist ---
@pytest.mark.asyncio
async def test_add_to_playlist_success(monkeypatch):
    dummy_playlist = DummyPlaylist(4, "My Playlist", [])
    class DummyPlexServerWithPlaylist(DummyPlexServer):
        def playlists(self):
            return [dummy_playlist]
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerWithPlaylist()))
    # Override DummySection.search so that it returns a dummy movie with key 5.
    monkeypatch.setattr(DummySection, "search", lambda self, filters: [DummyMovie(5, "Added Movie")] if filters.get("ratingKey") == 5 else [])
    result = await add_to_playlist("4", "5")
    assert "Successfully added 'Added Movie' to playlist" in result

@pytest.mark.asyncio
async def test_add_to_playlist_playlist_not_found(monkeypatch):
    class DummyPlexServerNoPlaylist(DummyPlexServer):
        def playlists(self):
            return []
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServerNoPlaylist()))
    result = await add_to_playlist("999", "5")
    assert "No playlist found with key 999" in result

# --- Tests for recent_movies ---
@pytest.mark.asyncio
async def test_recent_movies_found(monkeypatch):
    class DummySectionWithRecent(DummySection):
        def recentlyAdded(self, maxresults):
            m = DummyMovie(1, "Recent Movie")
            m.addedAt = datetime(2022, 5, 1)
            return [m]
    monkeypatch.setattr(DummyLibrary, "sections", lambda self: [DummySectionWithRecent("movie")])
    monkeypatch.setattr("plex_mcp.get_plex_server", lambda: asyncio.sleep(0, result=DummyPlexServer()))
    result = await recent_movies(5)
    assert "Recent Movie" in result

@pytest.mark.asyncio
async def test_recent_movies_not_found(monkeypatch, patch_get_plex_server):
    patch_get_plex_server()
    monkeypatch.setattr(DummySection, "recentlyAdded", lambda self, maxresults: [])
    result = await recent_movies(5)
    assert "No recent movies found" in result

# --- Tests for get_movie_genres ---
@pytest.mark.asyncio
async def test_get_movie_genres_found(monkeypatch, patch_get_plex_server):
    # Define DummyMovieWithGenres if not already defined
    class DummyMovieWithGenres(DummyMovie):
        def __init__(self, ratingKey, title, genres, **kwargs):
            super().__init__(ratingKey, title, **kwargs)
            self.genres = genres
    class DummyGenre:
        def __init__(self, tag):
            self.tag = tag
    # Patch DummySection.search to return a movie with genres.
    monkeypatch.setattr(DummySection, "search", lambda self, filters: [DummyMovieWithGenres(1, "Test Movie", [DummyGenre("Action"), DummyGenre("Thriller")])] if filters.get("ratingKey") == 1 else [])
    patch_get_plex_server([DummyMovieWithGenres(1, "Test Movie", [DummyGenre("Action"), DummyGenre("Thriller")])])
    result = await get_movie_genres("1")
    assert "Action" in result
    assert "Thriller" in result

@pytest.mark.asyncio
async def test_get_movie_genres_not_found(monkeypatch, patch_get_plex_server):
    patch_get_plex_server([])
    monkeypatch.setattr(DummySection, "search", lambda self, filters: [])
    result = await get_movie_genres("1")
    assert "No movie found with key 1" in result