"""SQLite compatibility update for historical question rows."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from .extensions import db


def _sqlite_path(uri: str) -> Path | None:
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return None
    raw = uri[len(prefix):]
    if not raw or raw == ":memory:" or raw.startswith("file:"):
        return None
    return Path(raw).expanduser()


def ensure_compatibility_schema(uri: str) -> None:
    """Add the stored difficulty level without rewriting an existing database."""
    path = _sqlite_path(uri)
    if path is None or not path.exists():
        return
    inspector = inspect(db.engine)
    if "quest_question" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("quest_question")}
    if "difficulty_level" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE quest_question ADD COLUMN difficulty_level "
                "INTEGER NOT NULL DEFAULT 1"
            ))
