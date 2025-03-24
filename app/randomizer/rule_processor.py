# app/randomizer/rule_processor.py
import random
from flask import current_app


def categorize_rules(rules):
    """Categorize rules by type and processing order"""
    # Convert rules list to dict if needed
    if isinstance(rules, list):
        rules_dict = {rule["rule_type"]: rule["parameter"] for rule in rules}
    elif hasattr(rules, "rules"):
        # It's a RandomizerConfig object
        rules_dict = {rule.rule_type: rule.parameter for rule in rules.rules.all()}
    else:
        # Assume it's already a dictionary
        rules_dict = rules

    # Categorize rules by type for processing order
    has_artist_limit = "artist_limit" in rules_dict
    has_duration_rule = "min_duration" in rules_dict or "max_duration" in rules_dict
    has_content_filter = any(
        rule in rules_dict
        for rule in [
            "explicit_filter",
            "min_year",
            "max_year",
            "min_popularity",
            "max_popularity",
            "saved_within",
        ]
    )

    # Create rule dictionaries by category
    content_rules = {
        k: v
        for k, v in rules_dict.items()
        if k
        in [
            "explicit_filter",
            "min_year",
            "max_year",
            "min_popularity",
            "max_popularity",
            "saved_within",
        ]
    }

    artist_rules = (
        {"artist_limit": rules_dict["artist_limit"]} if has_artist_limit else {}
    )

    duration_rules = {
        k: v for k, v in rules_dict.items() if k in ["min_duration", "max_duration"]
    }

    return {
        "all_rules": rules_dict,
        "content_rules": content_rules,
        "artist_rules": artist_rules,
        "duration_rules": duration_rules,
        "has_artist_limit": has_artist_limit,
        "has_duration_rule": has_duration_rule,
        "has_content_filter": has_content_filter,
    }


def process_tracks_with_rules(
    tracks, categorized_rules, chunk_size=1000, max_tracks=100
):
    """Process tracks with rules in the correct order with refill mechanism"""
    total_tracks = len(tracks)
    original_tracks = tracks.copy()  # Keep a copy of all original tracks for refilling
    current_app.logger.info(f"Processing {total_tracks} tracks with rules")

    # First pass: Apply content filters in chunks
    if categorized_rules["has_content_filter"]:
        current_app.logger.info(f"Applying content filters first")
        filtered_tracks = process_in_chunks(
            tracks, categorized_rules["content_rules"], chunk_size
        )
    else:
        filtered_tracks = tracks

    # If we've filtered out all tracks, relax content filters and try again
    if not filtered_tracks and tracks:
        current_app.logger.warning(
            f"Content filters removed all tracks, attempting refill"
        )
        filtered_tracks = refill_tracks(original_tracks, filtered_tracks, max_tracks)

    # Second pass: Apply artist limits to the filtered tracks
    if categorized_rules["has_artist_limit"]:
        current_app.logger.info(
            f"Applying artist limits to {len(filtered_tracks)} tracks"
        )
        filtered_tracks = apply_artist_limit(
            filtered_tracks, categorized_rules["artist_rules"]
        )

        # Check if we need to refill after artist limit filtering
        if len(filtered_tracks) < max_tracks and total_tracks > max_tracks:
            current_app.logger.info(f"Artist limits created gaps, attempting refill")
            filtered_tracks = refill_with_artist_limits(
                original_tracks,
                filtered_tracks,
                categorized_rules["artist_rules"],
                max_tracks,
            )

    # Third pass: Apply duration rules to the filtered tracks
    if categorized_rules["has_duration_rule"]:
        current_app.logger.info(
            f"Applying duration rules to {len(filtered_tracks)} tracks"
        )
        filtered_tracks = apply_duration_rules(
            filtered_tracks, categorized_rules["duration_rules"]
        )

    # Ensure we didn't filter too much - if needed, can add backup tracks that meet most rules
    if not filtered_tracks and total_tracks > 0:
        current_app.logger.warning(
            f"All tracks were filtered out. Relaxing constraints."
        )
        # Fallback logic - take the original tracks and apply minimal filtering
        filtered_tracks = take_random_tracks(original_tracks, max_tracks)

    # Final shuffle of filtered tracks
    random.shuffle(filtered_tracks)

    current_app.logger.info(
        f"After applying all rules: {len(filtered_tracks)} tracks remain"
    )
    return filtered_tracks


def process_in_chunks(tracks, rules_dict, chunk_size=1000):
    """Process tracks in chunks to handle large libraries"""
    total_tracks = len(tracks)

    if total_tracks <= chunk_size:
        # Small enough to process at once
        return apply_rules_to_tracks(tracks, rules_dict)

    # Process in chunks for large libraries
    filtered_tracks = []
    for i in range(0, total_tracks, chunk_size):
        chunk_end = min(i + chunk_size, total_tracks)
        current_chunk = tracks[i:chunk_end]

        current_app.logger.info(
            f"Processing chunk {i // chunk_size + 1}/{(total_tracks + chunk_size - 1) // chunk_size} ({len(current_chunk)} tracks)"
        )

        # Apply rules to this chunk
        chunk_result = apply_rules_to_tracks(current_chunk, rules_dict)
        filtered_tracks.extend(chunk_result)

    return filtered_tracks


def apply_rules_to_tracks(tracks, rules_dict):
    """Apply a set of rules to a batch of tracks"""
    # This is a simplified version of apply_randomizer_rules
    # Start with a random shuffle
    random.shuffle(tracks)

    # Apply each rule type in sequence
    for rule_type, rule_param in rules_dict.items():
        track_count_before = len(tracks)

        # Apply the specific rule
        if rule_type == "artist_limit":
            tracks = apply_artist_limit(tracks, {rule_type: rule_param})
        elif rule_type in ["min_duration", "max_duration"]:
            tracks = apply_duration_rules(tracks, {rule_type: rule_param})
        elif rule_type == "explicit_filter":
            tracks = apply_explicit_filter(tracks, {rule_type: rule_param})
        elif rule_type in ["min_year", "max_year"]:
            tracks = apply_release_year_filter(tracks, {rule_type: rule_param})
        elif rule_type in ["min_popularity", "max_popularity"]:
            tracks = apply_popularity_filter(tracks, {rule_type: rule_param})
        elif rule_type == "saved_within":
            tracks = apply_saved_date_filter(tracks, {rule_type: rule_param})

        # Log the effect of this rule
        track_count_after = len(tracks)
        if track_count_before != track_count_after:
            current_app.logger.info(
                f"{rule_type} changed track count: {track_count_before} → {track_count_after}"
            )

    return tracks


def validate_final_playlist(tracks, rule_categories, max_tracks):
    """Validate and ensure the final playlist meets all requirements"""
    result_tracks = tracks.copy()

    # Re-validate artist limits before final selection
    if rule_categories["has_artist_limit"] and len(result_tracks) > max_tracks:
        # Get the artist limit value
        artist_limit = int(rule_categories["artist_rules"].get("artist_limit", 1))

        # Check if we need to reapply the artist limit
        artist_counts = {}
        for track in result_tracks:
            artist_id = track.get("artist_id", "")
            artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

        max_artist_count = max(artist_counts.values()) if artist_counts else 0

        if max_artist_count > artist_limit:
            current_app.logger.info(
                f"Reapplying artist limit ({artist_limit}) to final track list"
            )
            result_tracks = apply_artist_limit(
                result_tracks, rule_categories["artist_rules"]
            )

    # Ensure minimum duration if needed
    if (
        rule_categories["has_duration_rule"]
        and "min_duration" in rule_categories["duration_rules"]
    ):
        min_duration = (
            int(rule_categories["duration_rules"].get("min_duration", 0)) * 60 * 1000
        )  # Convert to ms

        if min_duration > 0:
            # Calculate current duration
            current_duration = sum(
                track.get("duration_ms", 0) for track in result_tracks[:max_tracks]
            )

            if current_duration < min_duration:
                current_app.logger.info(
                    f"Final selection duration ({current_duration / 60000:.2f} min) is below minimum ({min_duration / 60000:.2f} min)"
                )

                # Sort remaining tracks by duration to efficiently meet the minimum
                remaining_tracks = (
                    result_tracks[max_tracks:]
                    if len(result_tracks) > max_tracks
                    else []
                )
                sorted_remaining = sorted(
                    remaining_tracks,
                    key=lambda x: x.get("duration_ms", 0),
                    reverse=True,
                )

                # Add tracks until we meet the minimum duration
                final_tracks = result_tracks[:max_tracks].copy()
                running_duration = current_duration

                # If we have artist limit rule, respect it while adding tracks
                if rule_categories["has_artist_limit"]:
                    artist_limit = int(
                        rule_categories["artist_rules"].get("artist_limit", 1)
                    )
                    artist_counts = {}

                    # Count artists in the current selection
                    for track in final_tracks:
                        artist_id = track.get("artist_id", "")
                        artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

                    # Add tracks respecting artist limits
                    for track in sorted_remaining:
                        artist_id = track.get("artist_id", "")
                        if artist_counts.get(artist_id, 0) < artist_limit:
                            final_tracks.append(track)
                            running_duration += track.get("duration_ms", 0)
                            artist_counts[artist_id] = (
                                artist_counts.get(artist_id, 0) + 1
                            )

                            if running_duration >= min_duration:
                                break
                else:
                    # No artist limit, just add tracks by duration
                    for track in sorted_remaining:
                        final_tracks.append(track)
                        running_duration += track.get("duration_ms", 0)

                        if running_duration >= min_duration:
                            break

                current_app.logger.info(
                    f"Adjusted selection to reach minimum duration: {running_duration / 60000:.2f} min with {len(final_tracks)} tracks"
                )
                return final_tracks

    # Limit to max tracks if needed
    if len(result_tracks) > max_tracks:
        current_app.logger.info(
            f"Limiting playlist to {max_tracks} tracks (from {len(result_tracks)})"
        )
        result_tracks = result_tracks[:max_tracks]

    return result_tracks


def apply_randomizer_rules(tracks, rules):
    """Apply rules to shuffled tracks

    Can accept either a list of rule dictionaries, a dict of rules, or a RandomizerConfig object
    """
    # Start with a random shuffle
    original_count = len(tracks)
    random.shuffle(tracks)
    current_app.logger.info(
        f"Starting rule application with {original_count} tracks after initial shuffle"
    )

    # Convert the rules to a dictionary if it's a config object or list
    if hasattr(rules, "rules"):
        # It's a RandomizerConfig object
        rules_dict = {rule.rule_type: rule.parameter for rule in rules.rules.all()}
        current_app.logger.info(f"Using RandomizerConfig with name: {rules.name}")
    elif isinstance(rules, list):
        # It's a list of rule dictionaries
        rules_dict = {rule["rule_type"]: rule["parameter"] for rule in rules}
    else:
        # Assume it's already a dictionary
        rules_dict = rules

    current_app.logger.info(f"Rules to apply: {rules_dict}")

    # Apply each rule type in sequence and track changes
    # The order matters - we typically want to apply content filters first,
    # then artist limits, and duration constraints last

    # Content filters
    track_count_before = len(tracks)
    tracks = apply_explicit_filter(tracks, rules_dict)
    track_count_after = len(tracks)
    if track_count_before != track_count_after:
        current_app.logger.info(
            f"Explicit filter changed track count: {track_count_before} → {track_count_after}"
        )

    track_count_before = len(tracks)
    tracks = apply_release_year_filter(tracks, rules_dict)
    track_count_after = len(tracks)
    if track_count_before != track_count_after:
        current_app.logger.info(
            f"Release year filter changed track count: {track_count_before} → {track_count_after}"
        )

    track_count_before = len(tracks)
    tracks = apply_popularity_filter(tracks, rules_dict)
    track_count_after = len(tracks)
    if track_count_before != track_count_after:
        current_app.logger.info(
            f"Popularity filter changed track count: {track_count_before} → {track_count_after}"
        )

    track_count_before = len(tracks)
    tracks = apply_saved_date_filter(tracks, rules_dict)
    track_count_after = len(tracks)
    if track_count_before != track_count_after:
        current_app.logger.info(
            f"Saved date filter changed track count: {track_count_before} → {track_count_after}"
        )

    # Artist diversity
    track_count_before = len(tracks)
    tracks = apply_artist_limit(tracks, rules_dict)
    track_count_after = len(tracks)
    if track_count_before != track_count_after:
        current_app.logger.info(
            f"Artist limit changed track count: {track_count_before} → {track_count_after}"
        )

    # Duration constraints (should be applied last)
    track_count_before = len(tracks)
    tracks = apply_duration_rules(tracks, rules_dict)
    track_count_after = len(tracks)
    if track_count_before != track_count_after:
        current_app.logger.info(
            f"Duration rules changed track count: {track_count_before} → {track_count_after}"
        )

    current_app.logger.info(
        f"Final track count after all rules: {len(tracks)} (removed {original_count - len(tracks)} tracks)"
    )

    return tracks


def apply_artist_limit(tracks, rules):
    """Apply artist limit rule with enhanced debugging"""
    artist_limit = int(rules.get("artist_limit", 0))
    if artist_limit > 0:
        current_app.logger.info(
            f"Applying artist limit: maximum {artist_limit} tracks per artist"
        )
        artists_count = {}
        filtered_tracks = []
        excluded_tracks = []
        artist_names = {}

        # First pass: count artists to log the initial distribution
        for track in tracks:
            artist_id = track["artist_id"]
            artist_name = track.get("artist", "Unknown")
            artist_names[artist_id] = artist_name
            artists_count[artist_id] = artists_count.get(artist_id, 0) + 1

        # Log the initial artist distribution for top artists
        top_artists_before = sorted(
            [(artist_id, count) for artist_id, count in artists_count.items()],
            key=lambda x: x[1],
            reverse=True,
        )[
            :10
        ]  # Top 10 artists

        current_app.logger.info("Initial artist distribution (before limiting):")
        for artist_id, count in top_artists_before:
            artist_name = artist_names.get(artist_id, "Unknown")
            current_app.logger.info(f"  - {artist_name}: {count} tracks")

        # Second pass: apply the limits
        artists_count = {}  # Reset for actual filtering
        for track in tracks:
            artist_id = track["artist_id"]
            artist_name = track.get("artist", "Unknown")
            current_count = artists_count.get(artist_id, 0)

            if current_count < artist_limit:
                filtered_tracks.append(track)
                artists_count[artist_id] = current_count + 1
            else:
                excluded_tracks.append(
                    {"title": track.get("name", "Unknown"), "artist": artist_name}
                )

        # Log what's actually getting excluded
        if excluded_tracks:
            current_app.logger.info(
                f"Excluded {len(excluded_tracks)} tracks due to artist limit:"
            )
            for i, track in enumerate(
                excluded_tracks[:20], 1
            ):  # Show max 20 excluded tracks
                current_app.logger.info(f"  {i}. {track['artist']} - {track['title']}")

            if len(excluded_tracks) > 20:
                current_app.logger.info(
                    f"  ... and {len(excluded_tracks) - 20} more tracks"
                )

        return filtered_tracks

    return tracks


def apply_duration_rules(tracks, rules):
    """Apply duration-based rules to tracks"""
    min_duration = int(rules.get("min_duration", 0)) * 60 * 1000  # Convert to ms
    max_duration = int(rules.get("max_duration", 0)) * 60 * 1000  # Convert to ms

    if min_duration > 0 or max_duration > 0:
        current_app.logger.info(
            f"Applying duration rules: min={min_duration / 60000}min, max={max_duration / 60000}min"
        )
        total_duration = 0
        filtered_tracks = []

        # Sort tracks by duration for more efficient playlist creation
        sorted_tracks = sorted(
            tracks, key=lambda x: x.get("duration_ms", 0), reverse=True
        )

        for track in sorted_tracks:
            track_duration = track.get("duration_ms", 0)
            new_total = total_duration + track_duration
            track_duration_min = track_duration / 60000

            # If we haven't reached min_duration yet, always add the track
            if min_duration > 0 and total_duration < min_duration:
                filtered_tracks.append(track)
                total_duration = new_total
                current_app.logger.debug(
                    f"Added track ({track.get('name', 'Unknown')}, {track_duration_min:.2f}min) to meet minimum duration"
                )

            # If we have a max_duration and would exceed it, stop adding tracks
            elif max_duration > 0 and new_total > max_duration:
                current_app.logger.info(
                    f"Reached maximum duration ({max_duration / 60000}min), stopping at {len(filtered_tracks)} tracks"
                )
                break

            # Otherwise, add the track
            else:
                filtered_tracks.append(track)
                total_duration = new_total

        current_app.logger.info(
            f"Final playlist duration: {total_duration / 60000:.2f} minutes ({len(filtered_tracks)} tracks)"
        )

        # For min_duration, if we didn't reach the target but used all tracks, that's OK
        if min_duration > 0 and total_duration < min_duration:
            current_app.logger.warning(
                f"Could not reach minimum duration of {min_duration / 60000}min (only reached {total_duration / 60000}min with all available tracks)"
            )

        return filtered_tracks

    return tracks


def apply_release_year_filter(tracks, rules):
    """Filter tracks based on release year constraints"""
    min_year = rules.get("min_year", "")
    max_year = rules.get("max_year", "")

    if not min_year and not max_year:
        return tracks

    try:
        min_year = int(min_year) if min_year else 0
        max_year = int(max_year) if max_year else 9999

        current_app.logger.info(
            f"Applying release year filter: {min_year} to {max_year}"
        )

        filtered_tracks = []
        excluded_count = 0

        for track in tracks:
            # Extract year from release_date if available
            release_date = None
            if "album" in track and "release_date" in track["album"]:
                release_date = track["album"]["release_date"]
            elif "release_date" in track:
                release_date = track["release_date"]

            if release_date:
                # Extract just the year from formats like YYYY-MM-DD
                year = int(release_date.split("-")[0])

                if min_year <= year <= max_year:
                    filtered_tracks.append(track)
                else:
                    excluded_count += 1
            else:
                # Include tracks with unknown release dates
                filtered_tracks.append(track)

        current_app.logger.info(
            f"Excluded {excluded_count} tracks due to release year filter"
        )
        return filtered_tracks
    except (ValueError, TypeError) as e:
        current_app.logger.error(f"Error applying release year filter: {str(e)}")
        return tracks


def apply_popularity_filter(tracks, rules):
    """Filter tracks based on their popularity score"""
    min_popularity = rules.get("min_popularity", "")
    max_popularity = rules.get("max_popularity", "")

    if not min_popularity and not max_popularity:
        return tracks

    try:
        min_popularity = int(min_popularity) if min_popularity else 0
        max_popularity = int(max_popularity) if max_popularity else 100

        current_app.logger.info(
            f"Applying popularity filter: {min_popularity} to {max_popularity}"
        )

        filtered_tracks = []
        excluded_count = 0

        for track in tracks:
            popularity = track.get("popularity", 0)

            if min_popularity <= popularity <= max_popularity:
                filtered_tracks.append(track)
            else:
                excluded_count += 1

        current_app.logger.info(
            f"Excluded {excluded_count} tracks due to popularity filter"
        )
        return filtered_tracks
    except (ValueError, TypeError) as e:
        current_app.logger.error(f"Error applying popularity filter: {str(e)}")
        return tracks


def apply_explicit_filter(tracks, rules):
    """Filter tracks based on explicit flag"""
    explicit_filter = rules.get("explicit_filter", "")

    if not explicit_filter or explicit_filter.lower() == "any":
        return tracks

    include_explicit = explicit_filter.lower() == "explicit_only"
    exclude_explicit = explicit_filter.lower() == "clean_only"

    if not include_explicit and not exclude_explicit:
        return tracks

    current_app.logger.info(
        f"Applying explicit filter: {'including only explicit' if include_explicit else 'excluding explicit'}"
    )

    filtered_tracks = []
    excluded_count = 0

    for track in tracks:
        is_explicit = track.get("explicit", False)

        if (include_explicit and is_explicit) or (exclude_explicit and not is_explicit):
            filtered_tracks.append(track)
        else:
            excluded_count += 1

    current_app.logger.info(f"Excluded {excluded_count} tracks due to explicit filter")
    return filtered_tracks


def apply_saved_date_filter(tracks, rules):
    """Filter tracks based on when they were saved"""
    from datetime import datetime, timedelta

    saved_within = rules.get("saved_within", "")

    if not saved_within:
        return tracks

    try:
        days = int(saved_within)
        if days <= 0:
            return tracks

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        current_app.logger.info(
            f"Applying saved date filter: last {days} days (since {cutoff_str})"
        )

        filtered_tracks = []
        excluded_count = 0

        for track in tracks:
            saved_at = track.get("saved_at")

            if saved_at and saved_at >= cutoff_str:
                filtered_tracks.append(track)
            else:
                excluded_count += 1

        current_app.logger.info(
            f"Excluded {excluded_count} tracks due to saved date filter"
        )
        return filtered_tracks
    except (ValueError, TypeError) as e:
        current_app.logger.error(f"Error applying saved date filter: {str(e)}")
        return tracks


# Helper functions from helpers.py needed for rule processing
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


def take_random_tracks(tracks, count):
    """Take a random subset of tracks"""
    if not tracks:
        return []

    tracks_copy = tracks.copy()
    random.shuffle(tracks_copy)
    return tracks_copy[: min(count, len(tracks_copy))]
