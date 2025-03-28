import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-key-please-change-in-production"

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or f'sqlite:///{os.path.join(basedir, "instance", "app.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = (
        os.environ.get("SPOTIFY_REDIRECT_URI") or "http://localhost:5000/callback"
    )
    SPOTIFY_API_SCOPES = os.environ.get("SPOTIFY_API_SCOPES")

    USER_DB_PATH = os.environ.get("USER_DB_PATH") or os.path.join(
        basedir, "instance", "user_data"
    )

    # Track features CSV configuration
    TRACK_FEATURES_CSV_PATH = (
        os.environ.get("TRACK_FEATURES_CSV_PATH") or "data/tracks_features.csv"
    )
    # Use CSV for audio features instead of Spotify API
    USE_CSV_FOR_AUDIO_FEATURES = os.environ.get(
        "USE_CSV_FOR_AUDIO_FEATURES", "True"
    ).lower() in ("true", "yes", "1")

    CACHE_TYPE = "simple"
    CACHE_DEFAULT_TIMEOUT = 300
