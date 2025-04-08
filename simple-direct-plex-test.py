#!/usr/bin/env python3
import os
import sys
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound

def main():
    """Simplest possible direct Plex API test"""
    print("Direct Plex API Test")
    print("===================")
    
    # Check environment variables
    plex_token = os.environ.get("PLEX_TOKEN")
    plex_server_url = os.environ.get("PLEX_SERVER_URL")
    
    if not plex_token or not plex_server_url:
        print("ERROR: Environment variables not set!")
        print(f"PLEX_SERVER_URL: {'Set' if plex_server_url else 'Not set'}")
        print(f"PLEX_TOKEN: {'Set' if plex_token else 'Not set'}")
        print("\nPlease set both PLEX_TOKEN and PLEX_SERVER_URL environment variables.")
        sys.exit(1)
    
    print(f"Environment variables configured:")
    print(f"PLEX_SERVER_URL: {plex_server_url}")
    print(f"PLEX_TOKEN: {'*****' + plex_token[-4:] if plex_token else 'Not set'}")
    print()
    
    try:
        print("Connecting to Plex server...")
        plex = PlexServer(plex_server_url, plex_token)
        
        print(f"✅ SUCCESS: Connected to Plex server '{plex.friendlyName}'")
        print(f"Server version: {plex.version}")
        print()
        
        # Try to get library sections
        print("Retrieving library sections:")
        sections = plex.library.sections()
        
        if sections:
            print(f"Found {len(sections)} library sections:")
            for section in sections:
                print(f"- {section.title} ({section.type}): {len(section.all())} items")
        else:
            print("No library sections found.")
            
        # Try to get recent items
        movie_sections = [section for section in sections if section.type == 'movie']
        if movie_sections:
            section = movie_sections[0]
            print(f"\nRecent items from '{section.title}':")
            items = section.recentlyAdded(maxresults=3)
            
            if items:
                for item in items:
                    print(f"- {item.title} ({getattr(item, 'year', 'Unknown Year')})")
            else:
                print("No recent items found.")
        
    except Unauthorized:
        print("❌ ERROR: Authentication failed. Please check your PLEX_TOKEN.")
    except NotFound:
        print("❌ ERROR: Resource not found. Please check your PLEX_SERVER_URL.")
    except Exception as e:
        print(f"❌ ERROR: An exception occurred: {str(e)}")

if __name__ == "__main__":
    main()