"""Small, additive schema compatibility updates for the SQLite household app."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from .extensions import db


def _sqlite_path(uri: str) -> Path | None:
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return None
    raw = uri[len(prefix) :]
    if not raw or raw == ":memory:" or raw.startswith("file:"):
        return None
    return Path(raw).expanduser()


def ensure_compatibility_schema(uri: str) -> None:
    """Apply safe additions when an existing SQLite database needs them.

    ``db.create_all()`` creates the field for new databases, but it does not
    alter a family's existing database. Do not open a path that does not exist:
    the server uses that absence to give a useful "run setup" message.
    """
    path = _sqlite_path(uri)
    if path is None or not path.exists():
        return

    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if not tables:
        return
    parent_additions = {
        "login_name": "VARCHAR(80) NOT NULL DEFAULT 'parent'",
        "auth_version": "INTEGER NOT NULL DEFAULT 1",
        "setup_complete": "BOOLEAN NOT NULL DEFAULT 0",
        "bootstrap_token_hash": "VARCHAR(255)",
        "bootstrap_token_consumed_at": "DATETIME",
    }
    learner_additions = {
        "auth_nonce": "VARCHAR(64)",
    }
    settings_additions = {
        "great_enabled": "BOOLEAN NOT NULL DEFAULT 1",
        "great_diagnostic": "BOOLEAN NOT NULL DEFAULT 0",
        "gcse_subject": "VARCHAR(30) NOT NULL DEFAULT 'gcse_maths'",
        "gcse_tier": "VARCHAR(20) NOT NULL DEFAULT 'off'",
        "gcse_board": "VARCHAR(20) NOT NULL DEFAULT 'generic'",
    }
    question_additions = {
        "response_json": "JSON",
        "response_status": "VARCHAR(20) NOT NULL DEFAULT 'unanswered'",
        "score": "INTEGER",
        "max_score": "INTEGER",
        "assessment_json": "JSON",
        "difficulty_level": "INTEGER NOT NULL DEFAULT 1",
    }
    quest_additions = {
        "practice_profile": "VARCHAR(30) NOT NULL DEFAULT 'standard'",
    }
    additions_by_table = {
        "parent_account": parent_additions,
        "learner_account": learner_additions,
        "settings": settings_additions,
        "quest": quest_additions,
        "quest_question": question_additions,
    }

    with db.engine.begin() as connection:
        for table, additions in additions_by_table.items():
            if table not in tables:
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
                    )

        if "parent_account" in tables:
            # Existing databases predate the parent handle. Resolve any
            # duplicate legacy handles before adding the storage invariant.
            seen: set[str] = set()
            rows = connection.execute(
                text("SELECT id, login_name FROM parent_account ORDER BY id")
            ).mappings().all()
            for row in rows:
                original = str(row["login_name"] or "parent").strip()
                base = original or "parent"
                candidate = base
                suffix = 2
                while candidate.lower() in seen:
                    candidate = f"{base}-{suffix}"
                    suffix += 1
                if candidate != original:
                    connection.execute(
                        text(
                            "UPDATE parent_account SET login_name = :login_name "
                            "WHERE id = :id"
                        ),
                        {"login_name": candidate, "id": row["id"]},
                    )
                seen.add(candidate.lower())
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_parent_account_login_name "
                    "ON parent_account (login_name)"
                )
            )
