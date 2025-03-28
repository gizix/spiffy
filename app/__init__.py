from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
import os
from app.jinja_filters import register_filters

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    register_filters(app)

    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.main import bp as main_bp

    app.register_blueprint(main_bp)

    from app.spotify import bp as spotify_bp

    app.register_blueprint(spotify_bp, url_prefix="/spotify")

    from app.admin import bp as admin_bp
    from app.admin.metrics_routes import register_metrics_routes

    register_metrics_routes(admin_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.randomizer import randomizer as randomizer_bp

    app.register_blueprint(randomizer_bp)

    os.makedirs(app.instance_path, exist_ok=True)
    user_db_path = app.config.get("USER_DB_PATH")
    if user_db_path:
        os.makedirs(user_db_path, exist_ok=True)

    # Register custom template filters
    @app.template_filter("from_json")
    def from_json_filter(value):
        import json

        try:
            return json.loads(value)
        except:
            return {}

    @app.template_filter("tojson")
    def tojson_filter(value, indent=None):
        import json

        try:
            return json.dumps(value, indent=indent)
        except:
            return "{}"

    return app


from app import models
