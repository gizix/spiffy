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
import time
import json
from app.spotify import bp
from app import db
from app.models import User, SpotifyDataType, UserDataSync


# Dictionary to store progress information for each operation
# Format: { 'operation_id': { 'percent': 0, 'completed': 0, 'total': 100, 'status': 'Processing', 'complete': False } }
progress_tracker = {}


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


@bp.route("/progress/<operation_id>")
def check_progress(operation_id):
    """Return progress information for a specific operation"""
    if operation_id not in progress_tracker:
        return jsonify(
            {
                "percent": 0,
                "completed": 0,
                "total": 0,
                "status": "Unknown operation",
                "complete": False,
            }
        )

    return jsonify(progress_tracker[operation_id])


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
        # Gets the same SpotifyOAuth instance with unified scopes
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


def handle_spotify_error(e, retry_count=0, max_retries=3):
    """Handle Spotify API errors with exponential backoff retry"""
    # Log the error
    error_msg = str(e)
    current_app.logger.error(f"Spotify API error: {error_msg}")

    # Check if we can retry
    if retry_count < max_retries:
        # Calculate backoff time - exponential with jitter
        import random

        backoff = (2**retry_count) + random.uniform(0, 1)
        current_app.logger.info(
            f"Retrying after {backoff:.2f} seconds (attempt {retry_count + 1}/{max_retries})"
        )

        # Sleep and return True to indicate retry
        time.sleep(backoff)
        return True

    # No more retries
    return False


@bp.route("/sync/<data_type>")
@login_required
def sync_data(data_type):
    # Create a unique operation ID for tracking progress
    operation_id = f"{data_type}_sync_{current_user.id}"

    # Initialize progress tracking
    progress_tracker[operation_id] = {
        "percent": 0,
        "completed": 0,
        "total": 100,  # Initial estimate, will be updated
        "status": "Starting sync operation",
        "complete": False,
    }

    data_type_obj = SpotifyDataType.query.filter_by(name=data_type).first_or_404()

    sp = get_spotify_client()
    if not sp:
        # Clean up progress tracker
        if operation_id in progress_tracker:
            del progress_tracker[operation_id]
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

        # Process different data types
        if data_type == "top_tracks":
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

            # Update progress total - 3 time ranges with batch_size each
            progress_tracker[operation_id]["total"] = 3 * batch_size
            progress_tracker[operation_id]["status"] = "Syncing top tracks"
            items_processed = 0

            # For top items we can only get up to 50 at a time with different time ranges
            for time_range in ["short_term", "medium_term", "long_term"]:
                progress_tracker[operation_id][
                    "status"
                ] = f"Syncing {time_range} top tracks"

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
                    items_processed += 1

                    # Update progress
                    percent = min(
                        int(
                            (items_processed / progress_tracker[operation_id]["total"])
                            * 100
                        ),
                        100,
                    )
                    progress_tracker[operation_id].update(
                        {
                            "percent": percent,
                            "completed": items_processed,
                            "status": f"Processing {time_range} tracks ({items_processed}/{progress_tracker[operation_id]['total']})",
                        }
                    )

                # Commit after each batch
                conn.commit()

        elif data_type == "top_artists":
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

            # Update progress total - 3 time ranges with batch_size each
            progress_tracker[operation_id]["total"] = 3 * batch_size
            progress_tracker[operation_id]["status"] = "Syncing top artists"
            items_processed = 0

            # For top items we can only get up to 50 at a time with different time ranges
            for time_range in ["short_term", "medium_term", "long_term"]:
                progress_tracker[operation_id][
                    "status"
                ] = f"Syncing {time_range} top artists"

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
                    items_processed += 1

                    # Update progress
                    percent = min(
                        int(
                            (items_processed / progress_tracker[operation_id]["total"])
                            * 100
                        ),
                        100,
                    )
                    progress_tracker[operation_id].update(
                        {
                            "percent": percent,
                            "completed": items_processed,
                            "status": f"Processing {time_range} artists ({items_processed}/{progress_tracker[operation_id]['total']})",
                        }
                    )

                # Commit after each batch
                conn.commit()

        elif data_type == "saved_tracks":
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

            # For saved tracks, we can paginate through results
            results = sp.current_user_saved_tracks(limit=batch_size)

            # Update total count for progress tracking
            total_tracks = min(results["total"], max_items)
            progress_tracker[operation_id]["total"] = total_tracks
            progress_tracker[operation_id][
                "status"
            ] = f"Syncing saved tracks ({total_tracks} total)"

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

                    # Update progress
                    percent = min(int((items_processed / total_tracks) * 100), 100)
                    progress_tracker[operation_id].update(
                        {
                            "percent": percent,
                            "completed": items_processed,
                            "status": f"Processing track {items_processed} of {total_tracks}",
                        }
                    )

                # Commit after each batch
                conn.commit()

                # Get next batch if available and we haven't hit our limit
                if results["next"] and items_processed < max_items:
                    progress_tracker[operation_id][
                        "status"
                    ] = f"Fetching next batch of tracks ({items_processed}/{total_tracks})"
                    results = sp.next(results)
                else:
                    break

        elif data_type == "playlists":
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

            # For playlists, we can paginate through results
            results = sp.current_user_playlists(limit=batch_size)

            # Update total count for progress tracking
            total_playlists = min(results["total"], max_items)
            progress_tracker[operation_id]["total"] = total_playlists
            progress_tracker[operation_id][
                "status"
            ] = f"Syncing playlists ({total_playlists} total)"

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

                    # Update progress
                    percent = min(int((items_processed / total_playlists) * 100), 100)
                    progress_tracker[operation_id].update(
                        {
                            "percent": percent,
                            "completed": items_processed,
                            "status": f"Processing playlist {items_processed} of {total_playlists}",
                        }
                    )

                # Commit after each batch
                conn.commit()

                # Get next batch if available and we haven't hit our limit
                if results["next"] and items_processed < max_items:
                    progress_tracker[operation_id][
                        "status"
                    ] = f"Fetching next batch of playlists ({items_processed}/{total_playlists})"
                    results = sp.next(results)
                else:
                    break

        elif data_type == "recently_played":
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

            # Recently played tracks can be paginated
            results = sp.current_user_recently_played(limit=batch_size)

            # Set a reasonable estimate for recently played tracks
            estimated_total = min(batch_size * 5, max_items)  # Estimate 5 pages
            progress_tracker[operation_id]["total"] = estimated_total
            progress_tracker[operation_id]["status"] = "Syncing recently played tracks"

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

                    # Update progress - adjust if we get more than expected
                    if items_processed > progress_tracker[operation_id]["total"]:
                        progress_tracker[operation_id]["total"] = (
                            items_processed + batch_size
                        )

                    percent = min(
                        int(
                            (items_processed / progress_tracker[operation_id]["total"])
                            * 100
                        ),
                        100,
                    )
                    progress_tracker[operation_id].update(
                        {
                            "percent": percent,
                            "completed": items_processed,
                            "status": f"Processing track {items_processed}",
                        }
                    )

                # Commit after each batch
                conn.commit()

                # Get next batch if available and we haven't hit our limit
                if results["next"] and items_processed < max_items:
                    progress_tracker[operation_id][
                        "status"
                    ] = f"Fetching next batch of recently played tracks ({items_processed} processed)"
                    results = sp.next(results)
                else:
                    break

        elif data_type == "audio_features":
            if current_app.config.get("USE_CSV_FOR_AUDIO_FEATURES", True):
                # Import the CSV manager
                from app.spotify.csv_data_manager import get_track_features_manager

                # Create tables if they don't exist
                cursor.execute(
                    f"""
                CREATE TABLE IF NOT EXISTS {data_type} (
                    id TEXT PRIMARY KEY,
                    track_id TEXT,
                    data TEXT,
                    fetched_at TIMESTAMP,
                    data_source TEXT
                )
                """
                )

                # Check if data_source column exists, if not add it
                try:
                    cursor.execute(f"SELECT data_source FROM {data_type} LIMIT 1")
                except sqlite3.OperationalError:
                    current_app.logger.info(
                        f"Adding data_source column to {data_type} table"
                    )
                    cursor.execute(
                        f"ALTER TABLE {data_type} ADD COLUMN data_source TEXT"
                    )
                    conn.commit()

                # Update progress to show CSV loading
                progress_tracker[operation_id].update(
                    {
                        "percent": 5,
                        "status": "Loading audio features database... This may take a few seconds",
                    }
                )

                # First, get saved tracks from the user's database
                cursor.execute("SELECT id, name, data FROM saved_tracks")
                saved_tracks = cursor.fetchall()

                if not saved_tracks:
                    # Clean up progress tracker
                    if operation_id in progress_tracker:
                        del progress_tracker[operation_id]
                    flash("No saved tracks found. Please sync your saved tracks first.")
                    return redirect(url_for("main.dashboard"))

                # Update progress - database loading started
                progress_tracker[operation_id].update(
                    {
                        "percent": 10,
                        "status": "Loading audio features database... This may take several seconds",
                    }
                )

                # Get existing audio feature track IDs to avoid resyncing
                cursor.execute(f"SELECT track_id FROM {data_type}")
                existing_track_ids = {row[0] for row in cursor.fetchall()}

                # Update progress - initializing track manager
                progress_tracker[operation_id].update(
                    {"percent": 15, "status": "Initializing audio features database..."}
                )

                # Initialize the track features manager - this is the slow step!
                track_manager = get_track_features_manager()

                # Update progress after CSV is loaded
                progress_tracker[operation_id].update(
                    {
                        "percent": 30,
                        "status": "Audio features database loaded, processing tracks...",
                    }
                )

                # Process tracks in batches
                batch_size = 100
                track_ids_to_process = []
                track_names = {}

                for track in saved_tracks:
                    track_id = track[0]
                    track_names[track_id] = track[1]

                    # Check if we already have features for this track
                    if track_id not in existing_track_ids:
                        track_ids_to_process.append(track_id)

                # If no tracks to process, we're done
                if not track_ids_to_process:
                    # Get the total count of audio features in the database
                    cursor.execute(f"SELECT COUNT(*) FROM {data_type}")
                    total_features_count = cursor.fetchone()[0]

                    # Update the sync status with the ACTUAL count of features
                    sync = UserDataSync.query.filter_by(
                        user_id=current_user.id, data_type_id=data_type_obj.id
                    ).first()

                    if not sync:
                        sync = UserDataSync(
                            user_id=current_user.id, data_type_id=data_type_obj.id
                        )
                        db.session.add(sync)

                    sync.last_sync = datetime.utcnow()
                    sync.record_count = total_features_count
                    db.session.commit()

                    # Update progress to complete immediately
                    progress_tracker[operation_id].update(
                        {
                            "percent": 100,
                            "completed": 0,
                            "total": 0,
                            "status": f"All tracks already have audio features ({total_features_count} total features)",
                            "complete": True,
                        }
                    )

                    flash(
                        f"All saved tracks already have audio features data. Database contains {total_features_count} audio features."
                    )
                    return redirect(url_for("main.dashboard"))

                # Update progress tracker with correct total count
                progress_tracker[operation_id]["total"] = len(track_ids_to_process)
                progress_tracker[operation_id][
                    "status"
                ] = f"Fetching audio features for {len(track_ids_to_process)} tracks from CSV"

                current_app.logger.info(
                    f"Fetching audio features for {len(track_ids_to_process)} tracks from CSV"
                )
                total_batches = (
                    len(track_ids_to_process) + batch_size - 1
                ) // batch_size

                tracks_processed = 0
                for i in range(0, len(track_ids_to_process), batch_size):
                    batch = track_ids_to_process[i : i + batch_size]
                    current_batch = i // batch_size + 1

                    # Update progress status
                    progress_tracker[operation_id][
                        "status"
                    ] = f"Processing batch {current_batch}/{total_batches} from CSV"

                    # Get features for this batch from CSV
                    features_batch = track_manager.get_features_batch(batch)
                    batch_record_count = 0

                    for feature in features_batch:
                        if feature:
                            track_id = feature["id"]
                            feature_json = json.dumps(feature)
                            cursor.execute(
                                f"INSERT OR REPLACE INTO {data_type} (id, track_id, data, fetched_at, data_source) VALUES (?, ?, ?, ?, ?)",
                                (
                                    track_id,
                                    track_id,
                                    feature_json,
                                    datetime.utcnow().isoformat(),
                                    "csv",
                                ),
                            )

                            batch_record_count += 1
                            record_count += 1

                    tracks_processed += len(batch)

                    # Update progress percentage
                    percent = min(
                        int((tracks_processed / len(track_ids_to_process)) * 100), 100
                    )
                    progress_tracker[operation_id].update(
                        {
                            "percent": percent,
                            "completed": tracks_processed,
                            "status": f"Processed batch {current_batch}/{total_batches}: Found {batch_record_count} features",
                        }
                    )

                    # Log progress
                    current_app.logger.info(
                        f"Processed batch {current_batch}/{total_batches}: Found {batch_record_count} features"
                    )

                    # Commit after each batch
                    conn.commit()

                    # For tracks that weren't found in the CSV, log them
                    missing_tracks = [
                        tid
                        for tid in batch
                        if tid not in [f.get("id") for f in features_batch]
                    ]

                    if missing_tracks:
                        missing_track_names = [
                            track_names.get(tid, tid) for tid in missing_tracks
                        ]
                        current_app.logger.warning(
                            f"Couldn't find audio features for {len(missing_tracks)} tracks in CSV: {', '.join(missing_track_names[:5])}"
                            + (
                                f" and {len(missing_track_names) - 5} more"
                                if len(missing_track_names) > 5
                                else ""
                            )
                        )

                # Get the total count of audio features for accurate reporting
                cursor.execute(f"SELECT COUNT(*) FROM {data_type}")
                total_features_count = cursor.fetchone()[0]

                # Update the sync status with the ACTUAL count of features in the database
                sync = UserDataSync.query.filter_by(
                    user_id=current_user.id, data_type_id=data_type_obj.id
                ).first()

                if not sync:
                    sync = UserDataSync(
                        user_id=current_user.id, data_type_id=data_type_obj.id
                    )
                    db.session.add(sync)

                sync.last_sync = datetime.utcnow()
                # Use the total count from the database, not just new records
                sync.record_count = total_features_count
                db.session.commit()

                # Update progress to complete with the actual record count
                progress_tracker[operation_id].update(
                    {
                        "percent": 100,
                        "completed": len(track_ids_to_process),
                        "total": len(track_ids_to_process),
                        "status": f"Sync complete - {total_features_count} total audio features in database",
                        "complete": True,
                    }
                )

                # Show the accurate count in the flash message
                flash(
                    f"Successfully synced audio features. Database contains {total_features_count} audio features."
                )

                # Skip the general sync update at the end of the function
                return redirect(url_for("main.dashboard"))
            else:
                # Original API-based implementation
                from app.spotify.utils import (
                    check_saved_tracks_dependency,
                    setup_audio_data_table,
                    get_tracks_to_process,
                    process_audio_data_batch,
                )

                # Check saved tracks dependency
                success, redirect_response = check_saved_tracks_dependency(current_user)

                if not success:
                    # Clean up progress tracker
                    if operation_id in progress_tracker:
                        del progress_tracker[operation_id]
                    return redirect_response

                # Set up database table
                setup_audio_data_table(cursor, data_type)

                # Get tracks that need processing
                tracks_to_process, redirect_response, total_tracks = (
                    get_tracks_to_process(cursor, data_type)
                )

                if not tracks_to_process:
                    # Clean up progress tracker
                    if operation_id in progress_tracker:
                        del progress_tracker[operation_id]
                    return redirect_response

                # Update progress tracker
                progress_tracker[operation_id]["total"] = len(tracks_to_process)
                progress_tracker[operation_id][
                    "status"
                ] = f"Processing audio features for {len(tracks_to_process)} tracks"

                # Process tracks in batches
                max_batch_size = 20
                total_batches = (
                    len(tracks_to_process) + max_batch_size - 1
                ) // max_batch_size
                current_app.logger.info(
                    f"Processing audio features for {len(tracks_to_process)} new tracks "
                    f"out of {total_tracks} total tracks in {total_batches} batches"
                )

                tracks_processed = 0
                for i in range(0, len(tracks_to_process), max_batch_size):
                    batch = tracks_to_process[i : i + max_batch_size]
                    current_batch = i // max_batch_size + 1

                    # Update progress status
                    progress_tracker[operation_id][
                        "status"
                    ] = f"Processing batch {current_batch} of {total_batches}"

                    batch_count = process_audio_data_batch(
                        sp,
                        cursor,
                        data_type,
                        batch,
                        (current_batch, total_batches),
                        single_track=False,
                    )

                    # If batch processing returned -1, stop processing entirely
                    if batch_count == -1:
                        progress_tracker[operation_id][
                            "status"
                        ] = f"Error in batch {current_batch}"
                        flash(
                            f"Stopped processing {data_type} after errors in batch {current_batch}."
                        )
                        break

                    tracks_processed += len(batch)
                    record_count += batch_count

                    # Update progress percentage
                    percent = min(
                        int((tracks_processed / len(tracks_to_process)) * 100), 100
                    )
                    progress_tracker[operation_id].update(
                        {
                            "percent": percent,
                            "completed": tracks_processed,
                        }
                    )

        elif data_type == "artists":
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

            # Check for dependencies - we need at least one of these data sources
            required_sources = ["saved_tracks", "top_tracks", "playlists"]
            dependencies_met = False

            for source in required_sources:
                source_type = SpotifyDataType.query.filter_by(name=source).first()
                if not source_type:
                    continue

                sync = UserDataSync.query.filter_by(
                    user_id=current_user.id, data_type_id=source_type.id
                ).first()

                if sync and sync.last_sync:
                    dependencies_met = True
                    break

            if not dependencies_met:
                # Clean up progress tracker
                if operation_id in progress_tracker:
                    del progress_tracker[operation_id]
                flash(
                    "Please sync at least one of: saved tracks, top tracks, or playlists first."
                )
                return redirect(url_for("main.dashboard"))

            # Set to collect unique artist IDs
            artist_ids = set()

            # Update progress status
            progress_tracker[operation_id][
                "status"
            ] = "Collecting artist IDs from your saved data"

            # Fetch artist IDs from saved_tracks
            try:
                cursor.execute("SELECT data FROM saved_tracks")
                for row in cursor.fetchall():
                    track_data = json.loads(row[0])
                    for artist in track_data.get("artists", []):
                        artist_ids.add(artist["id"])
            except (sqlite3.OperationalError, KeyError, json.JSONDecodeError) as e:
                current_app.logger.info(
                    f"Could not extract artists from saved_tracks: {str(e)}"
                )

            # Fetch artist IDs from top_tracks
            try:
                cursor.execute("SELECT data FROM top_tracks")
                for row in cursor.fetchall():
                    track_data = json.loads(row[0])
                    for artist in track_data.get("artists", []):
                        artist_ids.add(artist["id"])
            except (sqlite3.OperationalError, KeyError, json.JSONDecodeError) as e:
                current_app.logger.info(
                    f"Could not extract artists from top_tracks: {str(e)}"
                )

            # Update progress with total artist count
            total_artists = len(artist_ids)
            if total_artists == 0:
                # Clean up progress tracker
                if operation_id in progress_tracker:
                    del progress_tracker[operation_id]
                flash("No artists found in your saved tracks or top tracks.")
                return redirect(url_for("main.dashboard"))

            progress_tracker[operation_id]["total"] = total_artists
            progress_tracker[operation_id][
                "status"
            ] = f"Syncing data for {total_artists} artists"

            # Process artists in batches of 50 (Spotify API limit for artists endpoint)
            batch_size = 50
            artist_id_list = list(artist_ids)
            items_processed = 0

            for i in range(0, total_artists, batch_size):
                batch = artist_id_list[i : i + batch_size]

                progress_tracker[operation_id][
                    "status"
                ] = f"Processing artists {i+1}-{min(i+batch_size, total_artists)} of {total_artists}"

                try:
                    # Format the IDs parameter exactly as required by the API
                    ids_param = ",".join(batch)
                    artists_response = sp._get("artists", ids=ids_param)

                    # Process each artist
                    for artist in artists_response.get("artists", []):
                        item_id = artist["id"]
                        item_name = artist.get("name", "Unknown")
                        item_json = json.dumps(artist)

                        cursor.execute(
                            f"INSERT OR REPLACE INTO {data_type} (id, name, data, fetched_at) VALUES (?, ?, ?, ?)",
                            (
                                item_id,
                                item_name,
                                item_json,
                                datetime.utcnow().isoformat(),
                            ),
                        )
                        record_count += 1
                        items_processed += 1

                        # Update progress
                        percent = min(int((items_processed / total_artists) * 100), 100)
                        progress_tracker[operation_id].update(
                            {
                                "percent": percent,
                                "completed": items_processed,
                                "status": f"Processing artist {items_processed} of {total_artists}",
                            }
                        )

                    # Commit after each batch
                    conn.commit()

                    # Add a small delay to avoid rate limiting
                    time.sleep(0.5)

                except Exception as e:
                    current_app.logger.error(
                        f"Error processing artists batch: {str(e)}"
                    )
                    # If rate limiting, wait longer
                    if "rate limit" in str(e).lower():
                        time.sleep(2)

        elif data_type == "audio_analysis":
            from app.spotify.utils import (
                check_saved_tracks_dependency,
                setup_audio_data_table,
                get_tracks_to_process,
                process_audio_data_batch,
            )

            # Check saved tracks dependency
            success, redirect_response = check_saved_tracks_dependency(current_user)

            if not success:
                # Clean up progress tracker
                if operation_id in progress_tracker:
                    del progress_tracker[operation_id]
                return redirect_response

            # Set up database table
            setup_audio_data_table(cursor, data_type)

            # Get tracks that need processing (limit to 500 for audio analysis)
            tracks_to_process, redirect_response, total_tracks = get_tracks_to_process(
                cursor, data_type, max_tracks=500
            )

            if not tracks_to_process:
                # Clean up progress tracker
                if operation_id in progress_tracker:
                    del progress_tracker[operation_id]
                return redirect_response

            # Update progress tracker
            progress_tracker[operation_id]["total"] = len(tracks_to_process)
            progress_tracker[operation_id][
                "status"
            ] = f"Processing audio analysis for {len(tracks_to_process)} tracks"

            # Process tracks individually (audio analysis is heavy)
            batch_size = 10
            total_batches = (len(tracks_to_process) + batch_size - 1) // batch_size
            current_app.logger.info(
                f"Processing audio analysis for {len(tracks_to_process)} new tracks "
                f"out of {total_tracks} total tracks in {total_batches} batches"
            )

            tracks_processed = 0
            for i in range(0, len(tracks_to_process), batch_size):
                batch = tracks_to_process[i : i + batch_size]
                current_batch = i // batch_size + 1

                # Update progress status
                progress_tracker[operation_id][
                    "status"
                ] = f"Processing batch {current_batch} of {total_batches}"

                batch_count = process_audio_data_batch(
                    sp,
                    cursor,
                    data_type,
                    batch,
                    (current_batch, total_batches),
                    single_track=True,
                )

                # If batch processing returned -1, stop processing entirely
                if batch_count == -1:
                    progress_tracker[operation_id][
                        "status"
                    ] = f"Error in batch {current_batch}"
                    flash(
                        f"Stopped processing {data_type} after errors in batch {current_batch}."
                    )
                    break

                tracks_processed += len(batch)
                record_count += batch_count

                # Update progress percentage
                percent = min(
                    int((tracks_processed / len(tracks_to_process)) * 100), 100
                )
                progress_tracker[operation_id].update(
                    {
                        "percent": percent,
                        "completed": tracks_processed,
                    }
                )

        else:
            # Clean up progress tracker
            if operation_id in progress_tracker:
                del progress_tracker[operation_id]
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

        # Update progress to complete
        progress_tracker[operation_id].update(
            {
                "percent": 100,
                "completed": progress_tracker[operation_id]["total"],
                "status": "Sync complete",
                "complete": True,
            }
        )

        # Keep the progress information available for a short time for final status check
        import threading

        def cleanup_progress():
            if operation_id in progress_tracker:
                del progress_tracker[operation_id]

        # Schedule cleanup after 5 minutes
        timer = threading.Timer(300, cleanup_progress)
        timer.daemon = True
        timer.start()

        flash(f"Successfully synced {record_count} {data_type} items")

    except Exception as e:
        # Update progress to show error
        if operation_id in progress_tracker:
            progress_tracker[operation_id].update(
                {"status": f"Error: {str(e)}", "complete": True}
            )

        current_app.logger.error(f"Error syncing {data_type}: {str(e)}")
        if data_type == "audio_features" and "no such table: saved_tracks" in str(e):
            error_message = "You must sync your Saved Tracks first."
        else:
            error_message = str(e)
        flash(f"Error syncing data: {error_message}")

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
        conn = sqlite3.connect(current_user.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # For audio_features, join with saved_tracks to get additional track info if needed
        if data_type == "audio_features":
            # Check if we need to join data from saved_tracks
            try:
                # First check if the audio_features table has all the track info
                cursor.execute(f"SELECT * FROM {data_type} LIMIT 1")
                columns = [col[0] for col in cursor.description]
                has_track_info = all(
                    col in columns for col in ["name", "artists", "album"]
                )

                if not has_track_info:
                    # Join with saved_tracks to get the track info
                    current_app.logger.info(
                        "Joining audio_features with saved_tracks to get track info"
                    )
                    cursor.execute(
                        f"""
                        SELECT af.*, st.data as track_data, af.data_source
                        FROM {data_type} af
                        LEFT JOIN saved_tracks st ON af.track_id = st.id
                    """
                    )
                else:
                    # Already has track info in the table
                    cursor.execute(f"SELECT * FROM {data_type}")
            except sqlite3.OperationalError as e:
                # Handle case where data_source column might not exist
                if "no such column: data_source" in str(e):
                    cursor.execute(
                        f"SELECT *, 'unknown' as data_source FROM {data_type}"
                    )
                else:
                    raise

        elif data_type == "artists":
            # Log that we're starting to visualize artists
            current_app.logger.info(f"Visualizing artists for user {current_user.id}")

            # Get data from user's SQLite DB
            try:
                conn = sqlite3.connect(current_user.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Check if the table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='artists'"
                )
                if not cursor.fetchone():
                    current_app.logger.warning(
                        "Artists table doesn't exist in the database"
                    )
                    flash("No artists data found. Please sync your artists first.")
                    return redirect(url_for("main.dashboard"))

                # Query all artists
                cursor.execute("SELECT * FROM artists")
                db_items = cursor.fetchall()

                # Log how many artists we found
                current_app.logger.info(
                    f"Found {len(db_items)} artists in the database"
                )

                # Convert SQLite rows to dictionaries with parsed JSON
                items = []
                for item in db_items:
                    item_dict = dict(item)
                    try:
                        # Parse the data JSON string
                        if "data" in item_dict and item_dict["data"]:
                            item_dict["json_data"] = json.loads(item_dict["data"])
                        else:
                            item_dict["json_data"] = {}
                            current_app.logger.warning(
                                f"No data field for artist: {item_dict.get('name', 'Unknown')}"
                            )
                    except Exception as json_err:
                        current_app.logger.error(
                            f"JSON parsing error for artist {item_dict.get('name', 'Unknown')}: {str(json_err)}"
                        )
                        item_dict["json_data"] = {}

                    items.append(item_dict)

                # Debug: Log a sample item if we have any
                if items:
                    sample_item = items[0]
                    current_app.logger.info(
                        f"Sample artist: {sample_item.get('name', 'Unknown')}"
                    )

                    # Check if the sample item has key data we need
                    if "json_data" in sample_item:
                        has_followers = "followers" in sample_item["json_data"]
                        has_genres = "genres" in sample_item["json_data"]
                        has_popularity = "popularity" in sample_item["json_data"]

                        current_app.logger.info(
                            f"Sample data check - Followers: {has_followers}, "
                            + f"Genres: {has_genres}, Popularity: {has_popularity}"
                        )

                conn.close()

                # Render the template with artists data
                return render_template(
                    "spotify/visualize_artists.html",
                    title="Visualize Artists",
                    items=items,
                    data_type=data_type,
                )

            except Exception as e:
                current_app.logger.error(f"Error visualizing artists: {str(e)}")
                flash(f"Error loading artists data: {str(e)}")
                return redirect(url_for("main.dashboard"))

        else:
            cursor.execute(f"SELECT * FROM {data_type}")

        db_items = cursor.fetchall()

        # Convert SQLite rows to dictionaries with parsed JSON
        items = []
        for item in db_items:
            item_dict = dict(item)
            try:
                # Parse the data JSON string
                if "data" in item_dict and item_dict["data"]:
                    item_dict["json_data"] = json.loads(item_dict["data"])

                    # For audio features, handle the case where we joined with saved_tracks
                    if (
                            data_type == "audio_features"
                            and "track_data" in item_dict
                            and item_dict["track_data"]
                    ):
                        track_info = json.loads(item_dict["track_data"])

                        # Ensure audio feature data has essential track info
                        if (
                                "name" not in item_dict["json_data"]
                                and "name" in track_info
                        ):
                            item_dict["json_data"]["name"] = track_info["name"]

                        if (
                                "artists" not in item_dict["json_data"]
                                and "artists" in track_info
                        ):
                            # Handle both string and array of artist objects
                            # Handle different artist formats
                            artists_data = track_info.get("artists", "")
                            if isinstance(artists_data, list):
                                # List of artist objects from Spotify API
                                if artists_data and isinstance(artists_data[0], dict):
                                    item_dict["json_data"]["artists"] = ", ".join(
                                        [a.get("name", "") for a in artists_data]
                                    )
                                # List of strings from CSV
                                else:
                                    item_dict["json_data"]["artists"] = ", ".join(
                                        artists_data
                                    )
                            elif isinstance(artists_data, str):
                                # Try to parse string representations like "['Artist1', 'Artist2']"
                                if artists_data.startswith(
                                        "["
                                ) and artists_data.endswith("]"):
                                    try:
                                        # Convert to proper list if it's a string representation
                                        artists_list = eval(artists_data)
                                        if isinstance(artists_list, list):
                                            item_dict["json_data"]["artists"] = (
                                                ", ".join(artists_list)
                                            )
                                        else:
                                            item_dict["json_data"][
                                                "artists"
                                            ] = artists_data
                                    except:
                                        item_dict["json_data"]["artists"] = artists_data
                                else:
                                    item_dict["json_data"]["artists"] = artists_data
                            else:
                                item_dict["json_data"]["artists"] = str(artists_data)

                        if (
                                "album" not in item_dict["json_data"]
                                and "album" in track_info
                        ):
                            # Handle both string and album object
                            if isinstance(track_info.get("album"), dict):
                                item_dict["json_data"]["album"] = track_info[
                                    "album"
                                ].get("name", "")
                            else:
                                item_dict["json_data"]["album"] = track_info.get(
                                    "album", ""
                                )

                    # Add data_source to json_data for easy access in template
                    if "data_source" in item_dict:
                        item_dict["json_data"]["data_source"] = item_dict["data_source"]
                else:
                    item_dict["json_data"] = {}
            except Exception as json_err:
                current_app.logger.error(f"JSON parsing error: {str(json_err)}")
                item_dict["json_data"] = {}

            items.append(item_dict)

        conn.close()

        # Check if the specific template exists, otherwise use a generic one
        template_path = f"spotify/visualize_{data_type}.html"
        if not os.path.exists(
                os.path.join(current_app.root_path, "templates", template_path)
        ):
            template_path = "spotify/visualize_generic.html"

        # For audio_features, prepare a simpler data structure for the JavaScript
        # For audio_features, prepare a simpler data structure for the JavaScript
        if data_type == "audio_features":
            js_items = []
            for item in items:
                if "json_data" in item and item["json_data"]:
                    # Create a new dictionary for JavaScript with all required fields
                    js_item = {}

                    # Copy basic track info
                    js_item["id"] = item.get("id", "")
                    js_item["track_id"] = item.get("track_id", "")
                    js_item["name"] = item["json_data"].get("name", "Unknown")
                    js_item["artists"] = item["json_data"].get("artists", "") or item["json_data"].get("artists_x",
                                                                                                       "Unknown")
                    js_item["album"] = item["json_data"].get("album", "") or item["json_data"].get("album_name",
                                                                                                   "Unknown")

                    # Handle the suffixed column names (_x and _y variants)
                    # Try _x version first, then _y version, then plain version, then default to 0
                    js_item["tempo"] = item["json_data"].get("tempo_x", item["json_data"].get("tempo_y",
                                                                                              item["json_data"].get(
                                                                                                  "tempo", 0)))
                    js_item["danceability"] = item["json_data"].get("danceability_x",
                                                                    item["json_data"].get("danceability_y",
                                                                                          item["json_data"].get(
                                                                                              "danceability", 0)))
                    js_item["energy"] = item["json_data"].get("energy_x", item["json_data"].get("energy_y",
                                                                                                item["json_data"].get(
                                                                                                    "energy", 0)))
                    js_item["valence"] = item["json_data"].get("valence_x", item["json_data"].get("valence_y",
                                                                                                  item["json_data"].get(
                                                                                                      "valence", 0)))
                    js_item["acousticness"] = item["json_data"].get("acousticness_x",
                                                                    item["json_data"].get("acousticness_y",
                                                                                          item["json_data"].get(
                                                                                              "acousticness", 0)))
                    js_item["instrumentalness"] = item["json_data"].get("instrumentalness_x",
                                                                        item["json_data"].get("instrumentalness_y",
                                                                                              item["json_data"].get(
                                                                                                  "instrumentalness",
                                                                                                  0)))
                    js_item["liveness"] = item["json_data"].get("liveness_x", item["json_data"].get("liveness_y", item[
                        "json_data"].get("liveness", 0)))
                    js_item["speechiness"] = item["json_data"].get("speechiness_x",
                                                                   item["json_data"].get("speechiness_y",
                                                                                         item["json_data"].get(
                                                                                             "speechiness", 0)))
                    js_item["key"] = item["json_data"].get("key_x", item["json_data"].get("key_y",
                                                                                          item["json_data"].get("key",
                                                                                                                0)))
                    js_item["mode"] = item["json_data"].get("mode_x", item["json_data"].get("mode_y",
                                                                                            item["json_data"].get(
                                                                                                "mode", 0)))

                    # Add data source
                    js_item["data_source"] = item["json_data"].get("data_source", "unknown")

                    js_items.append(js_item)

            # Log info about the processed data
            current_app.logger.info(f"Processed {len(js_items)} tracks with audio features")
            if js_items:
                sample = js_items[0]
                current_app.logger.info(
                    f"Sample processed track: {sample.get('name')} - Tempo: {sample.get('tempo')}, Energy: {sample.get('energy')}")

            return render_template(
                template_path,
                title=f'Visualize {data_type.replace("_", " ").title()}',
                items=items,
                js_items=js_items,
                data_type=data_type,
            )
        else:
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
