from flask import Blueprint, render_template, jsonify
from .metrics_decorator import get_metrics, reset_metrics
from flask_login import login_required
from flask import current_app


# These routes will be added to the admin blueprint
def register_metrics_routes(admin_bp):
    @admin_bp.route("/metrics", methods=["GET"])
    @login_required
    def view_metrics():
        all_metrics = get_metrics()
        return render_template("admin/metrics_dashboard.html", metrics=all_metrics)

    @admin_bp.route("/metrics/data", methods=["GET"])
    @login_required
    def get_metrics_data():
        return jsonify(get_metrics())

    @admin_bp.route("/metrics/reset", methods=["POST"])
    @login_required
    def reset_metrics_data():
        reset_metrics()
        return jsonify({"status": "success", "message": "Metrics have been reset"})

    @admin_bp.route("/metrics/reset/<func_name>", methods=["POST"])
    @login_required
    def reset_function_metrics(func_name):
        reset_metrics(func_name)
        return jsonify(
            {"status": "success", "message": f"Metrics for {func_name} have been reset"}
        )
