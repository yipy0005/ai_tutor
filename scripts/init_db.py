"""Create the SQLite database and all tables.

    pixi run init-db
"""

from __future__ import annotations

from tutor import create_app, db
from tutor.services import maintenance


def main() -> int:
    app = create_app()
    with app.app_context():
        db.create_all()
        # Report the database actually in use, which DATABASE_URL can override.
        print(f"Database ready at {maintenance.live_db_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
