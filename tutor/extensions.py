"""Shared Flask extension objects and SQLite tuning."""

from __future__ import annotations

import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models."""


db = SQLAlchemy(model_class=Base)


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """Apply the pragmas a small multi-device household app wants.

    * ``WAL`` lets a parent read the dashboard while a child is answering
      questions, instead of one blocking the other.
    * ``busy_timeout`` waits politely for a brief lock rather than raising
      "database is locked" at whoever tapped second.
    * ``foreign_keys`` makes SQLite actually honour the ON DELETE CASCADE rules
      declared on the models, so deleting a learner cannot leave orphan rows.
    """
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
