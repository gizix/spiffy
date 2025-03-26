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


def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=current_app.config["SPOTIFY_CLIENT_ID"],
        client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=current_app.config["SPOTIFY_REDIRECT_URI"],
        scope=current_app.config["SPOTIFY_API_SCOPES"],
        cache_path=None,
        requests_timeout=30,
    )


@bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    # Generate a unique state for this login session
    import secrets
    state = secrets.token_urlsafe(16)
    session['spotify_auth_state'] = state

    # Redirect to Spotify authorization with state parameter
    sp_oauth = SpotifyOAuth(
        client_id=current_app.config["SPOTIFY_CLIENT_ID"],
        client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=current_app.config["SPOTIFY_REDIRECT_URI"],
        scope="user-library-read user-top-read playlist-read-private user-read-recently-played user-read-email",
        cache_path=None,  # Don't use file-based caching
        show_dialog=True,  # Force user to select account
    )
    auth_url = sp_oauth.get_authorize_url(state=state)
    return redirect(auth_url)


@bp.route("/callback")
@bp.route("/login/callback")
def callback():
    # Verify state to prevent CSRF
    state = request.args.get('state')
    stored_state = session.get('spotify_auth_state')
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
        # Exchange code for token
        current_app.logger.info(
            f"Exchanging code for token with redirect_uri: {current_app.config['SPOTIFY_REDIRECT_URI']}"
        )
        sp_oauth = SpotifyOAuth(
            client_id=current_app.config["SPOTIFY_CLIENT_ID"],
            client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
            redirect_uri=current_app.config["SPOTIFY_REDIRECT_URI"],
            scope="user-library-read user-top-read playlist-read-private user-read-recently-played user-read-email",
            cache_path=None,
            show_dialog=True,
        )

        # Exchange code for token
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        current_app.logger.info("Token obtained successfully")

        # Create Spotify client with the new token
        sp = spotipy.Spotify(auth=token_info["access_token"])

        # Get user info from Spotify
        spotify_user = sp.current_user()
        current_app.logger.info(
            f"Authenticated as Spotify user: {spotify_user.get('id')}"
        )

        # Check if user exists in database
        user = User.query.filter_by(spotify_id=spotify_user["id"]).first()

        if not user:
            # Create new user if not exists
            current_app.logger.info(
                f"Creating new user for Spotify ID: {spotify_user['id']}"
            )
            user = User(
                spotify_id=spotify_user["id"],
                email=spotify_user.get("email"),
                display_name=spotify_user.get("display_name"),
            )

            # Get profile image if available
            if spotify_user.get("images") and len(spotify_user["images"]) > 0:
                user.profile_image = spotify_user["images"][0].get("url")

            db.session.add(user)
        else:
            current_app.logger.info(f"User found for Spotify ID: {spotify_user['id']}")

        # Update user info
        user.set_spotify_tokens(
            token_info["access_token"],
            token_info["refresh_token"],
            token_info["expires_in"],
        )
        user.last_login = datetime.utcnow()

        # Ensure user has a database
        user.create_user_db(current_app.config)

        db.session.commit()

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
