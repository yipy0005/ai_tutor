"""Application configuration.

Everything here has a sensible default so the app runs with zero setup.
Override any value with an environment variable of the same name.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def _secret_key() -> str:
    """Use a stable secret so sessions survive a restart.

    A key is generated once and cached in the instance folder. That keeps a
    child logged in across restarts without asking a parent to configure
    anything.
    """
    env = os.environ.get("SECRET_KEY")
    if env:
        return env

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / "secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()

    key = secrets.token_hex(32)
    key_file.write_text(key, encoding="utf-8")
    key_file.chmod(0o600)
    return key


class Config:
    SECRET_KEY = _secret_key()

    BASE_DIR = BASE_DIR
    INSTANCE_DIR = INSTANCE_DIR
    DB_PATH = INSTANCE_DIR / "tutor.sqlite3"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DB_PATH}"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Sessions last a long time: a child should never meet a login screen.
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 90
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True

    JSON_SORT_KEYS = False
    TEMPLATES_AUTO_RELOAD = True

    # The parent area is protected by a PIN. This is the value used when a
    # profile is first created; a parent can change it in Parent -> Settings.
    DEFAULT_PARENT_PIN = os.environ.get("DEFAULT_PARENT_PIN", "1234")

    # Host/port used by `pixi run serve`.
    # 5001 rather than 5000: on macOS the AirPlay Receiver service holds 5000
    # and answers with a bare 403, which is a confusing thing to debug.
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5001"))
