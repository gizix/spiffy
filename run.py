from app import create_app, db
from app.models import User, SpotifyDataType, UserDataSync
from datetime import datetime
from flask import redirect, url_for, request, current_app
import logging
import os

app = create_app()

# Configure logging
if not app.debug:
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.mkdir("logs")
    file_handler = logging.FileHandler("logs/spotify_explorer.log")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(module)s: %(message)s")
    )
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Spiffy startup")
else:
    # More verbose logging in debug mode
    logging.basicConfig(level=logging.DEBUG)


@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "User": User,
        "SpotifyDataType": SpotifyDataType,
        "UserDataSync": UserDataSync,
    }


# Add a root-level callback route that redirects to the auth callback
@app.route("/callback")
def callback_redirect():
    app.logger.info(f"Root callback hit with args: {request.args}")
    return redirect(url_for("auth.callback", **request.args))


if __name__ == "__main__":
    app.run(debug=True)
