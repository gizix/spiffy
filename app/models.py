from datetime import datetime, timedelta
from flask_login import UserMixin
import json
import os
from app import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True)
    display_name = db.Column(db.String(100))
    profile_image = db.Column(db.String(200))

    spotify_token = db.Column(db.Text)
    spotify_token_expiry = db.Column(db.DateTime)
    spotify_refresh_token = db.Column(db.String(200))

    db_path = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    token_expires_at = db.Column(db.DateTime)

    def token_expired(self):
        if not self.spotify_token_expiry:
            return True

        # If spotify_token_expiry is a datetime object, convert to timestamp
        if isinstance(self.spotify_token_expiry, datetime):
            return datetime.utcnow() > self.spotify_token_expiry
        else:
            expiry_timestamp = self.spotify_token_expiry
            return datetime.utcnow().timestamp() > expiry_timestamp

    def set_spotify_tokens(self, access_token, refresh_token, expires_in):
        self.spotify_token = access_token
        self.spotify_refresh_token = refresh_token
        self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return datetime.utcnow() > self.token_expires_at

    def create_user_db(self, app_config):
        if not self.id:
            raise ValueError("User ID must be set before creating a user database")

        user_db_dir = app_config["USER_DB_PATH"]
        os.makedirs(user_db_dir, exist_ok=True)
        self.db_path = os.path.join(user_db_dir, f"user_{self.id}.db")

        # Log the database path
        print(f"Creating database for user {self.id} at {self.db_path}")

        # Create the database with a basic structure if it doesn't exist
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create a version table to track database schema
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS db_info (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
        )

        # Set a version
        cursor.execute(
            "INSERT OR REPLACE INTO db_info (key, value) VALUES (?, ?)",
            ("version", "1.0"),
        )

        conn.commit()
        conn.close()

        return self.db_path

    def __repr__(self):
        return f"<User {self.display_name or self.spotify_id}>"


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class SpotifyDataType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.String(200))
    endpoint = db.Column(db.String(100))
    required_scope = db.Column(db.String(100))

    def __repr__(self):
        return f"<SpotifyDataType {self.name}>"


class UserDataSync(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    data_type_id = db.Column(db.Integer, db.ForeignKey("spotify_data_type.id"))
    last_sync = db.Column(db.DateTime)
    record_count = db.Column(db.Integer, default=0)

    user = db.relationship("User", backref="data_syncs")
    data_type = db.relationship("SpotifyDataType")

    def __repr__(self):
        return f"<UserDataSync {self.user_id}:{self.data_type.name}>"


class RandomizerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, nullable=True)

    # Relationship to rules
    rules = db.relationship(
        "RandomizerRule", backref="config", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<RandomizerConfig {self.name}>"


class RandomizerRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(
        db.Integer, db.ForeignKey("randomizer_config.id"), nullable=False
    )
    rule_type = db.Column(
        db.String(64), nullable=False
    )  # e.g., 'artist_limit', 'playlist_length'
    parameter = db.Column(
        db.String(128), nullable=True
    )  # e.g., '2' for max 2 songs per artist

    def __repr__(self):
        return f"<RandomizerRule {self.rule_type}: {self.parameter}>"


# Establishing relationships between User and RandomizerConfig
User.randomizer_configs = db.relationship(
    "RandomizerConfig", backref="user", lazy="dynamic"
)


class PlaylistCreationHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    playlist_id = db.Column(db.String(100), nullable=False)
    playlist_name = db.Column(db.String(200), nullable=False)
    track_count = db.Column(db.Integer, default=0)
    duration_ms = db.Column(db.Integer, default=0)
    artist_count = db.Column(db.Integer, default=0)
    explicit_count = db.Column(db.Integer, default=0)
    oldest_year = db.Column(db.Integer, nullable=True)
    newest_year = db.Column(db.Integer, nullable=True)
    rules_used = db.Column(db.Text, nullable=True)
    config_id = db.Column(
        db.Integer, db.ForeignKey("randomizer_config.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    display_name = db.Column(db.String(255), nullable=True)

    # Relationship to user
    user = db.relationship("User", backref="playlist_history")
    # Optional relationship to config
    config = db.relationship("RandomizerConfig", backref="playlist_history")

    def get_duration_minutes(self):
        """Get playlist duration in minutes"""
        return round(self.duration_ms / 60000, 2) if self.duration_ms else 0

    def __repr__(self):
        return f"<PlaylistHistory '{self.playlist_name}'>"


class BetaSignup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BetaSignup {self.name} ({self.email})>"
