from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    jsonify,
)
from flask_login import current_user, login_required
import csv
import io
import json
from app import db
from app.admin import bp
from app.models import BetaSignup, User


# Admin access decorator function
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if (
            not current_user.is_authenticated
            or current_user.spotify_id != "jinx_talaris"
        ):
            flash("Admin access required.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@bp.route("/beta-signups")
@login_required
@admin_required
def beta_signups():
    signups = BetaSignup.query.order_by(BetaSignup.created_at.desc()).all()
    return render_template(
        "admin/beta_signups.html", title="Beta Signups", signups=signups
    )


@bp.route("/export-signups/<format>")
@login_required
@admin_required
def export_signups(format):
    signups = BetaSignup.query.order_by(BetaSignup.created_at.desc()).all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Email", "Signup Date"])

        for signup in signups:
            writer.writerow(
                [
                    signup.id,
                    signup.name,
                    signup.email,
                    signup.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )

        response_data = output.getvalue()
        headers = {
            "Content-Disposition": "attachment; filename=beta_signups.csv",
            "Content-Type": "text/csv",
        }

        return response_data, 200, headers

    elif format == "json":
        signup_list = []
        for signup in signups:
            signup_list.append(
                {
                    "id": signup.id,
                    "name": signup.name,
                    "email": signup.email,
                    "created_at": signup.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        response_data = json.dumps(signup_list, indent=2)
        headers = {
            "Content-Disposition": "attachment; filename=beta_signups.json",
            "Content-Type": "application/json",
        }

        return response_data, 200, headers

    flash("Invalid export format", "danger")
    return redirect(url_for("admin.beta_signups"))
