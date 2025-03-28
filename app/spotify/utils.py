# app/spotify/utils.py
from flask import current_app
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from app.models import User
from app.spotify.routes import get_spotify_oauth


def get_spotify_client(user):
    from app import db

    """Get an authenticated Spotify client for a user"""
    if not user:
        return None

    # Get a user-specific OAuth with the correct cache path
    sp_oauth = get_spotify_oauth(user.id)

    if not user.spotify_token or not user.token_expires_at or user.is_token_expired():
        # If token is expired or missing, we need to refresh
        if user.spotify_refresh_token:
            # Refresh the token
            token_info = sp_oauth.refresh_access_token(user.spotify_refresh_token)
            user.set_spotify_tokens(
                token_info["access_token"],
                token_info.get("refresh_token", user.spotify_refresh_token),
                token_info["expires_in"],
            )
            db.session.commit()
        else:
            # No refresh token, can't proceed
            current_app.logger.error(f"No refresh token for user {user.id}")
            return None

    # Create and return Spotify client with the access token
    return spotipy.Spotify(auth=user.spotify_token)


def check_saved_tracks_dependency(current_user, data_type_name="saved_tracks"):
    from flask import flash, redirect, url_for
    from app.models import SpotifyDataType, UserDataSync

    saved_tracks_type = SpotifyDataType.query.filter_by(name=data_type_name).first()
    if not saved_tracks_type:
        flash(
            f"{data_type_name.replace('_', ' ').title()} data type not found. Please contact an administrator."
        )
        return False, redirect(url_for("main.dashboard"))

    saved_tracks_sync = UserDataSync.query.filter_by(
        user_id=current_user.id, data_type_id=saved_tracks_type.id
    ).first()

    if not saved_tracks_sync or not saved_tracks_sync.last_sync:
        flash(f"Please sync your {data_type_name.replace('_', ' ')} first.")
        return False, redirect(url_for("main.dashboard"))

    return True, None


def process_audio_data_batch(
    sp, cursor, data_type, batch, batch_info, single_track=False
):
    import json
    import time
    import random
    from datetime import datetime
    from flask import current_app, flash

    current_batch, total_batches = batch_info
    retry_count = 0
    success = False
    record_count = 0

    # Log processing start
    current_app.logger.info(
        f"Processing {data_type} batch {current_batch}/{total_batches} "
        f"with {len(batch)} tracks"
    )

    while not success and retry_count < 3:
        try:
            if single_track:
                # Process one track at a time (for audio analysis)
                results = []
                for track_id in batch:
                    if data_type == "audio_analysis":
                        # For audio analysis, get simplified data to save space
                        analysis = sp.audio_analysis(track_id)
                        if analysis:
                            simplified_analysis = {
                                "track": analysis.get("track", {}),
                                "sections": analysis.get("sections", []),
                                "segments_count": len(analysis.get("segments", [])),
                                "bars_count": len(analysis.get("bars", [])),
                                "beats_count": len(analysis.get("beats", [])),
                                "tatums_count": len(analysis.get("tatums", [])),
                                "segments_sample": analysis.get("segments", [])[:3],
                                "bars_sample": analysis.get("bars", [])[:3],
                                "beats_sample": analysis.get("beats", [])[:3],
                                "tatums_sample": analysis.get("tatums", [])[:3],
                            }
                            results.append(
                                {"id": track_id, "data": simplified_analysis}
                            )

                    # Add a small delay between individual track requests
                    if track_id != batch[-1]:
                        time.sleep(0.5)
            else:
                # Process a batch of tracks at once (for audio features)
                features_batch = sp.audio_features(batch)
                results = []
                for feature in features_batch:
                    if feature:  # Some tracks might not have features
                        results.append({"id": feature["id"], "data": feature})

            # Process and store each result
            for result in results:
                track_id = result["id"]
                data_json = json.dumps(result["data"])

                cursor.execute(
                    f"INSERT OR REPLACE INTO {data_type} (id, track_id, data, fetched_at) VALUES (?, ?, ?, ?)",
                    (track_id, track_id, data_json, datetime.utcnow().isoformat()),
                )
                record_count += 1

            # Commit after successful batch processing
            cursor.connection.commit()
            success = True

            current_app.logger.info(
                f"Saved {data_type} for {record_count} tracks in batch {current_batch}"
            )

        except Exception as batch_error:
            retry_count += 1
            error_msg = str(batch_error)
            current_app.logger.error(f"Error processing {data_type} batch: {error_msg}")

            # Check if this is a rate limiting issue
            if "429" in error_msg or "too many requests" in error_msg.lower():
                backoff = (2**retry_count) + random.uniform(0, 1)
                current_app.logger.info(
                    f"Rate limited. Retrying after {backoff:.2f} seconds (attempt {retry_count}/3)"
                )
                time.sleep(backoff)
            elif "403" in error_msg or "forbidden" in error_msg.lower():
                current_app.logger.info(
                    f"Permission issue. Waiting longer before retry (attempt {retry_count}/3)"
                )
                time.sleep(10)  # 10 second delay for permission issues
            else:
                time.sleep(2)

            # If we've hit max retries, stop processing entirely
            if retry_count >= 3:
                flash(f"Error processing batch {current_batch}: {error_msg}")
                current_app.logger.error(
                    f"Max retries reached for batch {current_batch}. Stopping all processing."
                )
                return -1  # Signal to stop all processing

    # Add a delay between batches to avoid rate limiting
    if current_batch < total_batches:
        time.sleep(2)

    return record_count


def setup_audio_data_table(cursor, data_type):
    import sqlite3
    from flask import current_app

    # Create table if it doesn't exist
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {data_type} (
            id TEXT PRIMARY KEY,
            track_id TEXT,
            data TEXT,
            fetched_at TIMESTAMP
        )
        """
    )

    # Add the track_id column if it doesn't exist (for backward compatibility)
    try:
        cursor.execute(f"SELECT track_id FROM {data_type} LIMIT 1")
    except sqlite3.OperationalError:
        current_app.logger.info(f"Adding track_id column to {data_type} table")
        cursor.execute(f"ALTER TABLE {data_type} ADD COLUMN track_id TEXT")
        cursor.connection.commit()


def get_tracks_to_process(cursor, data_type, max_tracks=None):
    from flask import flash, redirect, url_for

    # Get all saved track IDs from the database
    cursor.execute("SELECT id FROM saved_tracks")
    all_track_ids = [row[0] for row in cursor.fetchall()]

    if not all_track_ids:
        flash("No saved tracks found to process.")
        return None, redirect(url_for("main.dashboard")), 0

    # Limit the number of tracks if specified
    if max_tracks:
        all_track_ids = all_track_ids[:max_tracks]

    # Find which track IDs already have data to avoid reprocessing
    cursor.execute(f"SELECT track_id FROM {data_type}")
    existing_track_ids = {row[0] for row in cursor.fetchall()}

    # Filter to only process tracks that don't already have data
    tracks_to_process = [tid for tid in all_track_ids if tid not in existing_track_ids]

    if not tracks_to_process:
        flash(
            f"All {len(all_track_ids)} tracks already have {data_type.replace('_', ' ')} data."
        )
        return None, redirect(url_for("main.dashboard")), len(all_track_ids)

    return tracks_to_process, None, len(all_track_ids)
