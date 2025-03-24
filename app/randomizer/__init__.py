# app/randomizer/__init__.py
from flask import Blueprint

randomizer = Blueprint("randomizer", __name__)

from app.randomizer import routes
