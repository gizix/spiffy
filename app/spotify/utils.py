# app/spotify/utils.py
from flask import current_app
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from app.models import User


def get_spotify_client(user):
    """Get an authenticated Spotify client for a user"""
    if not user.spotify_token or not user.token_expires_at or user.is_token_expired():
        # If token is expired or missing, we need to refresh
        sp_oauth = SpotifyOAuth(
            client_id=current_app.config["SPOTIFY_CLIENT_ID"],
            client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
            redirect_uri=current_app.config["SPOTIFY_REDIRECT_URI"],
            scope=current_app.config["SPOTIFY_API_SCOPES"],
            cache_path=None,
        )

        if user.spotify_refresh_token:
            # Refresh the token
            token_info = sp_oauth.refresh_access_token(user.spotify_refresh_token)
            user.set_spotify_tokens(
                token_info["access_token"],
                token_info.get("refresh_token", user.spotify_refresh_token),
                token_info["expires_in"],
            )
        else:
            # No refresh token, can't proceed
            current_app.logger.error(f"No refresh token for user {user.id}")
            return None

    # Create and return Spotify client with the access token
    return spotipy.Spotify(auth=user.spotify_token)
