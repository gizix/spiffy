# app/randomizer/rule_processor.py
import random
import json
from flask import current_app
from app.randomizer.helpers import refill_tracks, refill_with_artist_limits


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
    """Filter tracks based on explicit flag with improved error handling"""
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

    # More detailed diagnostic with track inspection
    if not hasattr(apply_explicit_filter, "has_diagnosed_deeply"):
        apply_explicit_filter.has_diagnosed_deeply = True
        track_sample = tracks[0] if tracks else {}
        current_app.logger.info(f"Full track data structure example:")
        current_app.logger.info(f"{json.dumps(track_sample, indent=2)}")
        # Look for any field containing 'explicit'
        for key, value in flatten_dict(track_sample).items():
            if "explicit" in key.lower():
                current_app.logger.info(
                    f"Found possible explicit field: {key} = {value}"
                )

    filtered_tracks = []
    excluded_count = 0
    missing_explicit_info = 0
    explicit_tracks_found = 0

    for track in tracks:
        # Check different possible locations for explicit info
        is_explicit = None

        # Try direct field
        if "explicit" in track:
            is_explicit = track["explicit"]

        # Try in external_ids
        elif "external_ids" in track and isinstance(track["external_ids"], dict):
            ext_ids = track["external_ids"]
            if "isrc" in ext_ids and "explicit" in ext_ids:
                is_explicit = ext_ids["explicit"]

        # Try in album
        elif "album" in track and isinstance(track["album"], dict):
            if "explicit" in track["album"]:
                is_explicit = track["album"]["explicit"]

        # Try in the raw data if available
        elif "data" in track and isinstance(track["data"], str):
            try:
                data = json.loads(track["data"])
                if "explicit" in data:
                    is_explicit = data["explicit"]
            except:
                pass

        # If still missing, look for it as a field called "is_explicit"
        elif "is_explicit" in track:
            is_explicit = track["is_explicit"]

        # Still not found - check track name for explicit markers as last resort
        if is_explicit is None:
            track_name = track.get("name", "").lower()
            if " (explicit)" in track_name or "[explicit]" in track_name:
                is_explicit = True

        # Count explicit tracks we find for logging
        if is_explicit is True:
            explicit_tracks_found += 1

        # If still missing, default conservatively based on filter type
        if is_explicit is None:
            missing_explicit_info += 1
            # For explicit_only, we skip tracks with unknown status (assume clean)
            # For clean_only, we include tracks with unknown status (assume clean)
            is_explicit = False

        if (include_explicit and is_explicit) or (exclude_explicit and not is_explicit):
            filtered_tracks.append(track)
        else:
            excluded_count += 1

    current_app.logger.info(f"Excluded {excluded_count} tracks due to explicit filter")
    current_app.logger.info(
        f"Tracks with missing explicit info: {missing_explicit_info}"
    )
    current_app.logger.info(f"Explicit tracks found: {explicit_tracks_found}")

    # Fallback logic for explicit_only filter when we can't find any explicit tracks
    if include_explicit and explicit_tracks_found == 0 and len(tracks) > 0:
        current_app.logger.warning(
            f"No explicit tracks found in the dataset - this suggests a data problem"
        )

        # For explicit_only, look for tracks with explicit terms in the title
        profanity_filtered_tracks = []
        profanity_terms = ["fuck", "shit", "bitch", "ass", "damn", "hell", "dick"]

        for track in tracks:
            name = track.get("name", "").lower()
            if any(term in name for term in profanity_terms):
                profanity_filtered_tracks.append(track)

        current_app.logger.info(
            f"Found {len(profanity_filtered_tracks)} tracks with potentially explicit titles"
        )

        if len(profanity_filtered_tracks) > 0:
            return profanity_filtered_tracks[: min(100, len(profanity_filtered_tracks))]

        # If that still yields nothing, return random tracks but note it's problematic
        current_app.logger.warning(
            f"Falling back to random tracks since no explicit tracks could be found"
        )
        random_sample = random.sample(tracks, min(100, len(tracks)))
        return random_sample

    # If we filtered all tracks with a clean_only filter, that's not necessarily a problem
    if len(filtered_tracks) == 0 and exclude_explicit and explicit_tracks_found > 0:
        current_app.logger.info(
            f"All tracks were filtered out because all tracks appear to be explicit"
        )

    return filtered_tracks


# Helper function to flatten nested dictionaries for inspection
def flatten_dict(d, parent_key="", sep="."):
    items = []
    for k, v in d.items() if isinstance(d, dict) else []:
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


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


def take_random_tracks(tracks, count):
    """Take a random subset of tracks"""
    if not tracks:
        return []

    tracks_copy = tracks.copy()
    random.shuffle(tracks_copy)
    return tracks_copy[: min(count, len(tracks_copy))]


def generate_rule_debug_report(original_tracks, filtered_tracks, rule_categories):
    """Generate a detailed report of how each rule affected the track selection"""
    report = {
        "original_count": len(original_tracks),
        "final_count": len(filtered_tracks),
        "rule_effects": [],
        "ignored_tracks": [],
        "artist_distribution": {},
    }

    # Make a copy of tracks to work with
    remaining_tracks = original_tracks.copy()

    # Process each rule type and track its effect
    for rule_type, rule_param in rule_categories["all_rules"].items():
        tracks_before = len(remaining_tracks)

        # Apply this specific rule
        if rule_type == "artist_limit":
            remaining_tracks = apply_artist_limit(
                remaining_tracks, {rule_type: rule_param}
            )
        elif rule_type in ["min_duration", "max_duration"]:
            remaining_tracks = apply_duration_rules(
                remaining_tracks, {rule_type: rule_param}
            )
        elif rule_type == "explicit_filter":
            remaining_tracks = apply_explicit_filter(
                remaining_tracks, {rule_type: rule_param}
            )
        elif rule_type in ["min_year", "max_year"]:
            remaining_tracks = apply_release_year_filter(
                remaining_tracks, {rule_type: rule_param}
            )
        elif rule_type in ["min_popularity", "max_popularity"]:
            remaining_tracks = apply_popularity_filter(
                remaining_tracks, {rule_type: rule_param}
            )
        elif rule_type == "saved_within":
            remaining_tracks = apply_saved_date_filter(
                remaining_tracks, {rule_type: rule_param}
            )

        tracks_after = len(remaining_tracks)

        # Record the effect
        report["rule_effects"].append(
            {
                "rule_type": rule_type,
                "parameter": rule_param,
                "tracks_before": tracks_before,
                "tracks_after": tracks_after,
                "tracks_removed": tracks_before - tracks_after,
                "percent_removed": (
                    round((tracks_before - tracks_after) / tracks_before * 100, 2)
                    if tracks_before > 0
                    else 0
                ),
            }
        )

    # Get tracks that were in original but not in final
    final_uris = {track["uri"] for track in filtered_tracks}
    ignored_tracks = [t for t in original_tracks if t["uri"] not in final_uris]

    # Sample some ignored tracks for the report
    sample_size = min(10, len(ignored_tracks))
    if sample_size > 0:
        for track in random.sample(ignored_tracks, sample_size):
            report["ignored_tracks"].append(
                {
                    "name": track.get("name", "Unknown"),
                    "artist": track.get("artist", "Unknown"),
                    "duration_ms": track.get("duration_ms", 0),
                    "popularity": track.get("popularity", 0),
                }
            )

    # Calculate artist distribution in final tracks
    for track in filtered_tracks:
        artist = track.get("artist", "Unknown")
        if artist in report["artist_distribution"]:
            report["artist_distribution"][artist] += 1
        else:
            report["artist_distribution"][artist] = 1

    return report


def diagnose_explicit_content(tracks, sample_size=5):
    """Diagnostic function to check explicit field in tracks"""
    current_app.logger.info(f"DIAGNOSING EXPLICIT CONTENT ISSUE")

    # Count how many tracks have the explicit field
    tracks_with_explicit = sum(1 for track in tracks if "explicit" in track)
    current_app.logger.info(
        f"Tracks with explicit field: {tracks_with_explicit}/{len(tracks)} ({tracks_with_explicit / len(tracks) * 100:.2f}%)"
    )

    # Sample some tracks to see their structure
    sample = tracks[:sample_size]
    for i, track in enumerate(sample):
        current_app.logger.info(f"Sample track {i + 1}:")
        current_app.logger.info(f"  - Track name: {track.get('name', 'Unknown')}")
        current_app.logger.info(f"  - Artist: {track.get('artist', 'Unknown')}")
        current_app.logger.info(f"  - Has explicit field: {'explicit' in track}")
        current_app.logger.info(
            f"  - Explicit value: {track.get('explicit', 'MISSING')}"
        )

        # Look for alternative fields that might contain explicit info
        for key in track:
            if "explicit" in key.lower():
                current_app.logger.info(f"  - Related field: {key} = {track[key]}")
