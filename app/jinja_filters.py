"""
Custom Jinja2 filters for the application.
This module contains filters that can be registered with Flask to enhance templates.
"""

from flask import Blueprint


def format_number(value):
    """
    Format numbers to be more readable by converting large numbers
    to K (thousands) or M (millions) format.

    Args:
        value: The number to format

    Returns:
        str: Formatted number string (e.g., 1.2K, 3.5M)
    """
    try:
        value = int(value)
        if value >= 1000000:
            return f"{value / 1000000:.1f}M"
        elif value >= 1000:
            return f"{value / 1000:.1f}K"
        return str(value)
    except (ValueError, TypeError):
        return "0"


def register_filters(app):
    """
    Register all custom filters with the Flask app.

    Args:
        app: Flask application instance
    """
    app.jinja_env.filters["format_number"] = format_number
