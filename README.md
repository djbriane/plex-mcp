# Plex MCP Server

This is a Python-based MCP server that integrates with the Plex Media Server API to search for movies and manage playlists. It uses the PlexAPI library for seamless interaction with your Plex server.

## Setup

### Prerequisites

- Python 3.8 or higher
- `uv` package manager
- A Plex Media Server with API access

### Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd plex-mcp
   ```

2. Install dependencies with `uv`:
   ```
   uv venv
   source .venv/bin/activate
   uv sync
   ```

3. Configure environment variables for your Plex server:
   - `PLEX_TOKEN`: Your Plex authentication token
   - `PLEX_SERVER_URL`: Your Plex server URL (e.g., http://192.168.1.100:32400)

### Finding Your Plex Token

You can find your Plex token in this way:

   - Sign in to Plex Web App
   - Open Developer Tools
   - In Console tab, paste and run:
     ```javascript
     window.localStorage.getItem('myPlexAccessToken')
     ```

## Usage with Claude

Add the following configuration to your Claude app:

```json
{
    "mcpServers": {
        "plex": {
            "command": "uv",
            "args": [
                "--directory",
                "FULL_PATH_TO_PROJECT/plex-mcp",
                "run",
                "plex-mcp.py"
            ],
            "env": {
                "PLEX_TOKEN": "YOUR_PLEX_TOKEN",
                "PLEX_SERVER_URL": "YOUR_PLEX_SERVER_URL"
            }
        }
    }
}
```

## Available Commands

The Plex MCP server exposes these commands:

| Command | Description | OpenAPI Reference |
|---------|-------------|-------------------|
| `search_movies` | Search for movies in your library by title | `/library/sections/{sectionKey}/search` |
| `get_movie_details` | Get detailed information about a specific movie | `/library/metadata/{ratingKey}` |
| `get_movie_genres` | Get the genres for a specific movie | `/library/sections/{sectionKey}/genre` |
| `list_playlists` | List all playlists on your Plex server | `/playlists` |
| `get_playlist_items` | Get the items in a specific playlist | `/playlists/{playlistID}/items` |
| `create_playlist` | Create a new playlist with specified movies | `/playlists` |
| `delete_playlist` | Delete a playlist from your Plex server | `/playlists/{playlistID}` |
| `add_to_playlist` | Add a movie to an existing playlist | `/playlists/{playlistID}/items` |
| `recent_movies` | Get recently added movies from your library | `/library/recentlyAdded` |

## Testing

The repository includes a test script to verify connectivity and functionality:

- `simple-direct-plex-test.py` - A direct PlexAPI test that doesn't use the MCP server

## Troubleshooting

If you encounter connection issues, try these steps:

1. Verify your environment variables are set correctly:
   ```
   echo $PLEX_SERVER_URL
   echo $PLEX_TOKEN
   ```

2. Test direct connectivity to your Plex server:
   ```
   python simple-direct-plex-test.py
   ```