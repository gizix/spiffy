import os
import csv
import pandas as pd
from flask import current_app
import logging
import time


class TrackFeaturesManager:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(TrackFeaturesManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, csv_path=None):
        if self._initialized:
            return

        self.logger = logging.getLogger(__name__)
        self.csv_path = csv_path
        self._df = None
        self._indexed = False
        self._index = {}
        self._id_cache = {}

        if csv_path and os.path.exists(csv_path):
            self.load_csv(csv_path)

        self._initialized = True

    def load_csv(self, csv_path=None):
        if csv_path:
            self.csv_path = csv_path

        if not self.csv_path or not os.path.exists(self.csv_path):
            self.logger.error(f"CSV file not found: {self.csv_path}")
            return False

        try:
            start_time = time.time()
            self.logger.info(f"Loading track features from CSV: {self.csv_path}")

            # Read CSV in chunks to handle large files efficiently
            self._df = pd.read_csv(
                self.csv_path,
                dtype={
                    "id": str,
                    "name": str,
                    "album": str,
                    "album_id": str,
                    "artists": str,
                    "artist_ids": str,
                },
            )

            self.logger.info(
                f"Loaded {len(self._df)} tracks in {time.time() - start_time:.2f} seconds"
            )

            # Create indices for faster lookups
            self._create_indices()
            return True
        except Exception as e:
            self.logger.error(f"Failed to load CSV: {str(e)}")
            return False

    def _create_indices(self):
        if self._df is None:
            return

        start_time = time.time()
        self.logger.info("Creating track feature indices...")

        # Create primary index by track ID
        self._index = {}
        self._id_cache = set(self._df["id"].values)
        self._indexed = True

        self.logger.info(f"Created indices in {time.time() - start_time:.2f} seconds")

    def get_features_by_id(self, track_id):
        if self._df is None:
            return None

        if track_id not in self._id_cache:
            return None

        # Use pandas filtering for efficient lookup
        track = self._df[self._df["id"] == track_id]

        if len(track) == 0:
            return None

        # Convert row to dictionary and process special fields
        result = track.iloc[0].to_dict()

        # Process artists field - convert from string representation to clean format
        if "artists" in result and isinstance(result["artists"], str):
            # Handle string representations like "['Artist1', 'Artist2']"
            if result["artists"].startswith("[") and result["artists"].endswith("]"):
                try:
                    # Parse the string to get the actual list
                    artists_list = eval(result["artists"])
                    # Format as comma-separated string
                    result["artists"] = ", ".join(artists_list)
                except:
                    # If parsing fails, keep as is
                    pass

        # Add data source indicator
        result["data_source"] = "csv"

        return result

    def get_features_batch(self, track_ids):
        if self._df is None:
            return []

        # Filter existing IDs first to make the dataframe operation more efficient
        existing_ids = [
            track_id for track_id in track_ids if track_id in self._id_cache
        ]

        if not existing_ids:
            return []

        # Use isin for efficient batch filtering
        tracks = self._df[self._df["id"].isin(existing_ids)]

        # Convert to list of dictionaries and process special fields
        results = []
        for _, row in tracks.iterrows():
            result = row.to_dict()

            # Process artists field
            if "artists" in result and isinstance(result["artists"], str):
                if result["artists"].startswith("[") and result["artists"].endswith(
                    "]"
                ):
                    try:
                        artists_list = eval(result["artists"])
                        result["artists"] = ", ".join(artists_list)
                    except:
                        pass

            # Add data source indicator
            result["data_source"] = "csv"
            results.append(result)

        return results

    def search_tracks(self, name=None, artist=None, album=None, limit=10):
        if self._df is None:
            return []

        query = self._df

        if name:
            query = query[query["name"].str.contains(name, case=False, na=False)]

        if artist:
            query = query[query["artists"].str.contains(artist, case=False, na=False)]

        if album:
            query = query[query["album"].str.contains(album, case=False, na=False)]

        # Return limited results as list of dictionaries
        return [row.to_dict() for _, row in query.head(limit).iterrows()]

    def get_track_ids_in_csv(self):
        return list(self._id_cache) if self._df is not None else []


def get_track_features_manager(app=None):
    if app is None:
        from flask import current_app

        app = current_app

    csv_path = app.config.get("TRACK_FEATURES_CSV_PATH")

    manager = TrackFeaturesManager(csv_path)
    return manager
