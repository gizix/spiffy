from flask import (
    redirect,
    url_for,
    request,
    current_app,
    flash,
    jsonify,
    render_template,
    session,
)
from flask_login import current_user, login_required
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import sqlite3
import requests
from app.spotify import bp
from app import db
from app.models import User, SpotifyDataType, UserDataSync


def get_spotify_oauth(user_id=None):
    """
    Get a SpotifyOAuth instance with user-specific cache path
    """
    import os

    # Create cache directory if it doesn't exist
    cache_dir = os.path.join(current_app.root_path, "spotify_caches")
    os.makedirs(cache_dir, exist_ok=True)

    # Create a unique cache path if user_id is provided
    if user_id:
        cache_path = os.path.join(cache_dir, f"user_{user_id}_cache")
    else:
        # For unauthenticated users, use a temporary cache with session ID
        import secrets

        cache_id = session.get("spotify_cache_id")
        if not cache_id:
            cache_id = secrets.token_urlsafe(8)
            session["spotify_cache_id"] = cache_id
        cache_path = os.path.join(cache_dir, f"temp_{cache_id}_cache")

    # Log the cache path being used
    current_app.logger.info(f"Using Spotify cache path: {cache_path}")

    return SpotifyOAuth(
        client_id=current_app.config["SPOTIFY_CLIENT_ID"],
        client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=current_app.config["SPOTIFY_REDIRECT_URI"],
        scope=current_app.config["SPOTIFY_API_SCOPES"],
        cache_path=cache_path,  # Use the user-specific cache path
        requests_timeout=30,
        show_dialog=True,  # Always show dialog to force account selection
    )


def get_spotify_client():
    if not current_user.spotify_token:
        return None

    if current_user.token_expired():
        try:
            # Create a fresh SpotifyOAuth instance just for token refresh
            sp_oauth = SpotifyOAuth(
                client_id=current_app.config["SPOTIFY_CLIENT_ID"],
                client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
                redirect_uri=current_app.config["SPOTIFY_REDIRECT_URI"],
                scope=current_app.config["SPOTIFY_API_SCOPES"],
                cache_path=None,
                show_dialog=True,
            )

            # Use the refresh token to get a new access token
            token_info = sp_oauth.refresh_access_token(
                current_user.spotify_refresh_token
            )

            # Update the user's tokens
            current_user.set_spotify_tokens(
                token_info["access_token"],
                token_info.get("refresh_token", current_user.spotify_refresh_token),
                token_info["expires_in"],
            )
            db.session.commit()

            return spotipy.Spotify(auth=token_info["access_token"])
        except Exception as e:
            current_app.logger.error(f"Token refresh error: {str(e)}")
            flash("Your Spotify session has expired. Please log in again.")
            return None

    return spotipy.Spotify(auth=current_user.spotify_token)


@bp.route("/connect")
@login_required
def connect():
    # Generate a random state value for security
    import secrets

    state = secrets.token_urlsafe(16)

    # Use the unified scopes from config
    sp_oauth = get_spotify_oauth()

    # Log the scopes we're requesting
    current_app.logger.info(
        f"Requesting Spotify authorization with scopes: {current_app.config['SPOTIFY_API_SCOPES']}"
    )

    auth_url = sp_oauth.get_authorize_url(state=state)
    return redirect(auth_url)


@bp.route("/callback")
@login_required
def callback():
    error = request.args.get("error")
    if error:
        flash(f"Authentication error: {error}")
        return redirect(url_for("main.dashboard"))

    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        flash("Authentication failed: No code provided. Please try again.")
        return redirect(url_for("main.dashboard"))

    try:
        # Get the same SpotifyOAuth instance with unified scopes
        sp_oauth = get_spotify_oauth()

        # Exchange the code for tokens
        token_info = sp_oauth.get_access_token(code, as_dict=True)

        # Log the granted scopes if available
        if "scope" in token_info:
            current_app.logger.info(f"Granted scopes: {token_info['scope']}")

        # Save the tokens to the user
        current_user.set_spotify_tokens(
            token_info["access_token"],
            token_info["refresh_token"],
            token_info["expires_in"],
        )

        db.session.commit()

        # Test the connection to ensure everything works
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_info = sp.current_user()

        flash(f'Successfully connected to Spotify as {user_info["display_name"]}!')
    except Exception as e:
        flash(f"Error connecting to Spotify: {str(e)}")
        current_app.logger.error(f"Spotify OAuth error: {str(e)}")

    return redirect(url_for("main.dashboard"))


@bp.route("/disconnect")
@login_required
def disconnect():
    current_user.spotify_token = None
    current_user.spotify_refresh_token = None
    current_user.spotify_token_expiry = None
    current_user.token_expires_at = None  # Make sure we clear this as well if it exists
    db.session.commit()
    flash(
        "Disconnected from Spotify. Please reconnect to grant all necessary permissions."
    )
    return redirect(url_for("main.dashboard"))


@bp.route("/sync/<data_type>")
@login_required
def sync_data(data_type):
    data_type_obj = SpotifyDataType.query.filter_by(name=data_type).first_or_404()

    sp = get_spotify_client()
    if not sp:
        flash("Spotify connection required. Please connect your account.")
        return redirect(url_for("spotify.connect"))

    try:
        record_count = 0
        batch_size = 50
        max_items = 66_666

        current_app.logger.info(
            f"Using database at {current_user.db_path} for user {current_user.id}"
        )

        # Create connection to user's SQLite database
        conn = sqlite3.connect(current_user.db_path)
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute(
            f"""
        CREATE TABLE IF NOT EXISTS {data_type} (
            id TEXT PRIMARY KEY,
            name TEXT,
            data TEXT,
            fetched_at TIMESTAMP
        )
        """
        )

        # Import json here
        import json

        # Process different data types
        if data_type == "top_tracks":
            # For top items we can only get up to 50 at a time with different time ranges
            for time_range in ["short_term", "medium_term", "long_term"]:
                results = sp.current_user_top_tracks(
                    limit=batch_size, time_range=time_range
                )
                items = results["items"]

                # Add time range to each item for reference
                for item in items:
                    item["time_range"] = time_range

                    # Store item in database
                    item_id = item["id"]
                    item_name = item.get("name", "Unknown")
                    item_json = json.dumps(item)

                    cursor.execute(
                        f"INSERT OR REPLACE INTO {data_type} (id, name, data, fetched_at) VALUES (?, ?, ?, ?)",
                        (item_id, item_name, item_json, datetime.utcnow().isoformat()),
                    )
                    record_count += 1

                # Commit after each batch
                conn.commit()

        elif data_type == "top_artists":
            # For top items we can only get up to 50 at a time with different time ranges
            for time_range in ["short_term", "medium_term", "long_term"]:
                results = sp.current_user_top_artists(
                    limit=batch_size, time_range=time_range
                )
                items = results["items"]

                # Add time range to each item for reference
                for item in items:
                    item["time_range"] = time_range

                    # Store item in database
                    item_id = item["id"]
                    item_name = item.get("name", "Unknown")
                    item_json = json.dumps(item)

                    cursor.execute(
                        f"INSERT OR REPLACE INTO {data_type} (id, name, data, fetched_at) VALUES (?, ?, ?, ?)",
                        (item_id, item_name, item_json, datetime.utcnow().isoformat()),
                    )
                    record_count += 1

                # Commit after each batch
                conn.commit()

        elif data_type == "saved_tracks":
            # For saved tracks, we can paginate through results
            results = sp.current_user_saved_tracks(limit=batch_size)
            items_processed = 0

            while results and items_processed < max_items:
                saved_items = results["items"]

                # Process and store each track
                for saved_item in saved_items:
                    track = saved_item["track"]
                    # Add the saved_at date from the parent item to the track
                    track["saved_at"] = saved_item["added_at"]

                    item_id = track["id"]
                    item_name = track.get("name", "Unknown")
                    item_json = json.dumps(track)

                    cursor.execute(
                        f"INSERT OR REPLACE INTO {data_type} (id, name, data, fetched_at) VALUES (?, ?, ?, ?)",
                        (item_id, item_name, item_json, datetime.utcnow().isoformat()),
                    )
                    record_count += 1
                    items_processed += 1

                # Commit after each batch
                conn.commit()

                # Get next batch if available and we haven't hit our limit
                if results["next"] and items_processed < max_items:
                    results = sp.next(results)
                else:
                    break

        elif data_type == "playlists":
            # For playlists, we can paginate through results
            results = sp.current_user_playlists(limit=batch_size)
            items_processed = 0

            while results and items_processed < max_items:
                items = results["items"]

                # Process and store each playlist
                for item in items:
                    item_id = item["id"]
                    item_name = item.get("name", "Unknown")
                    item_json = json.dumps(item)

                    cursor.execute(
                        f"INSERT OR REPLACE INTO {data_type} (id, name, data, fetched_at) VALUES (?, ?, ?, ?)",
                        (item_id, item_name, item_json, datetime.utcnow().isoformat()),
                    )
                    record_count += 1
                    items_processed += 1

                # Commit after each batch
                conn.commit()

                # Get next batch if available and we haven't hit our limit
                if results["next"] and items_processed < max_items:
                    results = sp.next(results)
                else:
                    break

        elif data_type == "recently_played":
            # Recently played tracks can be paginated
            results = sp.current_user_recently_played(limit=batch_size)
            items_processed = 0

            while results and items_processed < max_items:
                items = results["items"]

                # Process and store each recently played track
                for item in items:
                    # Get the track from the play history item
                    track = item["track"]
                    # Add the played_at time to the track data
                    track["played_at"] = item["played_at"]

                    # Create a composite ID since the same track can be played multiple times
                    # Format: track_id-timestamp
                    timestamp = (
                        item["played_at"]
                        .replace(":", "")
                        .replace(".", "")
                        .replace("Z", "")
                    )
                    item_id = f"{track['id']}-{timestamp}"
                    item_name = track.get("name", "Unknown")
                    item_json = json.dumps(track)

                    cursor.execute(
                        f"INSERT OR REPLACE INTO {data_type} (id, name, data, fetched_at) VALUES (?, ?, ?, ?)",
                        (item_id, item_name, item_json, datetime.utcnow().isoformat()),
                    )
                    record_count += 1
                    items_processed += 1

                # Commit after each batch
                conn.commit()

                # Get next batch if available and we haven't hit our limit
                if results["next"] and items_processed < max_items:
                    results = sp.next(results)
                else:
                    break

        else:
            flash(f"Unknown data type: {data_type}")
            return redirect(url_for("main.dashboard"))

        conn.close()

        # Update sync status in the main database
        sync = UserDataSync.query.filter_by(
            user_id=current_user.id, data_type_id=data_type_obj.id
        ).first()

        if not sync:
            sync = UserDataSync(user_id=current_user.id, data_type_id=data_type_obj.id)
            db.session.add(sync)

        sync.last_sync = datetime.utcnow()
        sync.record_count = record_count
        db.session.commit()

        flash(f"Successfully synced {record_count} {data_type} items")

    except Exception as e:
        current_app.logger.error(f"Error syncing {data_type}: {str(e)}")
        flash(f"Error syncing data: {str(e)}")

    return redirect(url_for("main.dashboard"))


@bp.route("/visualize/<data_type>")
@login_required
def visualize(data_type):
    if not current_user.spotify_token:
        flash("Spotify connection required. Please connect your account.")
        return redirect(url_for("spotify.connect"))

    # Check if data exists
    sync = (
        UserDataSync.query.join(SpotifyDataType)
        .filter(
            UserDataSync.user_id == current_user.id, SpotifyDataType.name == data_type
        )
        .first()
    )

    if not sync or not sync.last_sync:
        flash(f"No {data_type} data found. Please sync first.")
        return redirect(url_for("main.dashboard"))

    # Get data from user's SQLite DB
    try:
        import json

        conn = sqlite3.connect(current_user.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f"SELECT * FROM {data_type}")
        db_items = cursor.fetchall()

        # Convert SQLite rows to dictionaries with parsed JSON
        items = []
        for item in db_items:
            item_dict = dict(item)
            try:
                # Try to parse the data JSON string
                if "data" in item_dict and item_dict["data"]:
                    # More robust JSON parsing
                    try:
                        # First attempt direct parsing
                        item_dict["json_data"] = json.loads(item_dict["data"])
                    except json.JSONDecodeError:
                        # If that fails, try with string replacements
                        # Fix common JSON formatting issues
                        json_str = item_dict["data"]
                        # Replace Python-style single quotes with JSON-style double quotes
                        json_str = json_str.replace("'", '"')
                        # Handle potential escaped single quotes within strings
                        json_str = json_str.replace('\\"', '\\\\"')
                        # Try to parse again
                        try:
                            item_dict["json_data"] = json.loads(json_str)
                        except json.JSONDecodeError:
                            # If all parsing attempts fail, set an empty dict
                            current_app.logger.warning(
                                f"Could not parse JSON for item {item_dict.get('id')}"
                            )
                            item_dict["json_data"] = {}
                else:
                    item_dict["json_data"] = {}
            except Exception as json_err:
                current_app.logger.error(f"JSON parsing error: {str(json_err)}")
                item_dict["json_data"] = {}

            # Ensure required fields exist for visualization templates
            if data_type == "top_tracks" and "json_data" in item_dict:
                # Make sure artists field exists
                if "artists" not in item_dict["json_data"]:
                    item_dict["json_data"]["artists"] = []

                # Handle time_range if missing
                if "time_range" not in item_dict["json_data"]:
                    # Try to extract from the id or set a default
                    item_dict["json_data"]["time_range"] = "unknown"

            items.append(item_dict)

        conn.close()

        # Check if the specific template exists, otherwise use a generic one
        template_path = f"spotify/visualize_{data_type}.html"
        if not os.path.exists(
            os.path.join(current_app.root_path, "templates", template_path)
        ):
            template_path = "spotify/visualize_generic.html"

        return render_template(
            template_path,
            title=f'Visualize {data_type.replace("_", " ").title()}',
            items=items,
            data_type=data_type,
        )

    except Exception as e:
        current_app.logger.error(f"Visualization error: {str(e)}")
        flash(f"Error loading data: {str(e)}")
        return redirect(url_for("main.dashboard"))


@bp.route("/get_playlists", methods=["GET"])
@login_required
def get_playlists():
    from app.spotify.utils import get_spotify_client

    spotify = get_spotify_client(current_user)
    if not spotify:
        return jsonify({"error": "Not connected to Spotify"}), 401

    try:
        playlists = []
        results = spotify.current_user_playlists()

        for item in results["items"]:
            playlists.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "tracks": item["tracks"]["total"],
                    "image": item["images"][0]["url"] if item["images"] else None,
                }
            )

        # Get more playlists if available
        while results["next"]:
            results = spotify.next(results)
            for item in results["items"]:
                playlists.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "tracks": item["tracks"]["total"],
                        "image": item["images"][0]["url"] if item["images"] else None,
                    }
                )

        return jsonify({"playlists": playlists})

    except Exception as e:
        current_app.logger.error(f"Error fetching playlists: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
