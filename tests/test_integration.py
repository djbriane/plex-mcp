# tests/test_integration.py

import asyncio
import os
import pytest
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root.
load_dotenv()

# Import functions from the main module.
from plex_mcp import (
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

@pytest.mark.asyncio
async def test_integration_search_movies():
    """
    Integration test: Search for movies on the real Plex server.
    This test uses a sample query and asserts that the result is a non-empty string.
    Adjust the query as needed to match expected results.
    """
    result = await search_movies("Avengers")
    # Expect a response that either contains movies matching the search or a 'no movies found' message.
    assert isinstance(result, str)
    assert ("Avengers" in result) or ("No movies found" in result)

@pytest.mark.asyncio
async def test_integration_list_playlists():
    """
    Integration test: List the playlists on the real Plex server.
    Assert that the result is a string (may be an empty list message or a formatted list).
    """
    result = await list_playlists()
    assert isinstance(result, str)