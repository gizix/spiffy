from flask import render_template, redirect, url_for, current_app
from flask_login import current_user, login_required
from app.main import bp
from app.models import User, UserDataSync, SpotifyDataType


@bp.route("/")
@bp.route("/index")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    return render_template("main/index.html", title="Home")


@bp.route("/about")
def about():
    return render_template("main/about.html", title="About")


@bp.route("/dashboard")
@login_required
def dashboard():
    data_types = SpotifyDataType.query.all()
    user_syncs = UserDataSync.query.filter_by(user_id=current_user.id).all()

    sync_status = {}
    for data_type in data_types:
        sync_status[data_type.id] = None

    for sync in user_syncs:
        sync_status[sync.data_type_id] = sync

    return render_template(
        "main/dashboard.html",
        title="Dashboard",
        data_types=data_types,
        sync_status=sync_status,
    )
