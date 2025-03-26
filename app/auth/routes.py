from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    session,
)
from flask_login import login_user, logout_user, current_user, login_required
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from app import db
from app.auth import bp
from app.models import User, BetaSignup
from app.auth.forms import BetaSignupForm


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
        cache_id = session.get('spotify_cache_id')
        if not cache_id:
            cache_id = secrets.token_urlsafe(8)
            session['spotify_cache_id'] = cache_id
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


@bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    # Add random state for security
    import secrets

    state = secrets.token_urlsafe(16)
    session["spotify_auth_state"] = state

    # Get a unique SpotifyOAuth instance for this login attempt
    sp_oauth = get_spotify_oauth()  # Uses the session-based cache path

    # Build authorization URL with additional parameters to force login
    auth_url = sp_oauth.get_authorize_url(state=state)
    auth_url += "&show_dialog=true"

    # Clear any existing Spotify session cookies
    response = redirect(auth_url)
    return response


@bp.route("/callback")
@bp.route("/login/callback")
def callback():
    # Verify state to prevent CSRF
    state = request.args.get("state")
    stored_state = session.get("spotify_auth_state")
    if state is None or state != stored_state:
        flash("Authentication error: State verification failed")
        return redirect(url_for("main.index"))

    # Log all request data for debugging
    current_app.logger.info(f"Callback received with args: {request.args}")

    # Handle error response from Spotify
    error = request.args.get("error")
    if error:
        current_app.logger.error(f"Spotify auth error: {error}")
        flash(f"Authentication error: {error}")
        return redirect(url_for("main.index"))

    # Get authorization code from Spotify
    code = request.args.get("code")
    if not code:
        current_app.logger.error("No code provided in callback")
        flash("Authentication failed. Please try again.")
        return redirect(url_for("main.index"))

    try:
        # Use the same cache path that was used for login
        sp_oauth = get_spotify_oauth()  # Gets the session-based cache path
        current_app.logger.info(
            f"Exchanging code for token with redirect_uri: {current_app.config['SPOTIFY_REDIRECT_URI']}"
        )

        # Exchange code for token
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        current_app.logger.info("Token obtained successfully")

        # Create Spotify client with the new token
        sp = spotipy.Spotify(auth=token_info["access_token"])

        # Get user info from Spotify
        spotify_user = sp.current_user()
        spotify_id = spotify_user["id"]
        current_app.logger.info(f"Authenticated Spotify user: {spotify_id}")
        current_app.logger.info(f"Spotify user email: {spotify_user.get('email')}")
        current_app.logger.info(
            f"Spotify user display name: {spotify_user.get('display_name')}"
        )

        # Check if user exists in database
        user = User.query.filter_by(spotify_id=spotify_id).first()

        if user:
            current_app.logger.info(
                f"Found existing user with ID {user.id} for Spotify ID {spotify_id}"
            )
        else:
            current_app.logger.info(f"Creating new user for Spotify ID {spotify_id}")
            # Create new user if not exists
            user = User(
                spotify_id=spotify_id,
                email=spotify_user.get("email"),
                display_name=spotify_user.get("display_name"),
            )

            # Get profile image if available
            if spotify_user.get("images") and len(spotify_user["images"]) > 0:
                user.profile_image = spotify_user["images"][0].get("url")

            db.session.add(user)
            # Commit immediately to get an ID assigned
            db.session.commit()

        # Update user info
        user.set_spotify_tokens(
            token_info["access_token"],
            token_info["refresh_token"],
            token_info["expires_in"],
        )
        user.last_login = datetime.utcnow()

        # Now that we have a user ID, create the user database
        current_app.logger.info(f"Creating user DB for user ID: {user.id}")
        user_db_path = user.create_user_db(current_app.config)
        current_app.logger.info(f"User DB path: {user_db_path}")

        # Once we have a user ID, update to a user-specific cache for future use
        if user.id:
            # Get a new OAuth with the user's ID-based cache
            user_sp_oauth = get_spotify_oauth(user.id)

            # Transfer the token to the user-specific cache
            user_sp_oauth.cache_handler.save_token_to_cache(token_info)

            # Clean up the temporary cache if we have one
            if "spotify_cache_id" in session:
                temp_cache = f".spotify_cache_temp_{session['spotify_cache_id']}"
                try:
                    import os

                    if os.path.exists(temp_cache):
                        os.remove(temp_cache)
                        current_app.logger.info(
                            f"Deleted temporary cache: {temp_cache}"
                        )
                except Exception as cache_error:
                    current_app.logger.error(
                        f"Error deleting temp cache: {str(cache_error)}"
                    )
                session.pop("spotify_cache_id")

        db.session.commit()

        # Store the Spotify ID in the session for verification
        session["spotify_user_id"] = spotify_id

        # Log in the user
        login_user(user)

        flash(f'Welcome, {user.display_name or "Spotify User"}!')
        return redirect(url_for("main.dashboard"))

    except Exception as e:
        current_app.logger.error(
            f"Spotify authentication error: {str(e)}", exc_info=True
        )
        flash(f"Error during authentication: {str(e)}")
        return redirect(url_for("main.index"))


@bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("main.index"))


@bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html", title="Profile")


@bp.route("/beta-signup", methods=["GET", "POST"])
def beta_signup():
    form = BetaSignupForm()

    if form.validate_on_submit():
        signup = BetaSignup(name=form.name.data, email=form.email.data)
        db.session.add(signup)
        db.session.commit()

        flash("Thank you for joining our beta! We'll be in touch soon.", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/beta_signup.html", title="Join the Beta", form=form)
