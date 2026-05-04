import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load the .env file from the root directory
load_dotenv()

# Setup Spotify with credentials from .env
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
    redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
    scope="user-read-currently-playing user-top-read"
))


def get_current_track():
    """Retrieves the name, artist, and album of the song currently playing. Use ONLY for music queries."""
    track = sp.current_user_playing_track()
    if track and track['is_playing']:
        item = track['item']
        return {
            "song": item['name'],
            "artist": item['artists'][0]['name'],
            "album": item['album']['name'],
            
        }
    return "Sir, no music is currently detected."

def get_user_top_artists(limit: int = 5):
    """
    Fetches the user's most listened to music artists from Spotify. 
    Use this strictly to answer questions regarding the user's music taste, favorite bands, or listening history.
    """
    try:
        results = sp.current_user_top_artists(limit=5, time_range='short_term')
        if not results['items']:
            return "Tell the user they don't have enough listening history yet."
        artist_names = [artist['name'] for artist in results['items']]
        formatted_names = ", ".join(artist_names)
        return f"DATA: {formatted_names}. COMMAND: You MUST read these exact artist names to the user in your response."
        
    except Exception as e:
        return f"Error: {str(e)}"