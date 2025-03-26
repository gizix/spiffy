# app/randomizer/routes.py
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from app import db
from app.models import RandomizerConfig, RandomizerRule
from app.randomizer import randomizer
from app.spotify.utils import get_spotify_client
import random
from datetime import datetime

from app.models import UserDataSync, SpotifyDataType, PlaylistCreationHistory
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Import helpers and rule processor functions
from app.randomizer.helpers import (
    extract_rules_from_form,
    save_configuration,
    get_tracks_from_source,
    log_config_details,
    log_playlist_summary,
    track_playlist_creation,
    sync_playlist_history,
)

from app.randomizer.rule_processor import (
    categorize_rules,
    process_tracks_with_rules,
    validate_final_playlist,
)

MAX_PLAYLIST_TRACKS = 100


@randomizer.route("/randomizer", methods=["GET"])
@login_required
def index():
    try:
        current_app.logger.info("Starting randomizer index route")

        configs = RandomizerConfig.query.filter_by(user_id=current_user.id).all()
        current_app.logger.info(f"Found {len(configs)} configs")

        # Check if saved tracks are synced
        data_type_obj = SpotifyDataType.query.filter_by(name="saved_tracks").first()
        saved_tracks_synced = False

        if data_type_obj:
            sync = UserDataSync.query.filter_by(
                user_id=current_user.id, data_type_id=data_type_obj.id
            ).first()
            saved_tracks_synced = sync is not None and sync.last_sync is not None

        # Get playlist creation history, most recent first
        current_app.logger.info("Querying playlist history")
        playlist_history = []
        try:
            from app.models import PlaylistCreationHistory

            playlist_history = (
                PlaylistCreationHistory.query.filter_by(user_id=current_user.id)
                .order_by(PlaylistCreationHistory.created_at.desc())
                .limit(10)
                .all()
            )
            current_app.logger.info(f"Found {len(playlist_history)} history items")
        except Exception as e:
            current_app.logger.error(
                f"Error querying playlist history: {str(e)}", exc_info=True
            )
            playlist_history = []

        return render_template(
            "randomizer/index.html",
            title="Playlist Randomizer",
            configs=configs,
            saved_tracks_synced=saved_tracks_synced,
            max_playlist_tracks=MAX_PLAYLIST_TRACKS,
            playlist_history=playlist_history,
        )
    except Exception as e:
        current_app.logger.error(
            f"Error in randomizer index route: {str(e)}", exc_info=True
        )
        # Return a simple error page instead of blank screen
        return f"<h1>Error loading page</h1><p>{str(e)}</p><p><a href='/'>Return to home</a></p>"


@randomizer.route("/create_playlist", methods=["POST"])
@login_required
def create_playlist():
    # Start timing the operation
    start_time = datetime.utcnow()

    # Get source information
    source_type = request.form.get("source_type", "playlist")
    source_playlist_id = request.form.get("source_playlist_id")
    current_app.logger.info(
        f"Starting playlist creation request - source type: {source_type}"
    )

    # Validate source selection
    if source_type == "playlist" and not source_playlist_id:
        flash("Please select a source playlist")
        return redirect(url_for("randomizer.index"))

    # Get playlist name
    playlist_name = (
        request.form.get("playlist_name")
        or f"Shuffled Playlist {random.randint(1000, 9999)}"
    )

    # Extract rules from form
    rules = extract_rules_from_form(request)
    current_app.logger.info(f"Processing {len(rules)} rules for playlist creation")

    # Save configuration if requested
    save_config = request.form.get("save_config") == "on"
    config_name = request.form.get("config_name", "")
    config = None

    if save_config and config_name:
        config = save_configuration(rules, config_name, current_user.id)

    try:
        # Get tracks from source
        tracks, error_message = get_tracks_from_source(
            source_type, source_playlist_id, current_user
        )

        if error_message:
            flash(error_message)
            return redirect(url_for("randomizer.index"))

        # Categorize rules for processing
        if not rules and config:
            # Get rules from config if no rules provided directly
            config = RandomizerConfig.query.get(config.id)
            config_rules = [
                {"rule_type": rule.rule_type, "parameter": rule.parameter}
                for rule in config.rules
            ]
            current_app.logger.info(
                f"Using {len(config_rules)} rules from config '{config.name}'"
            )
            rules = config_rules

        # Categorize rules by type and order
        rule_categories = categorize_rules(rules)

        # Process tracks with rules
        filtered_tracks = process_tracks_with_rules(
            tracks, rule_categories, max_tracks=MAX_PLAYLIST_TRACKS
        )

        # Final validation and limiting
        shuffled_tracks = validate_final_playlist(
            filtered_tracks, rule_categories, MAX_PLAYLIST_TRACKS
        )

        # Log a summary of the final playlist
        log_playlist_summary(shuffled_tracks, playlist_name, config)

        # Get a fresh Spotify client with the correct scopes
        sp_oauth = SpotifyOAuth(
            client_id=current_app.config["SPOTIFY_CLIENT_ID"],
            client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
            redirect_uri=current_app.config["SPOTIFY_REDIRECT_URI"],
            scope=current_app.config["SPOTIFY_API_SCOPES"],
            cache_path=None,
            show_dialog=True,
        )

        if current_user.spotify_refresh_token:
            token_info = sp_oauth.refresh_access_token(
                current_user.spotify_refresh_token
            )
            current_user.set_spotify_tokens(
                token_info["access_token"],
                token_info.get("refresh_token", current_user.spotify_refresh_token),
                token_info["expires_in"],
            )
            db.session.commit()

            spotify = spotipy.Spotify(auth=token_info["access_token"])
        else:
            flash("Could not refresh your Spotify token. Please log in again.")
            return redirect(url_for("auth.login"))

        try:
            # Create a new playlist
            user_id = spotify.me()["id"]
            current_app.logger.info(
                f"Creating playlist '{playlist_name}' for user: {user_id}"
            )

            new_playlist = spotify.user_playlist_create(
                user=user_id,
                name=playlist_name,
                public=False,
                description="Created with Spiffy Randomizer"
                + (f' using "{config.name}" configuration' if config else ""),
            )

            # Add tracks to the new playlist
            track_uris = [track["uri"] for track in shuffled_tracks]

            # Check if we have tracks to add
            if not track_uris:
                current_app.logger.error("No tracks available to add to playlist")
                flash("Could not create playlist: no tracks matched your criteria")
                return redirect(url_for("randomizer.index"))

            # Add tracks in one request
            spotify.playlist_add_items(new_playlist["id"], track_uris)

            # Track playlist creation
            track_playlist_creation(
                new_playlist["id"],
                playlist_name,
                track_uris,
                rule_categories,
                config,
                shuffled_tracks,
            )

            # Calculate total operation time
            end_time = datetime.utcnow()
            operation_time = (end_time - start_time).total_seconds()
            current_app.logger.info(
                f"Playlist creation completed in {operation_time:.2f} seconds"
            )

            flash(
                f'Playlist "{playlist_name}" created successfully with {len(track_uris)} tracks'
            )
            return redirect(url_for("randomizer.index"))

        except Exception as e:
            current_app.logger.error(
                f"Error creating playlist: {str(e)}", exc_info=True
            )

            if "insufficient client scope" in str(e).lower():
                flash(
                    "Your account needs to be reconnected with additional permissions. Please disconnect and reconnect your Spotify account."
                )

                # Force a disconnect
                current_user.spotify_token = None
                current_user.spotify_refresh_token = None
                current_user.spotify_token_expiry = None
                current_user.token_expires_at = None
                db.session.commit()

                return redirect(url_for("spotify.connect"))
            else:
                flash(f"Error creating playlist: {str(e)}")
                return redirect(url_for("randomizer.index"))

    except Exception as e:
        current_app.logger.error(f"Error creating playlist: {str(e)}", exc_info=True)
        flash(f"Error creating playlist: {str(e)}")
        return redirect(url_for("randomizer.index"))


@randomizer.route("/get_config_rules/<int:id>", methods=["GET"])
@login_required
def get_config_rules(id):
    config = RandomizerConfig.query.get_or_404(id)
    if config.user_id != current_user.id:
        current_app.logger.warning(
            f"Unauthorized access to config {id} by user {current_user.id}"
        )
        return jsonify({"error": "Unauthorized"}), 403

    rule_info = log_config_details(config, "loaded")

    rules = [
        {"rule_type": rule.rule_type, "parameter": rule.parameter}
        for rule in config.rules
    ]

    # Update the last_used timestamp
    config.last_used = datetime.utcnow()
    db.session.commit()

    current_app.logger.info(
        f"Returning {len(rules)} rules for configuration '{config.name}'"
    )
    return jsonify({"id": config.id, "name": config.name, "rules": rules})


@randomizer.route("/edit_config/<int:id>", methods=["GET", "POST"])
@login_required
def edit_config(id):
    config = RandomizerConfig.query.get_or_404(id)
    if config.user_id != current_user.id:
        current_app.logger.warning(
            f"Unauthorized edit attempt of config {id} by user {current_user.id}"
        )
        flash("You cannot edit this configuration")
        return redirect(url_for("randomizer.index"))

    if request.method == "POST":
        old_name = config.name
        old_rules = log_config_details(config, "before edit")

        config.name = request.form.get("config_name", config.name)

        # Clear existing rules
        for rule in config.rules.all():
            db.session.delete(rule)

        # Process new rules
        new_rules = []
        for key in request.form.keys():
            if key.startswith("rules[") and key.endswith("[rule_type]"):
                # Extract the index from the key
                index = key[6:-11]
                rule_type = request.form.get(f"rules[{index}][rule_type]")
                parameter = request.form.get(f"rules[{index}][parameter]")

                if rule_type and parameter:
                    new_rules.append(f"{rule_type}: {parameter}")
                    rule = RandomizerRule(
                        config_id=config.id, rule_type=rule_type, parameter=parameter
                    )
                    db.session.add(rule)

        # Log the changes
        current_app.logger.info(
            f"Configuration '{old_name}' updated to '{config.name}'"
        )
        current_app.logger.info(
            f"  - Old rules: {', '.join(old_rules) if old_rules else 'None'}"
        )
        current_app.logger.info(
            f"  - New rules: {', '.join(new_rules) if new_rules else 'None'}"
        )

        db.session.commit()
        flash("Configuration updated successfully")
        return redirect(url_for("randomizer.index"))

    # GET request - render edit form
    current_app.logger.info(f"Editing configuration '{config.name}' (ID: {config.id})")
    rules = [
        {"rule_type": rule.rule_type, "parameter": rule.parameter}
        for rule in config.rules
    ]
    return render_template(
        "randomizer/edit_config.html",
        config=config,
        rules=rules,
        title="Edit Configuration",
    )


@randomizer.route("/delete_config/<int:id>", methods=["POST"])
@login_required
def delete_config(id):
    config = RandomizerConfig.query.get_or_404(id)
    if config.user_id != current_user.id:
        flash("You cannot delete this configuration")
        return redirect(url_for("randomizer.index"))

    db.session.delete(config)
    db.session.commit()
    flash("Configuration deleted successfully")
    return redirect(url_for("randomizer.index"))


@randomizer.route("/sync_playlists", methods=["GET", "POST"])
@login_required
def sync_playlists():
    """Sync playlist history with Spotify to identify deleted playlists"""
    if request.method == "POST":
        action = request.form.get("action", "sync")

        if action == "sync":
            # Run the sync operation
            synced_count, deleted_count, error = sync_playlist_history(current_user)

            if error:
                flash(error, "error")
            else:
                flash(
                    f"Playlist sync complete: {synced_count} active, {deleted_count} deleted"
                )

        elif action == "unlink":
            # Unlink or remove deleted playlists
            keep_history = request.form.get("keep_history", "true") == "true"
            removed_count, error = unlink_deleted_playlists(current_user, keep_history)

            if error:
                flash(error, "error")
            else:
                if keep_history:
                    flash(f"Updated {removed_count} deleted playlist entries")
                else:
                    flash(f"Removed {removed_count} deleted playlist entries")

    # Get statistics for the template
    deleted_count = PlaylistCreationHistory.query.filter_by(
        user_id=current_user.id, is_deleted=True
    ).count()

    total_count = PlaylistCreationHistory.query.filter_by(
        user_id=current_user.id
    ).count()

    active_count = total_count - deleted_count

    return render_template(
        "randomizer/sync_playlists.html",
        title="Manage Playlist History",
        active_count=active_count,
        deleted_count=deleted_count,
        total_count=total_count,
    )


@randomizer.route("/debug_playlist", methods=["POST"])
@login_required
def debug_playlist():
    # Start timing the operation
    start_time = datetime.utcnow()

    # Log the start of debug mode
    current_app.logger.info("===== STARTING DEBUG MODE =====")

    # Get source information
    source_type = request.form.get("source_type", "playlist")
    source_playlist_id = request.form.get("source_playlist_id")
    current_app.logger.info(f"Source type: {source_type}")

    # Validate source selection
    if source_type == "playlist" and not source_playlist_id:
        flash("Please select a source playlist")
        return redirect(url_for("randomizer.index"))

    # Get playlist name
    playlist_name = (
        request.form.get("playlist_name")
        or f"Shuffled Playlist {random.randint(1000, 9999)}"
    )
    current_app.logger.info(f"Debug playlist name: {playlist_name}")

    # Extract rules from form
    rules = extract_rules_from_form(request)
    current_app.logger.info(f"Processing {len(rules)} rules in debug mode")

    # Save configuration if requested
    save_config = request.form.get("save_config") == "on"
    config_name = request.form.get("config_name", "")
    config = None

    if save_config and config_name:
        current_app.logger.info(
            f"Debug mode: Configuration would be saved as '{config_name}'"
        )
        # Don't actually save in debug mode

    try:
        # Get tracks from source
        current_app.logger.info("Fetching source tracks...")
        tracks, error_message = get_tracks_from_source(
            source_type, source_playlist_id, current_user
        )

        if error_message:
            flash(error_message)
            return redirect(url_for("randomizer.index"))

        current_app.logger.info(f"Successfully retrieved {len(tracks)} source tracks")

        # Categorize rules for processing
        if not rules and config:
            # Get rules from config if no rules provided directly
            config = RandomizerConfig.query.get(config.id)
            config_rules = [
                {"rule_type": rule.rule_type, "parameter": rule.parameter}
                for rule in config.rules
            ]
            current_app.logger.info(
                f"Using {len(config_rules)} rules from config '{config.name}'"
            )
            rules = config_rules

        # Categorize rules by type and order
        rule_categories = categorize_rules(rules)

        # Log rule categories
        current_app.logger.info("Rule categorization:")
        for category, rules_dict in rule_categories.items():
            if isinstance(rules_dict, dict):
                current_app.logger.info(f"  - {category}: {rules_dict}")
            else:
                current_app.logger.info(f"  - {category}: {rules_dict}")

        # Process tracks with rules
        current_app.logger.info(f"Beginning rule processing on {len(tracks)} tracks")
        filtered_tracks = process_tracks_with_rules(
            tracks, rule_categories, max_tracks=MAX_PLAYLIST_TRACKS
        )

        # Final validation and limiting
        shuffled_tracks = validate_final_playlist(
            filtered_tracks, rule_categories, MAX_PLAYLIST_TRACKS
        )

        # Log a summary of the final playlist
        summary = log_playlist_summary(shuffled_tracks, playlist_name, config)

        # Calculate total operation time
        end_time = datetime.utcnow()
        operation_time = (end_time - start_time).total_seconds()

        # Create a debug summary to display to the user
        track_uris = [track["uri"] for track in shuffled_tracks]
        debug_summary = {
            "operation_time": operation_time,
            "source_type": source_type,
            "source_tracks_count": len(tracks),
            "final_tracks_count": len(shuffled_tracks),
            "rules_applied": rules,
            "playlist_summary": summary,
        }

        # Generate an HTML output of the summary
        from flask import render_template_string

        summary_html = render_template_string(
            """
            <div class="debug-summary">
                <h4>Debug Summary</h4>
                <p><strong>Operation Time:</strong> {{ debug_summary.operation_time|round(2) }} seconds</p>
                <p><strong>Source:</strong> {{ debug_summary.source_type }}</p>
                <p><strong>Source Tracks:</strong> {{ debug_summary.source_tracks_count }}</p>
                <p><strong>Final Tracks:</strong> {{ debug_summary.final_tracks_count }}</p>

                <h5>Rules Applied</h5>
                <ul>
                {% for rule in debug_summary.rules_applied %}
                    <li><strong>{{ rule.rule_type }}:</strong> {{ rule.parameter }}</li>
                {% endfor %}
                </ul>

                <h5>Playlist Summary</h5>
                <p><strong>Tracks:</strong> {{ debug_summary.playlist_summary.track_count }}</p>
                <p><strong>Duration:</strong> {{ debug_summary.playlist_summary.duration_min|round(2) }} minutes</p>
                <p><strong>Artists:</strong> {{ debug_summary.playlist_summary.artist_count }}</p>

                {% if debug_summary.playlist_summary.top_artists %}
                <h6>Top Artists</h6>
                <ul>
                {% for artist in debug_summary.playlist_summary.top_artists %}
                    <li>{{ artist.name }}: {{ artist.count }} tracks</li>
                {% endfor %}
                </ul>
                {% endif %}
            </div>
        """,
            debug_summary=debug_summary,
        )

        current_app.logger.info("===== DEBUG MODE COMPLETE =====")

        return render_template(
            "randomizer/debug_result.html",
            title="Randomizer Debug Result",
            debug_summary=debug_summary,
            summary_html=summary_html,
            operation_time=operation_time,
        )

    except Exception as e:
        current_app.logger.error(f"Error in debug mode: {str(e)}", exc_info=True)
        flash(f"Error in debug mode: {str(e)}")
        return redirect(url_for("randomizer.index"))
