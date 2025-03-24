from flask import Blueprint

bp = Blueprint("spotify", __name__)

from app.spotify import routes
