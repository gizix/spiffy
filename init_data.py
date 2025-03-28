from app import create_app, db
from app.models import SpotifyDataType


def init_spotify_data_types():
    data_types = [
        {
            "name": "top_tracks",
            "description": "Your most listened to tracks",
            "endpoint": "me/top/tracks",
            "required_scope": "user-top-read",
        },
        {
            "name": "top_artists",
            "description": "Your most listened to artists",
            "endpoint": "me/top/artists",
            "required_scope": "user-top-read",
        },
        {
            "name": "saved_tracks",
            "description": "Your saved tracks",
            "endpoint": "me/tracks",
            "required_scope": "user-library-read",
        },
        {
            "name": "playlists",
            "description": "Your playlists",
            "endpoint": "me/playlists",
            "required_scope": "playlist-read-private",
        },
        {
            "name": "recently_played",
            "description": "Your recently played tracks",
            "endpoint": "me/player/recently-played",
            "required_scope": "user-read-recently-played",
        },
        {
            "name": "audio_features",
            "description": "Audio features for your saved tracks. *Limited data, Spotify removed this API*",
            "endpoint": "audio-features",
            "required_scope": "user-library-read",
        },
        {
            "name": "artists",
            "description": "All artists from your saved tracks, playlists, and top tracks",
            "endpoint": "artists",
            "required_scope": "user-library-read",
        },
        # {
        #     "name": "audio_analysis",
        #     "description": "Detailed audio analysis for your saved tracks",
        #     "endpoint": "audio-analysis",
        #     "required_scope": "user-library-read",
        # },
    ]

    for data_type in data_types:
        existing = SpotifyDataType.query.filter_by(name=data_type["name"]).first()
        if not existing:
            dt = SpotifyDataType(**data_type)
            db.session.add(dt)

    db.session.commit()
    print("Spotify data types initialized")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        init_spotify_data_types()
