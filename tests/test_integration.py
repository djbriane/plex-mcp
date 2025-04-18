# tests/test_integration.py

import asyncio
import os
import pytest
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root.
load_dotenv()

# Import functions from the main module.
from plex_mcp.plex_mcp import (
    get_plex_server,
    search_movies,
    list_playlists,
)

# Mark these tests as integration tests.
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_integration_get_plex_server():
    """
    Integration test: Verify that we can connect to the real Plex server
    using environment variables defined in the .env file.
    """
    plex = await get_plex_server()
    assert plex is not None

# tests/test_integration.py

import os
import asyncio
import pytest
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from plex_mcp import search_movies

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_integration_search_movies_title():
    """
    Search by title keyword.
    """
    result = await search_movies("Avengers")
    assert isinstance(result, str)
    assert ("Result #" in result) or ("No movies found" in result)

@pytest.mark.asyncio
async def test_integration_search_movies_by_year():
    """
    Search by release year.
    """
    # find all movies from 1999
    result = await search_movies(year=1999)
    assert isinstance(result, str)
    assert ("Result #" in result) or ("No movies found" in result)

@pytest.mark.asyncio
async def test_integration_search_movies_by_director():
    """
    Search by director name.
    """
    result = await search_movies(director="Christopher Nolan")
    assert isinstance(result, str)
    assert ("Result #" in result) or ("No movies found" in result)

@pytest.mark.asyncio
async def test_integration_search_movies_unwatched():
    """
    Search for only unwatched movies.
    """
    result = await search_movies(watched=False)
    assert isinstance(result, str)
    assert ("Result #" in result) or ("No movies found" in result)

@pytest.mark.asyncio
async def test_integration_search_movies_min_duration():
    """
    Search for movies at least 120 minutes long.
    """
    result = await search_movies(min_duration=120)
    assert isinstance(result, str)
    assert ("Result #" in result) or ("No movies found" in result)

@pytest.mark.asyncio
async def test_integration_search_movies_multiple_filters():
    """
    Search combining year, genre, and minimum duration.
    """
    result = await search_movies(year=2020, genre="Drama", min_duration=100)
    assert isinstance(result, str)
    assert ("Result #" in result) or ("No movies found" in result)

@pytest.mark.asyncio
async def test_integration_list_playlists():
    """
    Integration test: List the playlists on the real Plex server.
    Assert that the result is a string (may be an empty list message or a formatted list).
    """
    result = await list_playlists()
    assert isinstance(result, str)