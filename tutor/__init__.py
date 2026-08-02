"""Application factory.

    pixi run dev     development server with reload
    pixi run serve   everyday family use
"""

from __future__ import annotations

import secrets
from datetime import date, datetime

from flask import Flask, g, jsonify, render_template, request, session

from .config import Config
from .extensions import db

__all__ = ["create_app", "db"]

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)
    config_object.INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from . import models  # noqa: F401  (registers the tables)

    _register_blueprints(app)
    _register_csrf(app)
    _register_context(app)
    _register_filters(app)
    _register_errors(app)

    return app


# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------


def _register_blueprints(app: Flask) -> None:
    from .blueprints.api import bp as api_bp
    from .blueprints.kid import bp as kid_bp
    from .blueprints.parent import bp as parent_bp

    app.register_blueprint(kid_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(parent_bp)


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------


def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def _register_csrf(app: Flask) -> None:
    @app.before_request
    def check_csrf():  # noqa: ANN202
        if request.method in SAFE_METHODS:
            return None
        if request.endpoint == "static":
            return None
        sent = (
            request.headers.get("X-CSRF-Token")
            or request.form.get("_csrf")
            or (request.get_json(silent=True) or {}).get("_csrf")
        )
        expected = session.get("_csrf")
        if not expected or not sent or not secrets.compare_digest(str(sent), str(expected)):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Your session expired. Please reload the page."}), 400
            return render_template("errors/expired.html"), 400
        return None


# ---------------------------------------------------------------------------
# Template context and filters
# ---------------------------------------------------------------------------


def _register_context(app: Flask) -> None:
    from .content import SUBJECT_ORDER, SUBJECTS, YEAR_BLURBS, YEAR_LABELS
    from .services import profiles

    @app.context_processor
    def inject_globals():  # noqa: ANN202
        child = getattr(g, "child", None)
        settings = child.settings if child else None
        return {
            "csrf_token": csrf_token,
            "SUBJECTS": SUBJECTS,
            "SUBJECT_ORDER": SUBJECT_ORDER,
            "YEAR_LABELS": YEAR_LABELS,
            "YEAR_BLURBS": YEAR_BLURBS,
            "child": child,
            "settings": settings,
            "body_classes": _body_classes(settings),
            "today": date.today(),
            "now": datetime.now(),
            "parent_unlocked": bool(session.get("parent_ok")),
            "child_count": len(profiles.all_children()),
        }


def _body_classes(settings) -> str:
    if settings is None:
        return ""
    classes = []
    if settings.dyslexia_font:
        classes.append("font-friendly")
    if settings.large_text:
        classes.append("text-large")
    if settings.high_contrast:
        classes.append("contrast-high")
    if not settings.animations_enabled:
        classes.append("motion-off")
    return " ".join(classes)


def _register_filters(app: Flask) -> None:
    @app.template_filter("minutes")
    def minutes_filter(seconds: int | None) -> str:
        seconds = int(seconds or 0)
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{round(seconds / 60)} min"
        hours, rest = divmod(seconds, 3600)
        return f"{hours}h {round(rest / 60)}m"

    @app.template_filter("shortdate")
    def shortdate_filter(value) -> str:
        if not value:
            return "—"
        return value.strftime("%-d %b") if hasattr(value, "strftime") else str(value)

    @app.template_filter("longdate")
    def longdate_filter(value) -> str:
        if not value:
            return "—"
        return value.strftime("%A %-d %B") if hasattr(value, "strftime") else str(value)

    @app.template_filter("clocktime")
    def clocktime_filter(value) -> str:
        if not value:
            return "—"
        return value.strftime("%-I:%M %p").lower() if hasattr(value, "strftime") else str(value)

    @app.template_filter("ago")
    def ago_filter(value) -> str:
        if not value:
            return "never"
        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())
        delta = datetime.now() - value
        seconds = delta.total_seconds()
        if seconds < 90:
            return "just now"
        if seconds < 3600:
            return f"{int(seconds // 60)} min ago"
        if seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        days = int(seconds // 86400)
        if days == 1:
            return "yesterday"
        if days < 14:
            return f"{days} days ago"
        return value.strftime("%-d %b")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def _register_errors(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(error):  # noqa: ANN202
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):  # noqa: ANN202
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify({"error": "Something went wrong on our side."}), 500
        return render_template("errors/500.html"), 500
