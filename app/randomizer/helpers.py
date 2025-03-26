# app/randomizer/helpers.py
import random
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from flask import current_app
from flask_login import current_user
from app import db
from app.models import (
    RandomizerConfig,
    RandomizerRule,
    SpotifyDataType,
    UserDataSync,
    PlaylistCreationHistory,
)
from app.spotify.utils import get_spotify_client


def extract_rules_from_form(request):
    """Extract rules from form data, supporting multiple formats"""
    rules = []

    # Get all form data as MultiDict
    form_data = request.form.to_dict(flat=False)

    # Process the empty bracket notation form data
    if "rules[][rule_type]" in form_data and "rules[][parameter]" in form_data:
        rule_types = form_data.get("rules[][rule_type]", [])
        rule_params = form_data.get("rules[][parameter]", [])

        # Match types with parameters
        for i in range(min(len(rule_types), len(rule_params))):
            if rule_types[i] and rule_params[i]:
                rules.append({"rule_type": rule_types[i], "parameter": rule_params[i]})
                current_app.logger.info(
                    f"Processing empty bracket rule {i + 1}: {rule_types[i]} = {rule_params[i]}"
                )

    # Also check for indexed notation
    for key in request.form.keys():
        if (
            key.startswith("rules[")
            and key.endswith("[rule_type]")
            and "[rule_type]" not in key
        ):
            index = key[6:-11]  # Extract the index number
            param_key = f"rules[{index}][parameter]"
            rule_type = request.form.get(key)
            param_value = request.form.get(param_key)

            if rule_type and param_value:
                rules.append({"rule_type": rule_type, "parameter": param_value})
                current_app.logger.info(
                    f"Processing indexed rule: {rule_type} = {param_value}"
                )

    current_app.logger.info(f"Extracted {len(rules)} rules from form")
    current_app.logger.info(f"All rules: {rules}")

    return rules


def save_configuration(rules, config_name, user_id):
    """Save rules as a named configuration"""
    if not config_name:
        return None

    config = RandomizerConfig(
        name=config_name,
        user_id=user_id,
        created_at=datetime.utcnow(),
        last_used=datetime.utcnow(),
    )
    db.session.add(config)
    db.session.flush()

    for rule_data in rules:
        rule = RandomizerRule(
            config_id=config.id,
            rule_type=rule_data["rule_type"],
            parameter=rule_data["parameter"],
        )
        db.session.add(rule)

    db.session.commit()
    current_app.logger.info(
        f"Saved new configuration '{config_name}' with ID {config.id}"
    )

    return config


def get_tracks_from_source(source_type, source_playlist_id, user):
    """Retrieve tracks from either a playlist or user's saved tracks"""
    if source_type == "playlist":
        # Get Spotify client for playlist tracks
        spotify = get_spotify_client(user)
        if not spotify:
            return None, "Could not connect to Spotify. Please log in again."

        # Get the playlist name for better logging
        if source_playlist_id:
            try:
                source_playlist = spotify.playlist(source_playlist_id)
                source_playlist_name = source_playlist["name"]
                current_app.logger.info(
                    f"Source playlist: '{source_playlist_name}' (ID: {source_playlist_id})"
                )
            except:
                source_playlist_name = f"ID: {source_playlist_id}"
                current_app.logger.info(f"Source playlist ID: {source_playlist_id}")

        tracks = get_source_tracks_from_playlist(spotify, source_playlist_id)
    else:  # liked_songs
        # Check if saved_tracks are synced
        data_type_obj = SpotifyDataType.query.filter_by(name="saved_tracks").first()
        if not data_type_obj:
            return (
                None,
                "Saved tracks data type not found. Please contact an administrator.",
            )

        sync = UserDataSync.query.filter_by(
            user_id=user.id, data_type_id=data_type_obj.id
        ).first()

        if not sync or not sync.last_sync:
            return None, "Please sync your saved tracks first from the dashboard."

        # Log when the tracks were last synced
        current_app.logger.info(f"Using saved tracks - last synced: {sync.last_sync}")

        # Get tracks from user's database
        tracks = get_source_tracks_from_db("saved_tracks")

    if not tracks:
        return None, "No tracks found in the selected source"

    current_app.logger.info(f"Found {len(tracks)} tracks from source")
    return tracks, None


def get_source_tracks_from_playlist(spotify, playlist_id):
    """Get tracks from a playlist with better timeout handling"""
    try:
        tracks = []
        offset = 0
        limit = 100
        total = None

        # Use pagination with explicit offset/limit to better handle large playlists
        while total is None or offset < total:
            current_app.logger.info(
                f"Fetching playlist tracks: offset={offset}, limit={limit}"
            )

            try:
                results = spotify.playlist_items(
                    playlist_id, limit=limit, offset=offset
                )

                if total is None:
                    total = results["total"]
                    current_app.logger.info(f"Total playlist tracks: {total}")

                # Process this batch
                batch_tracks = [
                    {
                        "uri": item["track"]["uri"],
                        "name": item["track"]["name"],
                        "artist": item["track"]["artists"][0]["name"],
                        "artist_id": item["track"]["artists"][0]["id"],
                        "duration_ms": item["track"]["duration_ms"],
                        "album": item["track"]["album"]["name"],
                    }
                    for item in results["items"]
                    if item["track"] is not None
                ]

                tracks.extend(batch_tracks)
                offset += limit

                # Add a small delay to avoid rate limiting
                if total > 200:
                    import time

                    time.sleep(0.1)

            except requests.exceptions.Timeout:
                current_app.logger.warning(
                    f"Timeout fetching batch at offset {offset}. Continuing with collected tracks."
                )
                break

        current_app.logger.info(
            f"Successfully fetched {len(tracks)} tracks from playlist"
        )
        return tracks

    except Exception as e:
        current_app.logger.error(f"Error fetching playlist tracks: {str(e)}")
        # Return whatever we managed to fetch so far
        return tracks if "tracks" in locals() and tracks else []


def get_source_tracks_from_db(data_type):
    """Get tracks from the user's local database with improved explicit flag handling"""
    try:
        conn = sqlite3.connect(current_user.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if the table exists
        cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{data_type}'"
        )
        if not cursor.fetchone():
            current_app.logger.error(
                f"Table {data_type} does not exist in user database"
            )
            return []

        current_app.logger.info(f"Fetching tracks from local database: {data_type}")
        cursor.execute(f"SELECT * FROM {data_type}")
        db_items = cursor.fetchall()

        # Extract track information from JSON data
        tracks = []
        explicit_tracks_count = 0
        for item in db_items:
            try:
                # Parse the JSON data string
                item_data = json.loads(item["data"])

                # For saved_tracks, the track info is directly in the item_data
                # since we already processed it during sync
                track_info = item_data

                # Make sure we have a URI for the track
                if "uri" not in track_info:
                    continue

                # Check if the track has an explicit flag and count explicit tracks
                is_explicit = False
                if "explicit" in track_info:
                    is_explicit = bool(track_info["explicit"])
                    if is_explicit:
                        explicit_tracks_count += 1

                # Create a standardized track object
                track = {
                    "uri": track_info.get("uri"),
                    "name": track_info.get("name", "Unknown"),
                    "artist": track_info.get("artists", [{}])[0].get("name", "Unknown"),
                    "artist_id": track_info.get("artists", [{}])[0].get("id", ""),
                    "duration_ms": track_info.get("duration_ms", 0),
                    "album": track_info.get("album", {}).get("name", "Unknown"),
                    "explicit": is_explicit,  # Explicitly include this field
                    "popularity": track_info.get("popularity", 0),
                }
                tracks.append(track)

            except (json.JSONDecodeError, KeyError) as e:
                current_app.logger.error(f"Error parsing track data: {str(e)}")
                continue

        conn.close()
        current_app.logger.info(
            f"Successfully loaded {len(tracks)} tracks from database with {explicit_tracks_count} explicit tracks"
        )
        return tracks

    except Exception as e:
        current_app.logger.error(
            f"Error loading tracks from database: {str(e)}", exc_info=True
        )
        return []


def log_config_details(config, operation="accessed"):
    """Log detailed information about a configuration"""
    rule_info = [f"{rule.rule_type}: {rule.parameter}" for rule in config.rules]

    current_app.logger.info(
        f"Configuration '{config.name}' (ID: {config.id}) {operation}"
    )
    current_app.logger.info(f"  - Created: {config.created_at}")
    current_app.logger.info(f"  - Last used: {config.last_used}")
    current_app.logger.info(
        f"  - Rules: {', '.join(rule_info) if rule_info else 'None'}"
    )

    return rule_info


def log_playlist_summary(tracks, playlist_name, config=None):
    """Log detailed information about the final playlist created"""
    if not tracks:
        current_app.logger.warning(f"Created empty playlist '{playlist_name}'")
        return

    # Calculate basic stats
    total_duration_ms = sum(track.get("duration_ms", 0) for track in tracks)
    total_duration_min = total_duration_ms / 60000

    # Count unique artists
    artists = {}
    for track in tracks:
        artist_id = track.get("artist_id")
        artist_name = track.get("artist", "Unknown")
        if artist_id:
            if artist_id in artists:
                artists[artist_id]["count"] += 1
            else:
                artists[artist_id] = {"name": artist_name, "count": 1}

    # Count tracks by year if available
    years = {}
    for track in tracks:
        release_date = None
        if "album" in track and "release_date" in track["album"]:
            release_date = track["album"]["release_date"]
        elif "release_date" in track:
            release_date = track["release_date"]

        if release_date and "-" in release_date:
            year = release_date.split("-")[0]
            years[year] = years.get(year, 0) + 1

    # Count explicit tracks
    explicit_count = sum(1 for track in tracks if track.get("explicit", False))

    # Log the summary
    current_app.logger.info(
        f"Created playlist '{playlist_name}' with {len(tracks)} tracks"
    )
    current_app.logger.info(
        f"  - Configuration: {config.name if config else 'Ad-hoc shuffle'}"
    )
    current_app.logger.info(f"  - Total duration: {total_duration_min:.2f} minutes")
    current_app.logger.info(f"  - Unique artists: {len(artists)}")

    # Top artists (up to 5)
    top_artists = sorted(artists.values(), key=lambda x: x["count"], reverse=True)[:5]
    if top_artists:
        current_app.logger.info("  - Top artists:")
        for artist in top_artists:
            current_app.logger.info(f"    * {artist['name']}: {artist['count']} tracks")

    # Release years summary if available
    if years:
        years_str = ", ".join(
            f"{year}: {count}" for year, count in sorted(years.items())
        )
        current_app.logger.info(f"  - Years distribution: {years_str}")

    # Explicit content
    if explicit_count > 0:
        current_app.logger.info(
            f"  - Explicit tracks: {explicit_count} ({(explicit_count / len(tracks)) * 100:.1f}%)"
        )

    # List all tracks in the playlist
    current_app.logger.debug("Playlist tracks:")
    for i, track in enumerate(tracks, 1):
        current_app.logger.debug(
            f"  {i}. {track.get('name', 'Unknown')} - {track.get('artist', 'Unknown')} ({track.get('duration_ms', 0) / 60000:.2f} min)"
        )

    # Return a summary dict for use in the playlist history
    return {
        "track_count": len(tracks),
        "duration_min": total_duration_min,
        "artist_count": len(artists),
        "explicit_count": explicit_count,
        "top_artists": [{"name": a["name"], "count": a["count"]} for a in top_artists],
        "years": years,
    }


def track_playlist_creation(
    playlist_id, playlist_name, track_uris, rule_categories, config, tracks
):
    """Record the playlist creation in history"""
    try:
        # Get details about the playlist for tracking
        total_duration_ms = sum(track.get("duration_ms", 0) for track in tracks)

        # Count unique artists
        artists = {}
        for track in tracks:
            artist_id = track.get("artist_id")
            if artist_id and artist_id not in artists:
                artists[artist_id] = True

        # Count explicit tracks
        explicit_count = sum(1 for track in tracks if track.get("explicit", False))

        # Track year range if available
        years = []
        for track in tracks:
            release_date = None
            if "album" in track and "release_date" in track["album"]:
                release_date = track["album"]["release_date"]
            elif "release_date" in track:
                release_date = track["release_date"]

            if release_date and "-" in release_date:
                year = int(release_date.split("-")[0])
                years.append(year)

        oldest_year = min(years) if years else None
        newest_year = max(years) if years else None

        # Convert rules to JSON string for storage
        rules_json = (
            json.dumps(rule_categories["all_rules"])
            if rule_categories and "all_rules" in rule_categories
            else None
        )

        # Create history record
        playlist_history = PlaylistCreationHistory(
            user_id=current_user.id,
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            track_count=len(track_uris),
            duration_ms=total_duration_ms,
            artist_count=len(artists),
            explicit_count=explicit_count,
            oldest_year=oldest_year,
            newest_year=newest_year,
            rules_used=rules_json,
            config_id=config.id if config else None,
        )

        db.session.add(playlist_history)
        db.session.commit()

        # Log extended creation info
        current_app.logger.info(
            f"Recorded playlist history for '{playlist_name}':"
            f"\n  - ID: {playlist_id}"
            f"\n  - Tracks: {len(track_uris)}"
            f"\n  - Duration: {playlist_history.get_duration_minutes():.2f} minutes"
            f"\n  - Artists: {len(artists)}"
            f"\n  - Explicit: {explicit_count} tracks"
            f"\n  - Years: {oldest_year or 'Unknown'} to {newest_year or 'Unknown'}"
        )

    except Exception as e:
        current_app.logger.error(
            f"Error tracking playlist creation: {str(e)}", exc_info=True
        )


def take_random_tracks(tracks, count):
    """Take a random subset of tracks"""
    if not tracks:
        return []

    tracks_copy = tracks.copy()
    random.shuffle(tracks_copy)
    return tracks_copy[: min(count, len(tracks_copy))]


def refill_tracks(original_tracks, filtered_tracks, max_tracks):
    """Refill tracks when filters have been too aggressive"""
    if not filtered_tracks and original_tracks:
        # If we've filtered out all tracks, take some random ones from the original set
        current_app.logger.warning(
            "Filters removed all tracks, selecting random tracks instead"
        )
        return take_random_tracks(original_tracks, max_tracks)
    elif len(filtered_tracks) < max_tracks:
        # If we have some tracks but not enough, add more random ones
        needed = max_tracks - len(filtered_tracks)
        current_app.logger.info(
            f"Adding {needed} random tracks to meet minimum requirements"
        )

        # Get pool of tracks not already in filtered_tracks
        filtered_uris = {track["uri"] for track in filtered_tracks}
        available_tracks = [t for t in original_tracks if t["uri"] not in filtered_uris]

        if available_tracks:
            additional_tracks = take_random_tracks(available_tracks, needed)
            filtered_tracks.extend(additional_tracks)

    return filtered_tracks


def refill_with_artist_limits(
    original_tracks, filtered_tracks, artist_rules, max_tracks
):
    """Refill tracks while respecting artist limits"""
    if len(filtered_tracks) >= max_tracks:
        return filtered_tracks[:max_tracks]

    artist_limit = int(artist_rules.get("artist_limit", 1))

    # Track current artist counts
    artist_counts = {}
    for track in filtered_tracks:
        artist_id = track.get("artist_id", "")
        artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

    # Get tracks we don't already have
    filtered_uris = {track["uri"] for track in filtered_tracks}
    available_tracks = [t for t in original_tracks if t["uri"] not in filtered_uris]
    random.shuffle(available_tracks)

    # Add tracks that don't violate artist limits
    for track in available_tracks:
        artist_id = track.get("artist_id", "")
        if artist_counts.get(artist_id, 0) < artist_limit:
            filtered_tracks.append(track)
            artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

            if len(filtered_tracks) >= max_tracks:
                break

    return filtered_tracks


def sync_playlist_history(user):
    """
    Sync playlist history with Spotify to identify deleted playlists.

    Args:
        user: The current user object

    Returns:
        tuple: (synced_count, deleted_count, error_message)
    """
    from app.spotify.utils import get_spotify_client

    spotify = get_spotify_client(user)
    if not spotify:
        return 0, 0, "Could not connect to Spotify. Please log in again."

    # Get the user's playlist history
    history_items = PlaylistCreationHistory.query.filter_by(user_id=user.id).all()

    if not history_items:
        return 0, 0, "No playlist history found."

    current_app.logger.info(f"Syncing {len(history_items)} playlist history items")

    # Collect all playlist IDs to check in batches
    playlist_ids = [item.playlist_id for item in history_items if item.playlist_id]

    # Track results
    deleted_count = 0
    synced_count = 0

    # Create a set of valid playlist IDs
    valid_playlists = set()

    try:
        # First approach: check user's playlists
        offset = 0
        limit = 50
        total = None

        while total is None or offset < total:
            playlists = spotify.current_user_playlists(limit=limit, offset=offset)

            if total is None:
                total = playlists["total"]

            # Add all current playlist IDs to our valid set
            for playlist in playlists["items"]:
                valid_playlists.add(playlist["id"])

            offset += limit

        # Second approach: directly check each playlist ID
        # This handles playlists the user can access but didn't create
        for playlist_id in playlist_ids:
            if playlist_id in valid_playlists:
                continue  # Already confirmed this exists

            try:
                # Try to fetch the playlist directly
                spotify.playlist(playlist_id, fields="id,name")
                valid_playlists.add(playlist_id)
            except Exception as e:
                if "not found" in str(e).lower() or "404" in str(e):
                    # Playlist doesn't exist or is inaccessible
                    pass
                else:
                    # Some other error occurred
                    current_app.logger.error(
                        f"Error checking playlist {playlist_id}: {str(e)}"
                    )

        # Update each history item
        for item in history_items:
            if not item.playlist_id:
                continue

            if item.playlist_id in valid_playlists:
                # Playlist exists and is accessible
                if item.is_deleted:
                    item.is_deleted = False
                    db.session.add(item)
                synced_count += 1
            else:
                # Playlist doesn't exist or is inaccessible
                if not item.is_deleted:
                    item.is_deleted = True
                    item.deleted_at = datetime.utcnow()
                    db.session.add(item)
                deleted_count += 1

        db.session.commit()
        current_app.logger.info(
            f"Playlist sync complete: {synced_count} active, {deleted_count} deleted"
        )

        return synced_count, deleted_count, None

    except Exception as e:
        current_app.logger.error(f"Error syncing playlists: {str(e)}", exc_info=True)
        db.session.rollback()
        return 0, 0, f"Error syncing playlists: {str(e)}"


def unlink_deleted_playlists(user, keep_history=True):
    """
    Unlink or remove deleted playlists from history.

    Args:
        user: The current user object
        keep_history: If True, keep history but mark as deleted; if False, remove entries

    Returns:
        tuple: (removed_count, error_message)
    """
    try:
        query = PlaylistCreationHistory.query.filter_by(
            user_id=user.id, is_deleted=True
        )

        count = query.count()

        if count == 0:
            return 0, None

        if not keep_history:
            # Permanently delete history entries
            for item in query.all():
                db.session.delete(item)

            db.session.commit()
            current_app.logger.info(
                f"Removed {count} deleted playlist entries from history"
            )
        else:
            # Keep history but update display names
            for item in query.all():
                if not item.display_name.startswith("[Deleted] "):
                    item.display_name = f"[Deleted] {item.playlist_name}"
                    db.session.add(item)

            db.session.commit()
            current_app.logger.info(
                f"Updated {count} deleted playlist entries in history"
            )

        return count, None

    except Exception as e:
        current_app.logger.error(f"Error unlinking playlists: {str(e)}", exc_info=True)
        db.session.rollback()
        return 0, f"Error unlinking playlists: {str(e)}"
